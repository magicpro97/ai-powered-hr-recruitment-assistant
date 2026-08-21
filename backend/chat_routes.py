"""
Chat API endpoints for conversational AI Agent
Maintains context across multiple interactions
"""

# Standard library imports
import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

# Third-party imports
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Local application imports
from backend.access_control import (
    Viewer,
    build_chat_upload_response,
    resolve_owner_id,
)
from backend.auth_cookies import optional_user_from_cookie
from backend.guest_limits import require_guest_quota

# Rate limiting
from backend.limiter import limiter
from backend.logging_config import get_logger

# Import sanitization and logging
from backend.sanitization import sanitize_user_input, validate_session_id
from backend.security import csrf_protected_optional_user
from src.agents.memory import (
    ContextManager,
    ConversationMemory,
    SessionOwnershipError,
    enforce_session_claim,
)
from src.agents.recruitment_agent import RecruitmentAgent

# from src.config import Config  # Unused in main logic, Config accessed
# via dependencies or objects
from src.config import Config
from src.dependencies import (
    get_context_manager_dep,
    get_cv_processor,
    get_job_processor,
    get_matching_engine,
    get_memory_dep,
    get_question_generator,
    get_recruitment_agent,
)
from src.processors.cv_processor import CVProcessor
from src.processors.job_processor import JobProcessor
from src.processors.matching_engine import MatchingEngine
from src.processors.question_generator import QuestionGenerator

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Initialize components -> REMOVED global init
# vector_store = VectorStore(Config.CHROMA_PERSIST_DIR)
# recruitment_agent = RecruitmentAgent(vector_store)
# ...


class ChatMessage(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., max_length=10000)
    context: Optional[Dict[str, Any]] = None
    # UI language preference ("vi" or "en") — takes priority over detection
    language: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    response: str
    suggestions: List[str]
    context_summary: str


