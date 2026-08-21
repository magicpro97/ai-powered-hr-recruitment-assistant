"""
AI Agent for HR Recruitment using LangGraph
Orchestrates the entire recruitment workflow autonomously.

This module implements a multi-agent system using LangGraph for state machine
orchestration of recruitment tasks including job analysis, CV screening,
candidate matching, and interview question generation.

Academic References:
- Wu et al. (2023). "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent
  Conversation". arXiv:2308.08155
- Chase (2022). "LangChain: Building applications with LLMs through composability".
  https://github.com/langchain-ai/langchain
- LangGraph Documentation (2024). "Building stateful, multi-actor applications
  with LLMs". https://langchain-ai.github.io/langgraph/
- Yao et al. (2022). "ReAct: Synergizing Reasoning and Acting in Language Models".
  ICLR 2023. arXiv:2210.03629
- Shinn et al. (2023). "Reflexion: Language Agents with Verbal Reinforcement
  Learning". NeurIPS 2023. arXiv:2303.11366
"""

# Standard library imports
# Logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, TypedDict

# Third-party imports
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from ..config import Config
from ..database.vector_store import VectorStore
from ..processors.cv_processor import CVProcessor
from ..processors.job_processor import JobProcessor
from ..processors.matching_engine import MatchingEngine
from ..processors.question_generator import QuestionGenerator
from .memory import ContextManager, ConversationMemory

# Ensure project root is in path for backend imports
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# Local application imports
from backend.logging_config import get_logger, log_llm_call  # noqa: E402

logger = get_logger(__name__)


class RecruitmentState(TypedDict):
    """State for recruitment agent workflow"""

    # Input
    task: str  # "analyze_job", "screen_cvs", "match_candidates", "generate_questions", "full_workflow"
    job_text: Optional[str]
    job_id: Optional[str]
    cv_files: Optional[List[str]]
    cv_ids: Optional[List[str]]
    top_k: Optional[int]

    # Viewer for resource visibility (threaded from caller)
    viewer_user_id: Optional[str]
    viewer_is_admin: Optional[bool]

    # Agent decisions
    next_action: Optional[str]
    analysis: Optional[str]

    # Processed data
    job_data: Optional[Dict[str, Any]]
    cv_data: Optional[List[Dict[str, Any]]]
    matches: Optional[List[Dict[str, Any]]]
    questions: Optional[Dict[str, List[Dict[str, Any]]]]

    # Workflow control
    completed_steps: List[str]
    errors: List[str]
    status: str  # "pending", "processing", "completed", "failed"


_SYSTEM_OWNER = "_system:recruitment_agent"


class RecruitmentAgent:
    """
    Autonomous AI Agent for HR Recruitment
    Uses LangGraph to orchestrate multi-step recruitment workflows
    Maintains conversation context and memory
    """

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.llm = ChatOpenAI(model=Config.OPENAI_MODEL, temperature=0.7)

        self.job_processor = JobProcessor(vector_store)
        self.cv_processor = CVProcessor(vector_store)
        self.matching_engine = MatchingEngine(vector_store)
        self.question_generator = QuestionGenerator(vector_store)

        # Initialize memory and context
        self.memory = ConversationMemory()
        self.context_manager = ContextManager(self.memory)

        # Build the agent graph
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build LangGraph workflow"""
        workflow = StateGraph(RecruitmentState)

        # Add nodes
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("analyze_job", self._analyze_job_node)
        workflow.add_node("screen_cvs", self._screen_cvs_node)
        workflow.add_node("match_candidates", self._match_candidates_node)
        workflow.add_node("generate_questions", self._generate_questions_node)
        workflow.add_node("summarize", self._summarize_node)

        # Set entry point
        workflow.set_entry_point("planner")

        # Add conditional edges from planner
        workflow.add_conditional_edges(
            "planner",
            self._route_next_action,
            {
                "analyze_job": "analyze_job",
                "screen_cvs": "screen_cvs",
                "match_candidates": "match_candidates",
                "generate_questions": "generate_questions",
                "summarize": "summarize",
                "end": END,
            },
        )

        # Add edges back to planner after each action
        workflow.add_edge("analyze_job", "planner")
        workflow.add_edge("screen_cvs", "planner")
        workflow.add_edge("match_candidates", "planner")
        workflow.add_edge("generate_questions", "planner")
        workflow.add_edge("summarize", END)

        return workflow.compile()

    def _planner_node(self, state: RecruitmentState) -> RecruitmentState:
        """
        Planning node - decides next action based on current state and conversation history
        """
        logger.info("PLANNER: Analyzing state and deciding next action")
        try:
            completed = state.get("completed_steps", [])
            task = state.get("task", "")
            session_id = state.get("job_id") or "default"

            # Get conversation context
            context_prompt = self.context_manager.build_context_prompt(
                session_id, owner_id=_SYSTEM_OWNER
            )

            # Build context for LLM
            system_prompt = "You are a workflow planning AI. Be concise and decisive. Consider conversation history."
            user_prompt = f"""
{context_prompt}

You are an AI recruitment agent planner. Analyze the current workflow state and decide the next action.

Task requested: {task}
Completed steps: {completed}

Available actions:
1. analyze_job - Extract requirements from job description
2. screen_cvs - Process and analyze CVs
3. match_candidates - Match CVs to job requirements
4. generate_questions - Create interview questions
5. summarize - Provide final summary
6. end - Complete workflow

Current state:
- Job data: {"✅" if state.get("job_data") else "❌"}
- CVs processed: {"✅" if state.get("cv_data") else "❌"}
- Matches found: {"✅" if state.get("matches") else "❌"}
- Questions generated: {"✅" if state.get("questions") else "❌"}

Rules:
- Must analyze job before screening CVs
- Must screen CVs before matching
- Must match before generating questions
- Always summarize at the end

What should be the next action? Reply with just the action name.
"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            # Add to memory
            self.memory.add_message(
                session_id,
                "system",
                "Planning next action",
                {"stage": "planning"},
                owner_id=_SYSTEM_OWNER,
            )

            start_time = time.time()
            response = self.llm.invoke(messages)
            duration = time.time() - start_time
            next_action = str(response.content).strip().lower()

            # Count actual tokens
            # Local application imports
            from backend.token_utils import count_tokens

            prompt_tokens = count_tokens(
                system_prompt + user_prompt, Config.OPENAI_MODEL
            )
            completion_tokens = count_tokens(str(response.content), Config.OPENAI_MODEL)

            # Log LLM call
            log_llm_call(
                logger=logger,
                operation="agent_planning",
                model=Config.OPENAI_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=duration,
                session_id=session_id,
                next_action=next_action,
            )

            # Track decision
            self.context_manager.track_decision(
                session_id,
                next_action,
                f"Based on completed: {completed}, state: {task}",
                owner_id=_SYSTEM_OWNER,
            )

            # Add response to memory
            self.memory.add_message(
                session_id,
                "assistant",
                f"Next action: {next_action}",
                {"stage": "planning"},
                owner_id=_SYSTEM_OWNER,
            )

            # Validate action
            valid_actions = [
                "analyze_job",
                "screen_cvs",
                "match_candidates",
                "generate_questions",
                "summarize",
                "end",
            ]
            if next_action not in valid_actions:
                next_action = "end"

            logger.info("PLANNER: Next action decided", next_action=next_action)

            state["next_action"] = next_action
            state["analysis"] = f"Planning complete. Next: {next_action}"

        except Exception as e:
            logger.error("PLANNER failed", error=str(e))
            state["errors"].append("Planning failed")
            state["next_action"] = "end"  # Fail-safe: end workflow on error

        return state

    def _route_next_action(self, state: RecruitmentState) -> str:
        """Route to next node based on planner decision"""
        return state.get("next_action") or "end"

    def _analyze_job_node(self, state: RecruitmentState) -> RecruitmentState:
        """Process job description"""
        logger.info("ANALYZE_JOB: Processing job description")
        try:
            job_text = state.get("job_text")
            job_id = state.get("job_id")

            if not job_text or not job_id:
                state["errors"].append("Missing job_text or job_id")
                return state

            # Preserve caller ownership; only trusted internal states that omit
            # viewer_user_id entirely create system-owned resources.
            if "viewer_user_id" in state and state["viewer_user_id"] is None:
                state["errors"].append("Missing resource owner")
                return state

            owner_id = state.get("viewer_user_id", _SYSTEM_OWNER)
            assert owner_id is not None
            job_data = self.job_processor.process_job_description(
                job_id, job_text, user_id=owner_id
            )

            state["job_data"] = job_data
            state["completed_steps"].append("analyze_job")

            logger.info(
                "ANALYZE_JOB completed",
                required_skills=len(job_data.get("required_skills", [])),
            )

        except Exception as e:
            logger.error("ANALYZE_JOB failed", error=str(e))
            state["errors"].append("Job analysis failed")

        return state

    def _screen_cvs_node(self, state: RecruitmentState) -> RecruitmentState:
        """Process CVs"""
        logger.info("SCREEN_CVS: Processing CVs")
        try:
            job_id = state.get("job_id")
            cv_files = state.get("cv_files") or []

            if not job_id:
                state["errors"].append("Missing job_id for CV screening")
                return state

            if "viewer_user_id" in state and state["viewer_user_id"] is None:
                state["errors"].append("Missing resource owner")
                return state

            owner_id = state.get("viewer_user_id", _SYSTEM_OWNER)
            assert owner_id is not None
            cv_data = []
            cv_ids = []

            for cv_file in cv_files:
                # Standard library imports
                import uuid

                cv_id = str(uuid.uuid4())
                try:
                    # Process CV (cv_processor handles PDF extraction internally)
                    processed_cv = self.cv_processor.process_cv(
                        cv_id, cv_file, user_id=owner_id
                    )
                    cv_data.append(processed_cv)
                    cv_ids.append(cv_id)

                    logger.info(
                        "CV processed successfully",
                        cv_id=cv_id,
                        name=processed_cv.get("name", "Unknown"),
                    )

                except Exception as e:
                    logger.warning(
                        "Failed to process CV", cv_file=str(cv_file), error=str(e)
                    )
                    state["errors"].append(f"CV processing failed for {cv_id}")

            state["cv_data"] = cv_data
            state["cv_ids"] = cv_ids
            state["completed_steps"].append("screen_cvs")

            logger.info("SCREEN_CVS completed", cv_count=len(cv_data))

        except Exception as e:
            logger.error("SCREEN_CVS failed", error=str(e))
            state["errors"].append("CV screening failed")

        return state

    def _match_candidates_node(self, state: RecruitmentState) -> RecruitmentState:
        """Match candidates to job"""
        logger.info("MATCH_CANDIDATES: Finding best matches")
        try:
            job_id = state.get("job_id")
            top_k = state.get("top_k", 10)

            if not job_id:
                state["errors"].append("Missing job_id for matching")
                return state

            # Explicit None is an anonymous viewer. Only trusted internal callers
            # that omit viewer fields entirely receive the system identity.
            # Local application imports
            from backend.access_control import Viewer

            viewer_user_id = state.get("viewer_user_id", _SYSTEM_OWNER)
            viewer_is_admin = bool(state.get("viewer_is_admin", False))
            viewer = Viewer(user_id=viewer_user_id, is_admin=viewer_is_admin)

            matches = self.matching_engine.match_candidates(
                job_id, viewer=viewer, top_k=top_k or 10
            )

            state["matches"] = matches
            state["completed_steps"].append("match_candidates")

            logger.info("MATCH_CANDIDATES completed", match_count=len(matches))
            for i, match in enumerate(matches[:3], 1):
                logger.debug(
                    "Top match",
                    rank=i,
                    name=match.get("name", "Unknown"),
                    fit_score=match.get("fit_score", 0),
                )

        except Exception as e:
            logger.error("MATCH_CANDIDATES failed", error=str(e))
            state["errors"].append("Matching failed")

        return state

    def _generate_questions_node(self, state: RecruitmentState) -> RecruitmentState:
        """Generate interview questions"""
        logger.info("GENERATE_QUESTIONS: Creating interview questions")
        try:
            job_id = state.get("job_id")
            matches = state.get("matches", [])

            if not job_id or not matches:
                state["errors"].append("Missing job_id or matches for questions")
                return state

            questions = {}

            # Generate for top 3 candidates
            for match in matches[:3]:
                cv_id = match.get("cv_id")
                if cv_id:
                    try:
                        qs = self.question_generator.generate_questions(job_id, cv_id)
                        questions[cv_id] = qs
                        logger.info(
                            "Questions generated",
                            cv_id=cv_id,
                            count=len(qs),
                            name=match.get("name", "Unknown"),
                        )
                    except Exception as e:
                        logger.warning(
                            "Question generation failed for candidate",
                            name=match.get("name", "Unknown"),
                            error=str(e),
                        )

            state["questions"] = questions
            state["completed_steps"].append("generate_questions")

            logger.info("GENERATE_QUESTIONS completed", candidate_count=len(questions))

        except Exception as e:
            logger.error("GENERATE_QUESTIONS failed", error=str(e))
            state["errors"].append("Question generation failed")

        return state

    def _summarize_node(self, state: RecruitmentState) -> RecruitmentState:
        """Generate final summary"""
        logger.info("SUMMARIZE: Creating final report")
        try:
            # Build summary with LLM
            job_data = state.get("job_data") or {}
            matches = state.get("matches") or []
            state.get("questions") or {}

            summary_prompt = f"""
Generate a concise recruitment summary:

Job: {job_data.get("title", "Unknown")}
Required Skills: {", ".join(job_data.get("required_skills", [])[:5])}

Top Candidates:
{chr(10).join([f"{i + 1}. {m.get('name', 'Unknown')} - Fit: {m.get('fit_score', 0)}%" for i, m in enumerate(matches[:5])])}

Recommendation: Provide brief hiring recommendation based on fit scores.
"""

            messages = [
                SystemMessage(
                    content="You are an HR recruitment expert. Be concise and professional."
                ),
                HumanMessage(content=summary_prompt),
            ]

            start_llm_time = time.time()
            response = self.llm.invoke(messages)
            llm_duration = time.time() - start_llm_time

            # Count actual tokens
            # Local application imports
            from backend.token_utils import count_tokens

            prompt_tokens = count_tokens(summary_prompt, Config.OPENAI_MODEL)
            completion_tokens = count_tokens(str(response.content), Config.OPENAI_MODEL)

            # Log LLM call
            log_llm_call(
                logger=logger,
                operation="agent_summarization",
                model=Config.OPENAI_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=llm_duration,
                candidate_count=len(matches),
            )

            state["analysis"] = str(response.content)
            state["status"] = "completed"
            state["completed_steps"].append("summarize")

            logger.info("SUMMARIZE: Report generated")

        except Exception as e:
            logger.error("SUMMARIZE failed", error=str(e))
            state["errors"].append("Summary failed")
            state["status"] = "failed"

        return state

    def run_workflow(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the recruitment workflow

        Args:
            initial_state: Initial state with task and input data.
                May include ``viewer_user_id`` and ``viewer_is_admin`` for
                resource visibility enforcement.
        Returns:
            Final state with results
        """
        logger.info(
            "Starting Recruitment AI Agent", task=initial_state.get("task", "unknown")
        )

        state = RecruitmentState(
            completed_steps=[], errors=[], status="processing", **initial_state
        )
        final_state = self.graph.invoke(state)
        logger.info(
            "Workflow completed",
            status=final_state.get("status", "unknown"),
            steps=len(final_state.get("completed_steps", [])),
            errors=len(final_state.get("errors", [])),
        )
        return final_state

    def quick_screen(
        self,
        job_text: str,
        cv_files: List[str],
        viewer_user_id: Optional[str] = None,
        viewer_is_admin: bool = False,
    ) -> Dict[str, Any]:
        """
        Quick screening workflow - analyze job, screen CVs, match, and generate questions

        Args:
            job_text: Job description text
            cv_files: List of CV file paths
            viewer_user_id: Viewer user ID for resource visibility
            viewer_is_admin: Whether viewer has admin privileges

        Returns:
            Complete screening results
        """
        # Standard library imports
        import uuid

        job_id = str(uuid.uuid4())

        initial_state = {
            "task": "full_workflow",
            "job_text": job_text,
            "job_id": job_id,
            "cv_files": cv_files,
            "top_k": 10,
            "viewer_user_id": viewer_user_id,
            "viewer_is_admin": viewer_is_admin,
        }

        final_state = self.run_workflow(initial_state)

        return {
            "job_id": job_id,
            "job_data": final_state.get("job_data"),
            "candidates": final_state.get("matches", []),
            "questions": final_state.get("questions", {}),
            "summary": final_state.get("analysis"),
            "status": final_state.get("status"),
        }