@router.post("/upload-cv")
@limiter.limit("30/minute")
async def upload_cv_via_chat(
    request: Request,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    cv_processor: CVProcessor = Depends(get_cv_processor),
    context_manager: ContextManager = Depends(get_context_manager_dep),
    memory: ConversationMemory = Depends(get_memory_dep),
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Upload a CV directly from the chat widget and auto-process it."""
    # Enforce guest quota for anonymous users
    await require_guest_quota(request, "cvs", current_user=current_user)

    # Local application imports
    from backend.file_validation import validate_pdf_file

    session_id = session_id or str(uuid.uuid4())

    # Validate file upload with MIME type verification
    try:
        file_content, safe_filename = await validate_pdf_file(file)
    except HTTPException as e:
        logger.warning(
            "cv_upload_rejected",
            session_id=session_id,
            filename=file.filename,
            reason=str(e.detail),
        )
        raise

    # ClamAV virus scan
    # Local application imports
    from backend.clamav_scanner import scan_file_bytes

    is_safe, threat = await asyncio.to_thread(scan_file_bytes, file_content)
    if not is_safe:
        logger.warning(
            "Malicious file upload blocked via chat",
            threat=threat,
        )
        raise HTTPException(
            status_code=400,
            detail="File rejected: uploaded file failed security scanning",
        )

    try:
        # Resolve owner
        owner_id = resolve_owner_id(request, current_user)

        # Enforce session ownership BEFORE any file processing or context writes
        is_admin = current_user.get("role") == "admin" if current_user else False
        try:
            enforce_session_claim(memory, session_id, owner_id, is_admin=is_admin)
        except SessionOwnershipError:
            raise HTTPException(status_code=404, detail="Session not found")

        # Generate cv_id BEFORE save
        cv_id = str(uuid.uuid4())

        # Save validated file with server-controlled storage_key
        # Local application imports
        from src.utils.file_utils import save_uploaded_file

        upload_dir = Path(Config.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        # Standard library imports
        import io

        file_obj = io.BytesIO(file_content)
        file_obj.filename = safe_filename
        saved_path = save_uploaded_file(file_obj, str(upload_dir), storage_key=cv_id)

        cv_data = cv_processor.process_cv(cv_id, saved_path, user_id=owner_id)

        processed_entry = {
            "cv_id": cv_id,
            "name": cv_data.get("name", "Unknown"),
            "file_path": os.path.basename(saved_path),
        }

        existing = (
            context_manager.get_context(session_id, "cvs", owner_id=owner_id) or []
        )
        existing.append(processed_entry)
        context_manager.store_context(session_id, "cvs", existing, owner_id=owner_id)
        context_manager.store_context(
            session_id, "cv_count", len(existing), owner_id=owner_id
        )
        context_manager.store_context(
            session_id, "workflow_stage", "cvs_ready", owner_id=owner_id
        )

        logger.info(
            "cv_upload_success",
            session_id=session_id,
            cv_id=cv_id,
            file_size=len(file_content),
        )

        summary = (
            f"📄 Uploaded & analyzed CV for {processed_entry['name']} (ID: {cv_id[:8]}...).\n"
            "You can type 'match candidates' or continue uploading more CVs."
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "cv_upload_processing_error", session_id=session_id, error=str(exc)
        )
        raise HTTPException(status_code=500, detail="Failed to process CV")

    # Strip email/phone/raw path from response — use safe DTO
    return build_chat_upload_response(
        session_id=session_id,
        cv_id=cv_id,
        name=cv_data.get("name", "Unknown"),
        skills=cv_data.get("skills", []),
        summary=cv_data.get("summary", ""),
        experience_years=cv_data.get("experience_years", 0),
        message=summary,
    )


@router.post("/message", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_message(
    request: Request,
    body: ChatMessage,
    memory: ConversationMemory = Depends(get_memory_dep),
    context_manager: ContextManager = Depends(get_context_manager_dep),
    recruitment_agent: RecruitmentAgent = Depends(get_recruitment_agent),
    job_processor: JobProcessor = Depends(get_job_processor),
    cv_processor: CVProcessor = Depends(get_cv_processor),
    matching_engine: MatchingEngine = Depends(get_matching_engine),
    question_generator: QuestionGenerator = Depends(get_question_generator),
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Conversational endpoint that can also orchestrate the full HR workflow."""
    # Enforce guest quota for anonymous users
    await require_guest_quota(request, "chat", current_user=current_user)

    session_id = body.session_id or str(uuid.uuid4())

    # Validate and sanitize session ID
    if not validate_session_id(session_id):
        logger.error("Invalid session ID format", session_id=session_id)
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    logger.info("Processing chat message", session_id=session_id)

    # Resolve owner for context scoping
    owner_id = resolve_owner_id(request, current_user)

    # Generate separate stable IDs for the user and assistant messages.
    user_message_id = str(uuid.uuid4())
    assistant_message_id = str(uuid.uuid4())

    # Sanitize user message
    sanitized_message = sanitize_user_input(body.message)
    if sanitized_message != body.message:
        logger.warning(
            "User message was sanitized",
            session_id=session_id,
            original_length=len(body.message),
            sanitized_length=len(sanitized_message),
        )

    # Auto-load session if it exists on disk
    if session_id not in memory.sessions:
        memory.load_session(session_id)

    # Enforce session ownership: claim new session or validate existing
    is_admin = current_user.get("role") == "admin" if current_user else False
    if session_id not in memory._session_owners:
        if session_id in memory.sessions:
            # Legacy unowned session — only admin can access
            if not is_admin:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            # New session — claim it for this owner
            memory.create_session(session_id, owner_id=owner_id)
    else:
        # Session exists — validate owner
        try:
            memory.require_session_owner(session_id, owner_id, is_admin=is_admin)
        except Exception:
            raise HTTPException(status_code=404, detail="Session not found")

    # Store the sanitized user message with its stable message ID.
    memory.add_message(
        session_id,
        "user",
        sanitized_message,
        message_id=user_message_id,
        owner_id=owner_id,
    )

    if body.context:
        for key, value in body.context.items():
            context_manager.store_context(session_id, key, value, owner_id=owner_id)

    # Use UI language preference if provided, otherwise detect from text
    user_lang = (
        body.language
        if body.language in ("vi", "en")
        else _detect_language(sanitized_message)
    )
    context_manager.store_context(session_id, "user_lang", user_lang, owner_id=owner_id)

    context_summary = context_manager.build_context_prompt(
        session_id, owner_id=owner_id
    )
    intent = _analyze_user_intent(
        session_id,
        sanitized_message,
        context_summary,
        context_manager,
        owner_id=owner_id,
    )

    # Handle different intent types
    if intent.get("action") == "off_topic":
        # For off-topic questions: polite redirect without losing context
        response_text = _generate_conversational_reply(
            session_id,
            sanitized_message,
            context_summary,
            memory,
            is_off_topic=True,
            context_manager=context_manager,
            owner_id=owner_id,
        )
    elif intent.get("action") == "general_conversation":
        response_text = _generate_conversational_reply(
            session_id,
            sanitized_message,
            context_summary,
            memory,
            is_off_topic=False,
            context_manager=context_manager,
            owner_id=owner_id,
        )
    else:
        action_result = _execute_chat_action(
            session_id,
            intent,
            job_processor,
            cv_processor,
            matching_engine,
            question_generator,
            context_manager,
            recruitment_agent,
            user_lang,
            current_user,
            owner_id=owner_id,
        )
        response_text = action_result.get(
            "message",
            (
                "I've completed your request."
                if user_lang == "en"
                else "Đã hoàn thành yêu cầu của bạn."
            ),
        )
    # Store the assistant response with its stable message ID.
    memory.add_message(
        session_id,
        "assistant",
        response_text,
        message_id=assistant_message_id,
        owner_id=owner_id,
    )

    # Save session after every interaction
    memory.save_session(session_id)

    # Also save context manager state
    context_manager.save_context(session_id)

    updated_context = context_manager.build_context_prompt(
        session_id, owner_id=owner_id
    )
    suggestions = _generate_suggestions(session_id, context_manager, owner_id=owner_id)

    # Strip internal LLM prompt markers before returning to client.
    # build_context_prompt output contains === CONVERSATION CONTEXT ===,
    # === STORED DATA ===, === END CONTEXT === structure that should not
    # be exposed to API consumers.
    client_context_summary = re.sub(r"={3,}[^=]*={3,}\s*", "", updated_context).strip()

    return ChatResponse(
        session_id=session_id,
        message_id=assistant_message_id,
        response=response_text,
        suggestions=suggestions,
        context_summary=client_context_summary,
    )


@router.get("/history/{session_id}")
@limiter.limit("60/minute")
async def get_chat_history(
    request: Request,
    session_id: str,
    limit: int = 20,
    memory: ConversationMemory = Depends(get_memory_dep),
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Get conversation history — owner-scoped, returns 404 for cross-owner."""
    owner_id = resolve_owner_id(request, current_user)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Session not found")
    is_admin = current_user.get("role") == "admin" if current_user else False
    # Auto-load if needed
    if session_id not in memory.sessions:
        memory.load_session(session_id)
    try:
        # Local application imports
        from src.agents.memory import SessionOwnershipError

        history = memory.get_session_history(
            session_id, limit=limit, owner_id=owner_id, is_admin=is_admin
        )
    except SessionOwnershipError:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "history": history}


@router.post("/clear/{session_id}")
@limiter.limit("10/minute")
async def clear_chat_history(
    request: Request,
    session_id: str,
    memory: ConversationMemory = Depends(get_memory_dep),
    context_manager: ContextManager = Depends(get_context_manager_dep),
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Clear conversation history — owner-scoped."""
    owner_id = resolve_owner_id(request, current_user)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Session not found")
    is_admin = current_user.get("role") == "admin" if current_user else False
    if session_id not in memory.sessions:
        memory.load_session(session_id)
    try:
        # Local application imports
        from src.agents.memory import SessionOwnershipError

        memory.clear_session(session_id, owner_id=owner_id, is_admin=is_admin)
    except SessionOwnershipError:
        raise HTTPException(status_code=404, detail="Session not found")
    context_manager.clear_context(session_id, owner_id=owner_id, is_admin=is_admin)
    return {"status": "cleared", "session_id": session_id}


@router.get("/context/{session_id}")
@limiter.limit("60/minute")
async def get_session_context(
    request: Request,
    session_id: str,
    context_manager: ContextManager = Depends(get_context_manager_dep),
    memory: ConversationMemory = Depends(get_memory_dep),
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Get stored context for session — owner-scoped."""
    owner_id = resolve_owner_id(request, current_user)
    if not owner_id:
        raise HTTPException(status_code=404, detail="Session not found")
    is_admin = current_user.get("role") == "admin" if current_user else False
    if session_id not in memory.sessions:
        memory.load_session(session_id)
    try:
        # Local application imports
        from src.agents.memory import SessionOwnershipError

        all_context = context_manager.get_all_context(
            session_id, owner_id=owner_id, is_admin=is_admin
        )
        decisions = context_manager.get_decision_history(
            session_id, owner_id=owner_id, is_admin=is_admin
        )
    except SessionOwnershipError:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "context": all_context,
        "decisions": decisions,
    }


def _generate_conversational_reply(
    session_id: str,
    user_message: str,
    context_summary: str,
    memory: ConversationMemory,
    is_off_topic: bool = False,
    context_manager: Optional[ContextManager] = None,
    owner_id: Optional[str] = None,
) -> str:
    """Fallback LLM response for small talk and unstructured queries."""
    history = memory.get_session_history(session_id, limit=10, owner_id=owner_id)
    llm = ChatOpenAI(model=Config.OPENAI_MODEL, temperature=0.7)

    # Get detected language from session
    user_lang = "en"
    if context_manager:
        user_lang = (
            context_manager.get_context(session_id, "user_lang", owner_id=owner_id)
            or "en"
        )

    lang_name = "Vietnamese" if user_lang == "vi" else "English"

    # Language instruction - respond in the same language as user
    language_instruction = (
        f"CRITICAL: You MUST respond in {lang_name}. "
        f"The user is communicating in {lang_name}, so all your responses must be in {lang_name}.\n\n"
    )

    # Different system messages based on topic relevance
    if is_off_topic:
        system_content = (
            "You are an AI recruitment assistant. The user just asked a question that is NOT related "
            "to HR, recruitment, hiring, or your purpose (e.g., weather, sports, math, general knowledge).\n\n"
            "Your response should:\n"
            "1. Politely acknowledge their question but explain you're specialized in recruitment\n"
            "2. Briefly redirect them back to what you CAN help with (job screening, CV analysis, interview questions)\n"
            "3. Keep it friendly and professional, not robotic\n"
            "4. Be concise (1-2 sentences max)\n\n"
            f"{language_instruction}"
            f"Current workflow context (DO NOT lose this):\n{context_summary}\n"
        )
    else:
        system_content = (
            "You are CV Screener — an AI-powered recruitment assistant. "
            "Here are the specific things you can do for the user:\n"
            "1. **Analyze job descriptions (JD)**: User sends/pastes a JD, you extract required skills, experience, responsibilities.\n"
            "2. **Screen & rank CVs**: Upload CVs (PDF) and match them against a job → get scored ranking with analysis.\n"
            "3. **Generate interview questions**: Create tailored interview questions for each candidate based on their CV and the job.\n"
            "4. **List jobs & CVs**: Show what's already in the system.\n"
            "5. **View details**: Inspect a specific job or candidate in depth.\n"
            "6. **Import jobs from TopCV / ITviec**: Scrape and import real job postings.\n"
            "7. **General recruitment advice**: Discuss hiring strategy, best practices, etc.\n\n"
            "When the user asks what you can do, list these capabilities clearly. "
            "Be concise, proactive, and helpful.\n\n"
            f"{language_instruction}"
            f"Context:\n{context_summary}\n"
        )

    messages: List[BaseMessage] = [SystemMessage(content=system_content)]

    for msg in history[-5:]:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_message))
    try:
        response = llm.invoke(messages)
    except Exception as e:
        logger.error("LLM invoke failed", session_id=session_id, error=str(e))
        return "I'm sorry, I encountered an error processing your request. Please try again."
    return str(response.content)


def _analyze_user_intent(
    session_id: str,
    user_message: str,
    context_summary: str,
    context_manager: ContextManager,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Use an LLM (with heuristics fallback) to decide which workflow step to run."""
    intent_prompt = f"""
You are an intent classifier for an HR recruitment assistant. Decide the next action the chatbot
should execute. Available actions:
- list_jobs: user wants to see existing job descriptions in the system (e.g., "có những JD nào", "list jobs", "show jobs", "danh sách công việc").
- search_jobs: user wants to search/filter jobs by keyword (e.g., "tìm kiếm Python", "search Java", "tìm vị trí kế toán", "find jobs with AWS"). Extract search_keyword from message.
- list_cvs: user wants to see existing CVs in the system (e.g., "có những CV nào", "list CVs", "show CVs", "danh sách ứng viên").
- view_job_detail: user wants detailed info about a SPECIFIC job (e.g., "chi tiết JD Senior Python", "xem JD 5a86ba", "job detail"). Extract job_identifier from message.
- view_cv_detail: user wants detailed info about a SPECIFIC CV/candidate (e.g., "chi tiết CV Nguyen Van A", "xem CV abc123", "thông tin ứng viên"). Extract cv_identifier from message.
- provide_job_description: user shared a job description or asked you to capture/understand it.
- provide_cv_paths: user referenced CV file names/paths or asked to process uploaded CVs.
- run_matching: user wants candidate scoring or shortlist (e.g., "match candidates", "screen CVs", "rank candidates").
- select_job: user is selecting a specific job from a previously listed set,
  by number (e.g., "1", "Công việc 1", "Job 2", "vị trí 3") or by partial
  name (e.g., "Platform Engineer", "Kế toán"). Extract job_number (int) or
  job_name (string).
- generate_questions: user wants interview questions for a candidate.
- run_full_workflow: user asked to run the complete AI agent pipeline.
- workflow_status: user asked for progress or what's already done.
- general_conversation: chit-chat, product questions, or anything related to recruitment but not a specific workflow action.
- off_topic: questions completely unrelated to HR, recruitment, hiring, or this assistant's purpose (e.g., weather, sports, cooking, math problems, general knowledge).

IMPORTANT RULES:
1. If the context shows that CVs have already been uploaded/processed, and the user asks to
   "match candidates" or similar, return action="run_matching" (NOT provide_cv_paths).
2. For off_topic questions: preserve all existing context, do NOT clear or modify workflow state.
3. Off-topic includes: weather, sports, entertainment, cooking, math, science facts, travel, etc.
4. Recruitment-related discussions (hiring strategy, interview tips) = general_conversation.
5. Completely unrelated topics = off_topic.

Return strict JSON with keys: action (string), job_text (string), cv_paths (list of strings),
candidate_name (string), top_k (int), notes (string), job_identifier (string for job name/ID),
cv_identifier (string for CV name/ID), search_keyword (string for job search). Use blank/empty values when not provided.

Context summary:
{context_summary}

User message:
{user_message}
"""

    intent: Dict[str, Any] = {}

    # Pre-LLM heuristic: if user sends a short number/job-selection pattern
    # and listed_jobs exist, skip the LLM entirely for faster response
    user_lower = user_message.lower().strip()
    listed_jobs = context_manager.get_context(
        session_id, "listed_jobs", owner_id=owner_id
    )
    if _is_job_selection(user_lower, listed_jobs):
        job_number = _extract_job_number(user_lower)
        return {
            "action": "select_job",
            "job_number": job_number,
            "job_name": user_message,
        }

    try:
        llm = ChatOpenAI(model=Config.OPENAI_MODEL, temperature=0)
        llm_response = llm.invoke([HumanMessage(content=intent_prompt)])
        content_str = str(llm_response.content).strip()

        # Remove markdown code blocks if present
        if content_str.startswith("```json"):
            content_str = content_str[7:]
        elif content_str.startswith("```"):
            content_str = content_str[3:]
        if content_str.endswith("```"):
            content_str = content_str[:-3]
        content_str = content_str.strip()

        parsed = json.loads(content_str)
        if isinstance(parsed, dict):
            intent = cast(Dict[str, Any], parsed)
    except Exception as e:
        logger.error("Error parsing intent", error=str(e))
        intent = {}

    # Heuristic fallbacks
    if not intent.get("action"):
        user_lower = user_message.lower()

        # Check for view detail keywords first (more specific)
        if any(
            keyword in user_lower
            for keyword in [
                "chi tiết jd",
                "chi tiết job",
                "xem jd",
                "thông tin jd",
                "job detail",
                "jd detail",
            ]
        ):
            intent = {
                "action": "view_job_detail",
                "job_identifier": user_message,
            }
        elif any(
            keyword in user_lower
            for keyword in [
                "chi tiết cv",
                "xem cv",
                "thông tin cv",
                "thông tin ứng viên",
                "cv detail",
                "candidate detail",
            ]
        ):
            intent = {
                "action": "view_cv_detail",
                "cv_identifier": user_message,
            }
        # Check for job search keywords
        search_match = re.match(
            r"^(?:tìm kiếm|tìm|search|find)\s+(.+)$", user_lower.strip()
        )
        if search_match:
            intent = {
                "action": "search_jobs",
                "search_keyword": search_match.group(1).strip(),
            }
        # Check for list jobs/CVs keywords
        elif any(
            keyword in user_lower
            for keyword in [
                "jd nào",
                "job nào",
                "list job",
                "show job",
                "danh sách công việc",
                "những jd",
                "những job",
                "existing job",
            ]
        ):
            intent = {"action": "list_jobs"}
        elif any(
            keyword in user_lower
            for keyword in [
                "cv nào",
                "list cv",
                "show cv",
                "danh sách cv",
                "những cv",
                "danh sách ứng viên",
                "existing cv",
            ]
        ):
            intent = {"action": "list_cvs"}
        # Check for job selection by number or name (e.g., "1", "Công việc 1", "Job 2", "vị trí 3")
        elif _is_job_selection(
            user_lower,
            context_manager.get_context(session_id, "listed_jobs", owner_id=owner_id),
        ):
            job_number = _extract_job_number(user_lower)
            intent = {
                "action": "select_job",
                "job_number": job_number,
                "job_name": user_message,
            }
        # Check for matching keywords
        elif any(
            keyword in user_lower
            for keyword in [
                "match",
                "screen",
                "rank",
                "shortlist",
                "candidate",
                "sàng lọc",
                "tìm ứng viên",
                "so khớp",
            ]
        ):
            # Always route to run_matching — it will handle missing job_id gracefully
            intent = {"action": "run_matching"}
        elif _looks_like_job_description(user_message):
            intent = {
                "action": "provide_job_description",
                "job_text": user_message,
            }
        else:
            intent = {"action": "general_conversation"}

    if intent.get("action") == "provide_job_description" and not intent.get("job_text"):
        if _looks_like_job_description(user_message):
            intent["job_text"] = user_message

    return intent


def _looks_like_job_description(text: str) -> bool:
    keywords = [
        "responsibilities",
        "requirements",
        "required skills",
        "job description",
        "about the role",
        "preferred skills",
    ]
    lowered = text.lower()
    return len(text) > 400 or any(keyword in lowered for keyword in keywords)


def _is_job_selection(user_lower: str, listed_jobs: Optional[List] = None) -> bool:
    """Check if user message is selecting a job by number or keyword."""
    if not listed_jobs:
        return False
    # Pure number: "1", "2", etc.
    if user_lower.strip().isdigit():
        return True
    # "Công việc 1", "Job 2", "vị trí 3", "#1"
    # Standard library imports
    import re

    if re.match(r"^(công việc|job|vị trí|position|#)\s*\d+$", user_lower.strip()):
        return True
    # Short text that matches a job title partially (not a full JD)
    if len(user_lower) < 100:
        for job in listed_jobs:
            title_lower = job.get("title", "").lower()
            if user_lower.strip() in title_lower or title_lower in user_lower.strip():
                return True
    return False


def _extract_job_number(user_lower: str) -> Optional[int]:
    """Extract job number from user message like '1', 'Công việc 2', 'Job 3'."""
    # Standard library imports
    import re

    # Pure number
    stripped = user_lower.strip()
    if stripped.isdigit():
        return int(stripped)
    # "Công việc 1", "Job 2", etc.
    m = re.search(r"\d+", stripped)
    if m:
        return int(m.group())
    return None


def _extract_pdf_paths(text: str) -> List[str]:
    matches = re.findall(r"[\w./-]+\.pdf", text, flags=re.IGNORECASE)
    # Preserve order while removing duplicates
    seen = []
    for path in matches:
        norm = path.strip()
        if norm not in seen:
            seen.append(norm)
    return seen


def _resolve_cv_path(raw_path: str) -> Optional[str]:
    """Resolve user-provided CV hints to actual files on disk.

    Security: reject dangerous raw paths before any filesystem access.
    Never accept absolute paths, traversal, or arbitrary client paths.
    """
    cleaned = raw_path.strip().strip('"')

    # Security: reject dangerous paths before any filesystem access
    if "\0" in cleaned:
        return None
    if ".." in cleaned:
        return None
    if os.path.isabs(cleaned):
        return None
    # Reject Windows-style absolute paths (e.g., C:\...)
    if len(cleaned) >= 2 and cleaned[1] == ":":
        return None

    candidates = []
    candidates.append(os.path.join(Config.UPLOAD_DIR, cleaned))
    candidates.append(os.path.join(Config.UPLOAD_DIR, os.path.basename(cleaned)))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None


def _detect_language(text: str) -> str:
    """Simple language detection based on Vietnamese characters."""
    vietnamese_chars = set(
        "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    )
    text_lower = text.lower()
    has_vietnamese = any(char in vietnamese_chars for char in text_lower)
    return "vi" if has_vietnamese else "en"


def _find_job_by_identifier(
    identifier: str,
    job_processor: JobProcessor,
    user_id: Optional[str] = None,
    is_admin: bool = False,
) -> Optional[Dict]:
    """Find a job by ID, title substring, or number from list."""
    if not identifier:
        return None

    jobs = job_processor.list_all_jobs(
        user_id=user_id, include_public=True, is_admin=is_admin
    )
    if not jobs:
        return None

    identifier_lower = identifier.lower()

    # Try to find by exact ID match first
    for job in jobs:
        job_id = job.get("id", "")
        if job_id and (job_id == identifier or job_id.startswith(identifier)):
            return job

    # Try to find by title substring
    for job in jobs:
        title = job.get("metadata", {}).get("title", "").lower()
        if title and (identifier_lower in title or title in identifier_lower):
            return job

    # Try to find by number (e.g., "JD 1", "job số 2")
    # Standard library imports
    import re

    num_match = re.search(r"(\d+)", identifier)
    if num_match:
        idx = int(num_match.group(1)) - 1  # Convert to 0-based
        if 0 <= idx < len(jobs):
            return jobs[idx]

    return None


def _find_cv_by_identifier(
    identifier: str,
    cv_processor: CVProcessor,
    user_id: Optional[str] = None,
    is_admin: bool = False,
) -> Optional[Dict]:
    """Find a CV by ID, name substring, or number from list."""
    if not identifier:
        return None

    cvs = cv_processor.list_all_cvs(
        user_id=user_id, include_public=True, is_admin=is_admin
    )
    if not cvs:
        return None

    identifier_lower = identifier.lower()

    # Try to find by exact ID match first
    for cv in cvs:
        cv_id = cv.get("id", "")
        if cv_id and (cv_id == identifier or cv_id.startswith(identifier)):
            return cv

    # Try to find by name substring
    for cv in cvs:
        name = cv.get("metadata", {}).get("name", "").lower()
        if name and (identifier_lower in name or name in identifier_lower):
            return cv

    # Try to find by number (e.g., "CV 1", "ứng viên số 2")
    # Standard library imports
    import re

    num_match = re.search(r"(\d+)", identifier)
    if num_match:
        idx = int(num_match.group(1)) - 1  # Convert to 0-based
        if 0 <= idx < len(cvs):
            return cvs[idx]

    return None


def _format_job_detail(job: Dict, lang: str = "en") -> str:
    """Format detailed job information for display."""
    meta = job.get("metadata", {})
    job_id = job.get("id", "N/A")
    title = meta.get("title", "Untitled")
    exp = meta.get("experience_years", "N/A")

    required_skills = meta.get("required_skills", [])
    if isinstance(required_skills, str):
        required_skills = [s.strip() for s in required_skills.split(",")]

    preferred_skills = meta.get("preferred_skills", [])
    if isinstance(preferred_skills, str):
        preferred_skills = [s.strip() for s in preferred_skills.split(",")]

    responsibilities = meta.get("responsibilities", [])
    if isinstance(responsibilities, str):
        responsibilities = [r.strip() for r in responsibilities.split(",")]

    education = meta.get("education", "N/A")

    if lang == "vi":
        lines = [
            f"📋 **Chi tiết vị trí: {title}**\n",
            f"🔑 **ID:** `{job_id}`\n",
            f"⏱️ **Kinh nghiệm yêu cầu:** {exp}\n",
            f"🎓 **Học vấn:** {education}\n",
            "\n🛠️ **Kỹ năng bắt buộc:**",
        ]
        if required_skills:
            for skill in required_skills[:8]:
                lines.append(f"   • {skill}")
        else:
            lines.append("   • Chưa xác định")

        lines.append("\n⭐ **Kỹ năng ưu tiên:**")
        if preferred_skills:
            for skill in preferred_skills[:5]:
                lines.append(f"   • {skill}")
        else:
            lines.append("   • Chưa xác định")

        if responsibilities:
            lines.append("\n📝 **Trách nhiệm chính:**")
            for resp in responsibilities[:5]:
                lines.append(f"   • {resp}")

        lines.append(f"\n\n💡 *Gõ 'match {title}' để tìm ứng viên phù hợp!*")
    else:
        lines = [
            f"📋 **Job Details: {title}**\n",
            f"🔑 **ID:** `{job_id}`\n",
            f"⏱️ **Experience Required:** {exp}\n",
            f"🎓 **Education:** {education}\n",
            "\n🛠️ **Required Skills:**",
        ]
        if required_skills:
            for skill in required_skills[:8]:
                lines.append(f"   • {skill}")
        else:
            lines.append("   • Not specified")

        lines.append("\n⭐ **Preferred Skills:**")
        if preferred_skills:
            for skill in preferred_skills[:5]:
                lines.append(f"   • {skill}")
        else:
            lines.append("   • Not specified")

        if responsibilities:
            lines.append("\n📝 **Key Responsibilities:**")
            for resp in responsibilities[:5]:
                lines.append(f"   • {resp}")

        lines.append(f"\n\n💡 *Type 'match {title}' to find matching candidates!*")

    return "\n".join(lines)


def _format_cv_detail(
    cv: Dict, lang: str = "en", viewer_user_id: str = None, is_admin: bool = False
) -> str:
    """Format detailed CV information for display."""
    # Local application imports
    from backend.pii_masking import mask_cv_metadata

    meta = cv.get("metadata", {})
    # Mask PII if viewer is not the owner
    owner = meta.get("owner_user_id", "")
    is_owner = viewer_user_id and owner == viewer_user_id
    if not is_admin and not is_owner:
        meta = mask_cv_metadata(meta, is_owner=False)
    cv_id = cv.get("id", "N/A")
    name = meta.get("name", "Unknown")
    email = meta.get("email", "N/A")
    phone = meta.get("phone", "N/A")
    exp = meta.get("experience_years", "N/A")

    skills = meta.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",")]

    education = meta.get("education", "N/A")

    experience = meta.get("experience", [])
    if isinstance(experience, str):
        experience = [experience]

    if lang == "vi":
        lines = [
            f"👤 **Thông tin ứng viên: {name}**\n",
            f"🔑 **ID:** `{cv_id}`\n",
            f"📧 **Email:** {email}",
            f"📱 **Điện thoại:** {phone}\n",
            f"⏱️ **Kinh nghiệm:** {exp} năm",
            f"🎓 **Học vấn:** {education}\n",
        ]
        # Show download link for owner/admin, otherwise inform no permission
        if is_admin or is_owner:
            lines.append(
                f"📥 **Tải xuống:** [CV_{name}.pdf](/api/cvs/{cv_id}/download)\n"
            )
        else:
            lines.append(
                "🔒 *Chỉ chủ sở hữu CV hoặc quản trị viên mới có thể tải xuống file CV này.*\n"
            )
        lines.append("\n🛠️ **Kỹ năng:**")
        if skills:
            for skill in skills[:10]:
                lines.append(f"   • {skill}")
        else:
            lines.append("   • Chưa xác định")

        if experience:
            lines.append("\n💼 **Kinh nghiệm làm việc:**")
            for exp_item in experience[:5]:
                if isinstance(exp_item, dict):
                    company = exp_item.get("company", "")
                    role = exp_item.get("role", "")
                    lines.append(f"   • {role} @ {company}")
                else:
                    lines.append(f"   • {exp_item}")

        lines.append(f"\n\n💡 *Gõ 'tạo câu hỏi cho {name}' để tạo câu hỏi phỏng vấn!*")
    else:
        lines = [
            f"👤 **Candidate Profile: {name}**\n",
            f"🔑 **ID:** `{cv_id}`\n",
            f"📧 **Email:** {email}",
            f"📱 **Phone:** {phone}\n",
            f"⏱️ **Experience:** {exp} years",
            f"🎓 **Education:** {education}\n",
        ]
        # Show download link for owner/admin, otherwise inform no permission
        if is_admin or is_owner:
            lines.append(
                f"📥 **Download:** [CV_{name}.pdf](/api/cvs/{cv_id}/download)\n"
            )
        else:
            lines.append(
                "🔒 *Only the CV owner or an admin can download this CV file.*\n"
            )
        lines.append("\n🛠️ **Skills:**")
        if skills:
            for skill in skills[:10]:
                lines.append(f"   • {skill}")
        else:
            lines.append("   • Not specified")

        if experience:
            lines.append("\n💼 **Work Experience:**")
            for exp_item in experience[:5]:
                if isinstance(exp_item, dict):
                    company = exp_item.get("company", "")
                    role = exp_item.get("role", "")
                    lines.append(f"   • {role} @ {company}")
                else:
                    lines.append(f"   • {exp_item}")

        lines.append(
            f"\n\n💡 *Type 'generate questions for {name}' to create interview questions!*"
        )

    return "\n".join(lines)


# Bilingual message templates
MESSAGES = {
    "no_job_desc": {
        "vi": "Bạn chưa cung cấp mô tả công việc để tôi so sánh.",
        "en": "You haven't sent a job description yet for me to match against.",
    },
    "no_cvs": {
        "vi": 'Không tìm thấy CV nào trong cơ sở dữ liệu. Vui lòng tải CV lên trước qua trang "Upload CVs".',
        "en": "No CVs found in the database. Please upload CVs first via the 'Upload CVs' page.",
    },
    "no_matches": {
        "vi": "Không tìm thấy kết quả phù hợp. CVs có thể chưa được lưu vào database đúng cách.",
        "en": "No matching results found. CVs may not have been saved to the database correctly.",
    },
    "found_cvs": {
        "vi": "✅ Tìm thấy {count} CV trong cơ sở dữ liệu. Tôi sẽ sử dụng chúng để tìm ứng viên phù hợp.\n\n",
        "en": "✅ Found {count} CVs in the database. I'll use them for matching.\n\n",
    },
    "need_job_and_matches": {
        "vi": "Tôi cần mô tả công việc và danh sách ứng viên đã match trước khi tạo câu hỏi phỏng vấn.",
        "en": "I need a job description and matched candidates before generating questions.",
    },
    "candidate_not_found": {
        "vi": "Không thể xác định ứng viên. Bạn có thể chọn từ: {names}.",
        "en": "Could not identify candidate. You can choose from: {names}.",
    },
    "cv_id_not_found": {
        "vi": "Không tìm thấy CV ID cho ứng viên này.",
        "en": "Could not find CV ID for this candidate.",
    },
    "need_job_for_workflow": {
        "vi": "Vui lòng cung cấp mô tả công việc trước khi chạy quy trình đầy đủ.",
        "en": "Please send a job description before running the full workflow.",
    },
    "no_cvs_for_workflow": {
        "vi": "Không tìm thấy CV để chạy quy trình. Vui lòng cung cấp đường dẫn file.",
        "en": "No CVs found to run the workflow. Please send file paths.",
    },
    "jd_too_short": {
        "vi": "Vui lòng gửi mô tả công việc đầy đủ (ít nhất vài đoạn văn) để tôi phân tích!",
        "en": "Please send the complete job description (at least a few paragraphs) so I can analyze it!",
    },
    "no_cv_paths": {
        "vi": 'Tôi không thấy đường dẫn CV nào. Vui lòng gửi theo định dạng như "uploads/sample_cv.pdf".',
        "en": "I didn't see any CV paths. Please send them like 'uploads/sample_cv_excellent_match.pdf'.",
    },
    "conversation_mode": {
        "vi": "Tôi đang ở chế độ hội thoại. Hãy yêu cầu tôi phân tích JD, xử lý CV, hoặc sàng lọc ứng viên!",
        "en": "I'm in conversation mode. Please ask me to analyze a job, process CVs, or run the workflow!",
    },
}


def _get_message(key: str, lang: str, **kwargs) -> str:
    """Get bilingual message based on detected language."""
    msg_dict = MESSAGES.get(key, {})
    template = msg_dict.get(lang, msg_dict.get("en", key))
    return template.format(**kwargs) if kwargs else template


# Store current user language per session
# _session_language: Dict[str, str] = {}


def _execute_chat_action(
    session_id: str,
    intent: Dict[str, Any],
    # Processors injected
    job_processor: JobProcessor,
    cv_processor: CVProcessor,
    matching_engine: MatchingEngine,
    question_generator: QuestionGenerator,
    context_manager: ContextManager,
    recruitment_agent: RecruitmentAgent,
    user_lang: str = "en",
    current_user: Optional[Dict] = None,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a chat action based on user intent."""
    action = intent.get("action", "general_conversation")
    user_id = current_user.get("id") if current_user else owner_id
    is_admin = current_user.get("role") == "admin" if current_user else False
    try:
        if action == "list_jobs":
            jobs = job_processor.list_all_jobs(
                user_id=user_id, include_public=True, is_admin=is_admin
            )
            if not jobs:
                if user_lang == "vi":
                    return {
                        "status": "info",
                        "message": "📋 Chưa có mô tả công việc nào trong hệ thống. Bạn có thể gửi JD mới cho tôi!",
                    }
                else:
                    return {
                        "status": "info",
                        "message": "📋 No job descriptions in the system yet. You can send me a new JD!",
                    }

            # Show top 5 most recent jobs (last added)
            recent_jobs = jobs[-5:]
            recent_jobs.reverse()  # newest first

            if user_lang == "vi":
                header = f"📋 **{len(jobs)} vị trí tuyển dụng** trong hệ thống"
                if len(jobs) > 5:
                    header += " (hiển thị 5 gần nhất)"
                header += ":\n\n"
            else:
                header = f"📋 **{len(jobs)} job openings** in the system"
                if len(jobs) > 5:
                    header += " (showing 5 most recent)"
                header += ":\n\n"

            lines = []
            listed_jobs = []
            for i, job in enumerate(recent_jobs, 1):
                meta = job.get("metadata", {})
                title = meta.get("title", "Untitled")
                job_id = job.get("id") or job.get("job_id", "")
                exp = meta.get("experience_years", "N/A")

                skills = meta.get("required_skills", [])
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",")[:4]]
                elif isinstance(skills, list):
                    skills = skills[:4]

                # Get short summary from responsibilities
                responsibilities = meta.get("responsibilities", [])
                if isinstance(responsibilities, str):
                    try:
                        responsibilities = json.loads(
                            responsibilities.replace("'", '"')
                        )
                    except Exception:
                        responsibilities = [responsibilities]
                summary = (
                    responsibilities[0][:80] + "..."
                    if responsibilities and len(responsibilities[0]) > 80
                    else (responsibilities[0] if responsibilities else "")
                )

                job_link = f"#job-detail/{job_id}"
                listed_jobs.append({"index": i, "job_id": job_id, "title": title})

                if user_lang == "vi":
                    line = f"**{i}. [{title}]({job_link})**\n"
                    line += f"   ⏱️ Kinh nghiệm: {exp} | 🛠️ {', '.join(skills) if skills else 'Chưa xác định'}\n"
                    if summary:
                        line += f"   📝 _{summary}_"
                else:
                    line = f"**{i}. [{title}]({job_link})**\n"
                    line += f"   ⏱️ Experience: {exp} | 🛠️ {', '.join(skills) if skills else 'Not specified'}\n"
                    if summary:
                        line += f"   📝 _{summary}_"
                lines.append(line)

            if user_lang == "vi":
                footer = "\n\n💡 *Gửi số thứ tự (VD: '1') để chọn, hoặc gõ 'sàng lọc' để tìm ứng viên.*"
                if len(jobs) > 5:
                    footer += f"\n🔍 *Gõ 'tìm kiếm <từ khóa>' để tìm trong {len(jobs)} vị trí (VD: 'tìm kiếm Python').*"
            else:
                footer = "\n\n💡 *Send a number (e.g. '1') to select, or type 'screen' to find candidates.*"
                if len(jobs) > 5:
                    footer += f"\n🔍 *Type 'search <keyword>' to search across {len(jobs)} positions (e.g. 'search Python').*"

            context_manager.store_context(
                session_id, "listed_jobs", listed_jobs, owner_id=owner_id
            )

            return {
                "status": "success",
                "message": header + "\n".join(lines) + footer,
            }

        if action == "search_jobs":
            keyword = (intent.get("search_keyword") or "").strip().lower()
            if not keyword:
                if user_lang == "vi":
                    return {
                        "status": "info",
                        "message": "🔍 Vui lòng nhập từ khóa tìm kiếm (VD: 'tìm kiếm Python').",
                    }
                else:
                    return {
                        "status": "info",
                        "message": "🔍 Please enter a search keyword (e.g. 'search Python').",
                    }

            jobs = job_processor.list_all_jobs(
                user_id=user_id, include_public=True, is_admin=is_admin
            )
            matched_jobs = []
            for job in jobs:
                meta = job.get("metadata", {})
                title = (meta.get("title") or "").lower()
                skills_raw = meta.get("required_skills", [])
                if isinstance(skills_raw, str):
                    skills_str = skills_raw.lower()
                else:
                    skills_str = " ".join(skills_raw).lower()
                searchable = f"{title} {skills_str} {(meta.get('responsibilities') or '')}".lower()
                if keyword in searchable:
                    matched_jobs.append(job)

            if not matched_jobs:
                if user_lang == "vi":
                    return {
                        "status": "info",
                        "message": f"🔍 Không tìm thấy vị trí nào với từ khóa **'{keyword}'**.\n\n💡 Thử từ khóa khác hoặc gõ 'danh sách' để xem tất cả.",
                    }
                else:
                    return {
                        "status": "info",
                        "message": f"🔍 No positions found for **'{keyword}'**.\n\n💡 Try another keyword or type 'list' to see all.",
                    }

            if user_lang == "vi":
                header = f"🔍 **Tìm thấy {len(matched_jobs)} vị trí** với từ khóa '{keyword}':\n\n"
            else:
                header = (
                    f"🔍 **Found {len(matched_jobs)} positions** for '{keyword}':\n\n"
                )

            lines = []
            listed_jobs = []
            for i, job in enumerate(matched_jobs[:10], 1):
                meta = job.get("metadata", {})
                title = meta.get("title", "Untitled")
                job_id = job.get("id") or job.get("job_id", "")
                exp = meta.get("experience_years", "N/A")
                skills = meta.get("required_skills", [])
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",")[:4]]
                elif isinstance(skills, list):
                    skills = skills[:4]
                job_link = f"#job-detail/{job_id}"
                listed_jobs.append({"index": i, "job_id": job_id, "title": title})

                if user_lang == "vi":
                    lines.append(
                        f"**{i}. [{title}]({job_link})**\n   ⏱️ {exp} | 🛠️ {', '.join(skills) if skills else '—'}"
                    )
                else:
                    lines.append(
                        f"**{i}. [{title}]({job_link})**\n   ⏱️ {exp} | 🛠️ {', '.join(skills) if skills else '—'}"
                    )

            context_manager.store_context(
                session_id, "listed_jobs", listed_jobs, owner_id=owner_id
            )
            if user_lang == "vi":
                footer = "\n\n💡 *Gửi số thứ tự để chọn vị trí.*"
            else:
                footer = "\n\n💡 *Send a number to select a position.*"
            return {"status": "success", "message": header + "\n".join(lines) + footer}

        if action == "select_job":
            listed_jobs = (
                context_manager.get_context(
                    session_id, "listed_jobs", owner_id=owner_id
                )
                or []
            )
            job_number = intent.get("job_number")
            job_name = intent.get("job_name", "").strip()
            selected = None

            # Try by number first
            if job_number and listed_jobs:
                for j in listed_jobs:
                    if j.get("index") == job_number:
                        selected = j
                        break

            # Try by name match
            if not selected and job_name and listed_jobs:
                name_lower = job_name.lower()
                for j in listed_jobs:
                    if (
                        name_lower in j.get("title", "").lower()
                        or j.get("title", "").lower() in name_lower
                    ):
                        selected = j
                        break

            if not selected:
                if user_lang == "vi":
                    available = (
                        ", ".join([f"{j['index']}. {j['title']}" for j in listed_jobs])
                        if listed_jobs
                        else "Chưa có"
                    )
                    return {
                        "status": "error",
                        "message": f"Không tìm thấy vị trí phù hợp. Các vị trí hiện có:\n{available}",
                    }
                else:
                    available = (
                        ", ".join([f"{j['index']}. {j['title']}" for j in listed_jobs])
                        if listed_jobs
                        else "None"
                    )
                    return {
                        "status": "error",
                        "message": f"Could not find matching position. Available:\n{available}",
                    }

            # Store selected job in context
            job_id = selected["job_id"]
            job_title = selected["title"]
            context_manager.store_context(
                session_id, "job_id", job_id, owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "workflow_stage", "job_ready", owner_id=owner_id
            )

            if user_lang == "vi":
                return {
                    "status": "success",
                    "message": f"✅ Đã chọn vị trí **{job_title}**.\n\n💡 Gõ 'sàng lọc' để tìm ứng viên phù hợp, hoặc 'câu hỏi phỏng vấn' để tạo câu hỏi.",
                }
            else:
                return {
                    "status": "success",
                    "message": f"✅ Selected position **{job_title}**.\n\n💡 Type 'screen' to find matching candidates, or 'interview questions' to generate questions.",
                }

        if action == "list_cvs":
            cvs = cv_processor.list_all_cvs(
                user_id=user_id, include_public=True, is_admin=is_admin
            )
            if not cvs:
                if user_lang == "vi":
                    return {
                        "status": "info",
                        "message": "📄 Chưa có CV nào trong hệ thống. Bạn có thể tải CV lên qua trang 'Upload CVs'!",
                    }
                else:
                    return {
                        "status": "info",
                        "message": "📄 No CVs in the system yet. You can upload CVs via the 'Upload CVs' page!",
                    }

            if user_lang == "vi":
                header = f"� **Có {len(cvs)} ứng viên trong hệ thống:**\n\n"
            else:
                header = f"👥 **{len(cvs)} candidates in the system:**\n\n"

            lines = []
            for i, cv in enumerate(cvs, 1):
                # Get data from metadata or direct fields
                meta = cv.get("metadata", {})
                # Mask PII for CVs not owned by the viewer
                cv_owner = meta.get("owner_user_id", "")
                is_owner = user_id and cv_owner == user_id
                if not is_admin and not is_owner:
                    # Local application imports
                    from backend.pii_masking import mask_cv_metadata

                    meta = mask_cv_metadata(meta, is_owner=False)
                name = meta.get("name") or cv.get("name", "Unknown")
                cv_id = cv.get("id") or cv.get("cv_id", "")
                email = meta.get("email") or cv.get("email", "")

                skills = meta.get("skills") or cv.get("skills", [])
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",")[:4]]
                elif isinstance(skills, list):
                    skills = skills[:4]

                exp = meta.get("experience_years") or cv.get("experience_years", "")

                # Format nicely
                line = f"**{i}. {name}**"
                if email:
                    line += f" 📧 {email}"
                line += "\n"
                if exp:
                    line += (
                        f"   ⏱️ {exp} năm kinh nghiệm\n"
                        if user_lang == "vi"
                        else f"   ⏱️ {exp} years exp\n"
                    )
                line += f"   🛠️ {', '.join(skills) if skills else 'N/A'}"
                if cv_id:
                    line += f"\n   🔑 ID: `{cv_id[:12]}...`"
                lines.append(line)

            if user_lang == "vi":
                footer = "\n\n💡 *Gửi 'match' để so khớp ứng viên với JD!*"
            else:
                footer = "\n\n💡 *Type 'match' to compare candidates with a JD!*"

            return {
                "status": "success",
                "message": header + "\n".join(lines) + footer,
            }

        if action == "view_job_detail":
            job_identifier = intent.get("job_identifier", "").strip()
            job = _find_job_by_identifier(
                job_identifier, job_processor, user_id=user_id, is_admin=is_admin
            )

            if not job:
                if user_lang == "vi":
                    return {
                        "status": "error",
                        "message": f"❌ Không tìm thấy JD với từ khóa '{job_identifier}'.\n\nGõ 'danh sách JD' để xem các vị trí hiện có.",
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"❌ No JD found matching '{job_identifier}'.\n\nType 'list jobs' to see available positions.",
                    }

            return {
                "status": "success",
                "message": _format_job_detail(job, user_lang),
            }

        if action == "view_cv_detail":
            cv_identifier = intent.get("cv_identifier", "").strip()
            cv = _find_cv_by_identifier(
                cv_identifier, cv_processor, user_id=user_id, is_admin=is_admin
            )

            if not cv:
                if user_lang == "vi":
                    return {
                        "status": "error",
                        "message": f"❌ Không tìm thấy CV với từ khóa '{cv_identifier}'.\n\nGõ 'danh sách CV' để xem các ứng viên hiện có.",
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"❌ No CV found matching '{cv_identifier}'.\n\nType 'list CVs' to see available candidates.",
                    }

            return {
                "status": "success",
                "message": _format_cv_detail(
                    cv, user_lang, viewer_user_id=user_id, is_admin=is_admin
                ),
            }

        if action == "provide_job_description":
            job_text = (intent.get("job_text") or "").strip()
            if not job_text or len(job_text.split()) < 20:
                return {
                    "status": "error",
                    "message": _get_message("jd_too_short", user_lang),
                }
            job_id = str(uuid.uuid4())
            job_data = job_processor.process_job_description(job_id, job_text)
            context_manager.store_context(
                session_id, "job_id", job_id, owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "job_text", job_text, owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "job_data", job_data, owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "workflow_stage", "job_ready", owner_id=owner_id
            )

            required = job_data.get("required_skills", [])
            preferred = job_data.get("preferred_skills", [])

            if user_lang == "vi":
                response = (
                    "✅ Đã phân tích mô tả công việc.\n"
                    f"• Vị trí: {job_data.get('title', 'Chưa xác định')}\n"
                    f"• Kinh nghiệm yêu cầu: {job_data.get('experience_years', 'N/A')} năm\n"
                    f"• Kỹ năng bắt buộc: {', '.join(required[:5]) or 'Chưa xác định'}\n"
                    f"• Kỹ năng ưu tiên: {', '.join(preferred[:3]) or 'Chưa xác định'}\n\n"
                    "Bạn có thể yêu cầu 'tìm ứng viên' hoặc 'sàng lọc CV' để tôi tìm ứng viên phù hợp."
                )
            else:
                response = (
                    "✅ Job description analyzed.\n"
                    f"• Position: {job_data.get('title', 'Unknown')}\n"
                    f"• Required experience: {job_data.get('experience_years', 'N/A')} years\n"
                    f"• Key required skills: {', '.join(required[:5]) or 'Not specified'}\n"
                    f"• Preferred skills: {', '.join(preferred[:3]) or 'Not specified'}\n\n"
                    "You can request 'match candidates' or 'screen CVs' to find suitable candidates."
                )
            return {"status": "success", "message": response}

        if action == "provide_cv_paths":
            # P1-AUDIT P1-B: Reject raw path processing. Users must upload
            # CVs through the proper /upload-cv endpoint instead.
            _P1B_MSG = {
                "vi": (
                    "Vui lòng tải CV lên qua trang Upload CV hoặc endpoint "
                    "/api/chat/upload-cv. Đường dẫn file trực tiếp không được "
                    "hỗ trợ vì lý do bảo mật."
                ),
                "en": (
                    "Please upload your CV via the Upload CV page or endpoint "
                    "/api/chat/upload-cv. Direct file path input is not "
                    "supported for security reasons."
                ),
            }
            return {
                "status": "error",
                "message": _P1B_MSG.get(user_lang, _P1B_MSG["en"]),
            }

        if action == "run_matching":
            job_id = context_manager.get_context(
                session_id, "job_id", owner_id=owner_id
            )
            if not job_id:
                # No job selected — list available jobs for quick selection
                jobs = job_processor.list_all_jobs(
                    user_id=user_id, include_public=True, is_admin=is_admin
                )
                if jobs:
                    listed = []
                    for i, job in enumerate(jobs, 1):
                        meta = job.get("metadata", {})
                        title = meta.get("title", "Untitled")
                        jid = job.get("id") or job.get("job_id", "")
                        listed.append({"index": i, "job_id": jid, "title": title})
                    context_manager.store_context(
                        session_id, "listed_jobs", listed, owner_id=owner_id
                    )
                    job_list = "\n".join(
                        [f"  **{j['index']}.** {j['title']}" for j in listed]
                    )
                    if user_lang == "vi":
                        return {
                            "status": "info",
                            "message": f"⚠️ Bạn chưa chọn vị trí tuyển dụng. Hãy chọn một vị trí:\n\n{job_list}\n\n💡 Gõ số thứ tự (VD: '1') hoặc tên vị trí để chọn.",
                        }
                    else:
                        return {
                            "status": "info",
                            "message": f"⚠️ No position selected. Please choose one:\n\n{job_list}\n\n💡 Type a number (e.g. '1') or position name to select.",
                        }
                return {
                    "status": "error",
                    "message": _get_message("no_job_desc", user_lang),
                }

            # Check if we have CVs in context from chat upload
            cvs_in_context = (
                context_manager.get_context(session_id, "cvs", owner_id=owner_id) or []
            )

            # If no CVs in session context, check if there are CVs in the
            # database
            if not cvs_in_context:
                try:
                    all_cvs = cv_processor.list_all_cvs(
                        user_id=user_id,
                        include_public=is_admin,
                        is_admin=is_admin,
                    )
                    if all_cvs and len(all_cvs) > 0:
                        # Use CVs from database
                        context_manager.store_context(
                            session_id, "cvs", all_cvs, owner_id=owner_id
                        )
                        context_manager.store_context(
                            session_id, "cv_count", len(all_cvs), owner_id=owner_id
                        )
                        message = _get_message(
                            "found_cvs", user_lang, count=len(all_cvs)
                        )
                    else:
                        return {
                            "status": "error",
                            "message": _get_message("no_cvs", user_lang),
                        }
                except Exception as e:
                    logger.error(
                        "Error checking database CVs", error=str(e), exc_info=True
                    )
                    return {
                        "status": "error",
                        "message": "Error checking database CVs",
                    }
            else:
                message = ""

            top_k = intent.get("top_k") or 5
            try:
                top_k = int(top_k)
            except (TypeError, ValueError):
                top_k = 5

            # P1-AUDIT P1-C: Build Viewer with actual admin flag and forward to engine
            viewer = Viewer(
                user_id=user_id,
                is_admin=is_admin,
            )

            # Run matching
            matches = matching_engine.match_candidates(
                job_id,
                viewer=viewer,
                top_k=top_k,
                lang=user_lang,
                owner_only=not is_admin,
            )

            if not matches:
                return {
                    "status": "error",
                    "message": _get_message("no_matches", user_lang),
                }

            context_manager.store_context(
                session_id, "matches", matches, owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "workflow_stage", "matched", owner_id=owner_id
            )
            api_base = os.getenv("API_URL", "").rstrip("/")
            summary = _format_matches_summary(
                matches,
                user_lang,
                api_base=api_base,
                viewer_user_id=user_id,
                is_admin=is_admin,
            )
            return {
                "status": "success",
                "message": message + summary,
            }

        if action == "generate_questions":
            job_id = context_manager.get_context(
                session_id, "job_id", owner_id=owner_id
            )
            matches = (
                context_manager.get_context(session_id, "matches", owner_id=owner_id)
                or []
            )
            if not job_id or not matches:
                return {
                    "status": "error",
                    "message": _get_message("need_job_and_matches", user_lang),
                }
            candidate = _select_candidate_from_matches(
                matches, intent.get("candidate_name")
            )
            if not candidate:
                names = (
                    ", ".join([m.get("name", "Unknown") for m in matches])
                    or "(no data)"
                )
                return {
                    "status": "error",
                    "message": f"Could not identify candidate. You can choose from: {names}.",
                }
            cv_id = candidate.get("cv_id")
            if not cv_id:
                return {
                    "status": "error",
                    "message": _get_message("cv_id_not_found", user_lang),
                }

            # Extract matching context (strengths + gaps) for better question
            # generation
            matching_context = {
                "strengths": candidate.get("strengths", []),
                "gaps": candidate.get("gaps", []),
            }

            questions = question_generator.generate_questions(
                job_id, cv_id, matching_context
            )
            existing = (
                context_manager.get_context(session_id, "questions", owner_id=owner_id)
                or {}
            )
            existing[cv_id] = questions
            context_manager.store_context(
                session_id, "questions", existing, owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "workflow_stage", "questions_ready", owner_id=owner_id
            )
            type_labels = {
                "Technical": "Kỹ thuật",
                "Behavioral": "Hành vi",
                "Situational": "Tình huống",
                "General": "Chung",
            }
            q_text = "\n".join(
                [
                    f"• ({type_labels.get(q.get('type'), q.get('type', 'Chung')) if user_lang == 'vi' else q.get('type', 'General')}) {q.get('question')}"
                    for q in questions[:5]
                ]
            )
            candidate_name = candidate.get(
                "name", "ứng viên" if user_lang == "vi" else "candidate"
            )
            visible_count = min(len(questions), 5)
            if len(questions) > visible_count:
                section_label = (
                    f"Hiển thị {visible_count} câu tiêu biểu trong {len(questions)} câu đã tạo:"
                    if user_lang == "vi"
                    else f"Showing {visible_count} representative questions out of {len(questions)}:"
                )
            else:
                section_label = "Chủ đề chính:" if user_lang == "vi" else "Key topics:"
            message = (
                f"💬 Đã tạo {len(questions)} câu hỏi cho {candidate_name}\n"
                f"{section_label}\n{q_text}"
                if user_lang == "vi"
                else f"💬 Generated {len(questions)} questions for {candidate_name}\n"
                f"{section_label}\n{q_text}"
            )
            return {
                "status": "success",
                "message": message,
            }

        if action == "run_full_workflow":
            job_text = intent.get("job_text") or context_manager.get_context(
                session_id, "job_text", owner_id=owner_id
            )
            if not job_text:
                return {
                    "status": "error",
                    "message": _get_message("need_job_for_workflow", user_lang),
                }
            cv_items = intent.get("cv_paths") or [
                item.get("file_path")
                for item in (
                    context_manager.get_context(session_id, "cvs", owner_id=owner_id)
                    or []
                )
            ]
            resolved_files = []
            for path in cv_items:
                resolved = _resolve_cv_path(path) if path else None
                if resolved:
                    resolved_files.append(resolved)
            if not resolved_files:
                return {
                    "status": "error",
                    "message": _get_message("no_cvs_for_workflow", user_lang),
                }

            result = recruitment_agent.quick_screen(
                job_text=job_text,
                cv_files=resolved_files,
                viewer_user_id=owner_id,
                viewer_is_admin=is_admin,
            )
            context_manager.store_context(
                session_id, "job_id", result.get("job_id"), owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "job_data", result.get("job_data"), owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "matches", result.get("candidates", []), owner_id=owner_id
            )
            context_manager.store_context(
                session_id, "questions", result.get("questions", {}), owner_id=owner_id
            )
            context_manager.store_context(
                session_id,
                "workflow_stage",
                result.get("status", "completed"),
                owner_id=owner_id,
            )
            context_manager.store_context(
                session_id,
                "cv_count",
                len(result.get("candidates", [])),
                owner_id=owner_id,
            )
            message = (
                "🤖 Completed automatic screening workflow!\n"
                f"• Top candidate: {result.get('candidates', [{}])[0].get('name', 'N/A') if result.get('candidates') else 'N/A'}\n"
                f"• Total candidates evaluated: {len(result.get('candidates', []))}\n"
                "You can ask 'show matches' or 'generate questions' to see details."
            )
            return {
                "status": "success",
                "message": message,
            }

        if action == "workflow_status":
            return {
                "status": "success",
                "message": _build_status_summary(
                    session_id, context_manager, owner_id=owner_id
                ),
            }

    except Exception as exc:
        logger.error("Error processing request", error=str(exc), exc_info=True)
        return {
            "status": "error",
            "message": "Error processing request",
        }

    return {
        "status": "info",
        "message": _get_message("conversation_mode", user_lang),
    }


def _select_candidate_from_matches(
    matches: List[Dict[str, Any]], desired_name: Optional[str]
) -> Optional[Dict[str, Any]]:
    if not matches:
        return None
    if not desired_name:
        return matches[0]
    desired_lower = desired_name.lower()
    for match in matches:
        if desired_lower in match.get("name", "").lower():
            return match
    return None


def _format_matches_summary(
    matches: List[Dict[str, Any]],
    lang: str = "en",
    api_base: str = "",
    viewer_user_id: str = None,
    is_admin: bool = False,
) -> str:
    if not matches:
        return ""
    # Local application imports
    from backend.pii_masking import mask_name

    if lang == "vi":
        lines = [f"🎯 **Kết quả sàng lọc ({len(matches)} ứng viên):**\n"]
        lines.append("| # | Ứng viên | Phù hợp | Điểm mạnh | Điểm yếu | CV |")
        lines.append("|---|----------|---------|-----------|-----------|-----|")
        for idx, match in enumerate(matches, start=1):
            name = match.get("name", "Chưa xác định")
            cv_owner = match.get("metadata", {}).get("owner_user_id", "")
            is_owner = viewer_user_id and cv_owner == viewer_user_id
            if not is_admin and not is_owner:
                name = mask_name(name)
            score = match.get("fit_score", 0)
            strengths = match.get("strengths", [])[:2]
            gaps = match.get("gaps", [])[:2]
            strength_text = "; ".join(strengths) if strengths else "—"
            gap_text = "; ".join(gaps) if gaps else "—"

            file_path = match.get("metadata", {}).get("file_path", "")
            cv_cell = "—"
            if file_path and (is_admin or is_owner):
                clean_path = file_path.lstrip("./")
                cv_url = (
                    f"{api_base}/uploads/{clean_path}"
                    if api_base
                    else f"/uploads/{clean_path}"
                )
                cv_cell = f"[Xem]({cv_url})"

            lines.append(
                f"| {idx} | **{name}** | **{score}%** | {strength_text} | {gap_text} | {cv_cell} |"
            )

        lines.append(
            "\n💡 *Gõ 'tạo câu hỏi cho <tên ứng viên>' để soạn câu hỏi phỏng vấn.*"
        )
    else:
        lines = [f"🎯 **Screening results ({len(matches)} candidates):**\n"]
        lines.append("| # | Candidate | Fit | Strengths | Gaps | CV |")
        lines.append("|---|-----------|-----|-----------|------|-----|")
        for idx, match in enumerate(matches, start=1):
            name = match.get("name", "Unknown")
            cv_owner = match.get("metadata", {}).get("owner_user_id", "")
            is_owner = viewer_user_id and cv_owner == viewer_user_id
            if not is_admin and not is_owner:
                name = mask_name(name)
            score = match.get("fit_score", 0)
            strengths = match.get("strengths", [])[:2]
            gaps = match.get("gaps", [])[:2]
            strength_text = "; ".join(strengths) if strengths else "—"
            gap_text = "; ".join(gaps) if gaps else "—"

            file_path = match.get("metadata", {}).get("file_path", "")
            cv_cell = "—"
            if file_path and (is_admin or is_owner):
                clean_path = file_path.lstrip("./")
                cv_url = (
                    f"{api_base}/uploads/{clean_path}"
                    if api_base
                    else f"/uploads/{clean_path}"
                )
                cv_cell = f"[View]({cv_url})"

            lines.append(
                f"| {idx} | **{name}** | **{score}%** | {strength_text} | {gap_text} | {cv_cell} |"
            )

        lines.append(
            "\n💡 *Type 'generate questions for <candidate name>' to get interview questions.*"
        )

    return "\n".join(lines)


def _build_status_summary(
    session_id: str, context_manager: ContextManager, owner_id: Optional[str] = None
) -> str:
    ctx = context_manager.get_all_context(session_id, owner_id=owner_id)
    lines = ["📊 Current status:"]
    job = ctx.get("job_data")
    if job:
        lines.append(
            f"• Job: {job.get('title', 'N/A')} (requires {len(job.get('required_skills', []))} skills)"
        )
    else:
        lines.append("• No job analyzed yet")
    cv_count = ctx.get("cv_count", 0)
    lines.append(f"• CVs processed: {cv_count}")
    matches = ctx.get("matches") or []
    if matches:
        lines.append(f"• Candidates scored: {len(matches)}")
    questions = ctx.get("questions") or {}
    if questions:
        lines.append(f"• Questions prepared for {len(questions.keys())} candidate(s)")
    stage = ctx.get("workflow_stage")
    if stage:
        lines.append(f"• Current stage: {stage}")
    lines.append(
        "Continue by running matching, generating questions, or starting a new workflow."
    )
    return "\n".join(lines)


def _generate_suggestions(
    session_id: str, context_manager: ContextManager, owner_id: Optional[str] = None
) -> List[str]:
    """Generate contextual suggestions"""
    all_context = context_manager.get_all_context(session_id, owner_id=owner_id)
    suggestions = []

    if not all_context.get("job_data"):
        suggestions.append("📋 Upload a job description")

    if all_context.get("job_data") and not all_context.get("cv_count"):
        suggestions.append("📄 Upload CVs to screen")

    if all_context.get("job_data") and all_context.get("cv_count"):
        suggestions.append("🎯 Match candidates to job")
        suggestions.append("🤖 Run full AI workflow")

    if all_context.get("matches"):
        suggestions.append("💬 Generate interview questions")
        suggestions.append("📊 Show workflow status")

    if not suggestions:
        suggestions = [
            "🤖 Run full AI Agent workflow",
            "📊 View recruitment summary",
            "🔄 Start new screening",
        ]

    # Keep suggestions concise for the UI
    return suggestions[:3]
