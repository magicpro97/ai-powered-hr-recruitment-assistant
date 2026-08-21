"""
FastAPI Backend for HR Recruitment Assistant
"""

# Standard library imports
import asyncio
import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

# Third-party imports
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Add parent directory to path to import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Local application imports
# Local application imports (after path modification)
from backend import (  # noqa: E402
    auth_routes_v2,
    chat_routes,
    interview_routes,
)
from backend.access_control import (  # noqa: E402
    Viewer,
    require_downloadable,
    require_viewable,
    resolve_owner_id,
    safe_resolve_upload_path,
    validate_cv_id_list,
)
from backend.auth_cookies import optional_user_from_cookie  # noqa: E402
from backend.exceptions import HRAssistantException  # noqa: E402
from backend.guest_limits import get_guest_usage, require_guest_quota  # noqa: E402
from backend.guest_token import get_guest_token, guest_owner_id  # noqa: E402
from backend.limiter import limiter  # noqa: E402
from backend.logging_config import setup_logging  # noqa: E402
from backend.pii_masking import (  # noqa: E402
    mask_candidate_result,
    mask_cv_list,
    mask_cv_metadata,
)
from backend.security import (  # noqa: E402
    SecurityHeadersMiddleware,
    csrf_protected_optional_user,
    csrf_protected_user,
)
from src.agents.recruitment_agent import RecruitmentAgent  # noqa: E402
from src.config import Config  # noqa: E402
from src.database.postgres_db import get_db  # noqa: E402
from src.database.vector_store import SYSTEM_USER_ID, VectorStore  # noqa: E402
from src.processors.cv_processor import CVProcessor  # noqa: E402
from src.processors.job_processor import JobProcessor  # noqa: E402
from src.processors.matching_engine import MatchingEngine  # noqa: E402
from src.processors.question_generator import QuestionGenerator  # noqa: E402
from src.utils.file_utils import save_uploaded_file  # noqa: E402

# Initialize structured logging with production-grade config
setup_logging(level="INFO")
logger = logging.getLogger(__name__)


# Initialize FastAPI
app = FastAPI(
    title="HR Recruitment Assistant API",
    description="AI-powered recruitment screening API with conversational context",
    version="2.0.0",
)


# Exception handling middleware for custom exceptions
@app.exception_handler(HRAssistantException)
async def hr_exception_handler(request, exc: HRAssistantException):
    """Handle custom HR Assistant exceptions with structured responses"""
    logger.error(
        "hr_exception code=%s message=%s status_code=%s path=%s",
        exc.code.value,
        exc.message,
        exc.status_code,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


# Attach rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Include routers
app.include_router(chat_routes.router)
app.include_router(auth_routes_v2.router)  # Cookie-based auth v2
app.include_router(interview_routes.router)  # Interview question sets

# CORS middleware - allow localhost and configured URLs (supports subdomains)
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:8000",
]

# Add configured frontend URL
if hasattr(Config, "FRONTEND_URL") and Config.FRONTEND_URL:
    frontend_origin = Config.FRONTEND_URL.rstrip("/")
    if frontend_origin not in cors_origins:
        cors_origins.append(frontend_origin)

# Add API URL origin for cross-subdomain requests
api_url = Config.API_URL
if api_url:
    api_origin = api_url.rstrip("/")
    if api_origin not in cors_origins:
        cors_origins.append(api_origin)

logger.info(f"CORS origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-CSRF-Token",
        "X-Requested-With",
        "X-Guest-Token",
    ],
)

# Uploads directory (no longer publicly mounted — served via authenticated endpoint)
uploads_path = os.path.abspath(Config.UPLOAD_DIR)
os.makedirs(uploads_path, exist_ok=True)

# Initialize components
try:
    Config.validate()
    Config.validate_auth()  # Validate JWT_SECRET is set

    # Initialize PostgreSQL database (auth, sessions, etc.)
    get_db()
    logger.info("PostgreSQL database initialized successfully")

    # Initialize vector store and processors
    vector_store = VectorStore(Config.CHROMA_PERSIST_DIR)
    job_processor = JobProcessor(vector_store)
    cv_processor = CVProcessor(vector_store)
    matching_engine = MatchingEngine(vector_store)
    question_generator = QuestionGenerator(vector_store)
    recruitment_agent = RecruitmentAgent(vector_store)
except Exception as e:
    logger.error("Error initializing components", error=str(e))
    raise

# ============= REQUEST/RESPONSE MODELS =============

# Maximum lengths for input validation (prevent DoS and prompt injection)
MAX_JOB_TEXT_LENGTH = 50000  # ~50KB, enough for detailed job descriptions
MAX_CV_FILE_SIZE_MB = 10  # 10MB max for CV uploads
MAX_TOP_K = 100  # Maximum candidates to return


class JobRequest(BaseModel):
    job_text: str = Field(..., min_length=50, max_length=MAX_JOB_TEXT_LENGTH)
    is_public: bool = False  # Whether job should be visible to all users


class JobResponse(BaseModel):
    job_id: str
    title: str
    experience_years: Optional[str]
    education: Optional[str]
    required_skills: List[str]
    preferred_skills: List[str]
    responsibilities: List[str]
    owner_user_id: Optional[str] = None
    is_public: Optional[bool] = None


class CVResponse(BaseModel):
    cv_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    skills: List[str]
    experience_years: Optional[int] = None
    owner_user_id: Optional[str] = None
    is_public: Optional[bool] = None


class CandidateMatch(BaseModel):
    cv_id: str
    name: str
    fit_score: int
    strengths: List[str]
    gaps: List[str]
    metadata: Dict[str, Any]


class Question(BaseModel):
    type: str
    question: str
    focus_area: str


class HealthResponse(BaseModel):
    status: str
    message: str


# ============= API ENDPOINTS =============


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "HR Recruitment Assistant API is running"}


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "API is healthy"}


@app.get("/api/guest/usage")
async def get_guest_usage_endpoint(
    request: Request,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """
    Get current guest usage stats.

    Returns usage counts and remaining quota for anonymous users.
    For authenticated users, returns unlimited access indicator.
    """
    if current_user:
        return {
            "is_authenticated": True,
            "usage": None,
            "limits": None,
            "remaining": None,
            "message": "Authenticated users have unlimited access",
        }

    usage_data = await get_guest_usage(request)
    return {
        "is_authenticated": False,
        **usage_data,
    }


@app.post("/api/jobs", response_model=JobResponse)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
    job_request: JobRequest,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Process and store a job description"""
    # Enforce guest quota for anonymous users
    await require_guest_quota(request, "jobs", current_user=current_user)

    try:
        logger.debug("Job request received", text_length=len(job_request.job_text))
        job_id = str(uuid.uuid4())
        logger.debug("Generated job_id", job_id=job_id)

        # Determine owner - authenticated user > guest token > system
        if current_user:
            owner_id = current_user["id"]
        else:
            gt = get_guest_token(request)
            owner_id = guest_owner_id(gt) if gt else SYSTEM_USER_ID
        is_public = (
            job_request.is_public if current_user else False
        )  # Guest data always private (sandbox)

        job_data = job_processor.process_job_description(
            job_id, job_request.job_text, user_id=owner_id, is_public=is_public
        )
        logger.debug("Job processed", job_id=job_id)

        experience_value = job_data.get("experience_years")
        if experience_value is not None and not isinstance(experience_value, str):
            experience_value = str(experience_value)

        return JobResponse(
            job_id=job_id,
            title=job_data.get("title", "Unknown"),
            experience_years=experience_value,
            education=job_data.get("education"),
            required_skills=job_data.get("required_skills", []),
            preferred_skills=job_data.get("preferred_skills", []),
            responsibilities=job_data.get("responsibilities", []),
            owner_user_id=owner_id,
            is_public=is_public,
        )
    except Exception as e:
        logger.error("Error in create_job", error_type=type(e).__name__, error=str(e))
        # Standard library imports
        import traceback

        traceback.print_exc()
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/jobs")
async def list_jobs(
    request: Request,
    response: Response,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
    include_public: bool = Query(
        True, description="Include public jobs from other users"
    ),
):
    """List all jobs accessible to the current user"""
    try:
        if current_user:
            user_id = current_user["id"]
            is_admin = current_user.get("role") == "admin"
        else:
            # Guest: use token-based owner for sandbox isolation
            gt = get_guest_token(request)
            user_id = guest_owner_id(gt) if gt else None
            is_admin = False
            include_public = False  # Guest only sees own + system data
        jobs = job_processor.list_all_jobs(
            user_id=user_id, include_public=include_public, is_admin=is_admin
        )
        response.headers["Cache-Control"] = "private, no-cache"
        return {"jobs": jobs}
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/jobs/{job_id}")
async def get_job(
    job_id: str,
    request: Request,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Get a specific job — requires Viewer visibility."""
    try:
        job = vector_store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Build viewer from authenticated user or guest token
        user_id = current_user.get("id") if current_user else None
        is_admin = current_user.get("role") == "admin" if current_user else False
        if not user_id:
            gt = get_guest_token(request)
            user_id = guest_owner_id(gt) if gt else None
        viewer = Viewer(user_id=user_id, is_admin=is_admin)

        # Require viewable before returning metadata
        try:
            require_viewable(viewer, job.get("metadata", {}))
        except PermissionError:
            raise HTTPException(status_code=404, detail="Job not found")

        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/cvs")
@limiter.limit("10/minute")
async def upload_cv(
    request: Request,
    file: UploadFile = File(...),
    is_public: bool = Query(
        False, description="Whether CV should be visible to all users"
    ),
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Upload and process a CV"""
    # Enforce guest quota for anonymous users
    await require_guest_quota(request, "cvs", current_user=current_user)

    try:
        # Validate file type: extension + content-based MIME (rejects renamed non-PDF)
        # Local application imports
        from backend.file_validation import validate_pdf_file

        file_content, safe_filename = await validate_pdf_file(file)

        # Scan for viruses using ClamAV
        # Local application imports
        from backend.clamav_scanner import scan_file_bytes

        is_safe, threat = await asyncio.to_thread(scan_file_bytes, file_content)
        if not is_safe:
            logger.warning(
                "Malicious file upload blocked threat=%s",
                threat,
            )
            raise HTTPException(
                status_code=400,
                detail="File rejected: uploaded file failed security scanning",
            )

        # Reset file position for save
        await file.seek(0)

        # Generate cv_id BEFORE save so file identity is server-controlled
        cv_id = str(uuid.uuid4())

        # Save file with server-controlled storage_key (=cv_id)
        file_path = save_uploaded_file(file, Config.UPLOAD_DIR, storage_key=cv_id)

        # Determine owner
        owner_id = resolve_owner_id(request, current_user)
        is_public_final = (
            is_public if current_user else False
        )  # Guest data always private (sandbox)

        # Process CV with ownership
        cv_data = cv_processor.process_cv(
            cv_id, file_path, user_id=owner_id, is_public=is_public_final
        )

        return CVResponse(
            cv_id=cv_id,
            name=cv_data.get("name", "Unknown"),
            email=cv_data.get("email"),
            phone=cv_data.get("phone"),
            skills=cv_data.get("skills", []),
            experience_years=cv_data.get("experience_years", 0),
            owner_user_id=owner_id,
            is_public=is_public_final,
        )
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file reference")
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/cvs")
async def list_cvs(
    request: Request,
    response: Response,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
    include_public: bool = Query(
        True, description="Include public CVs from other users"
    ),
):
    """List all CVs accessible to the current user"""
    try:
        if current_user:
            user_id = current_user["id"]
            is_admin = current_user.get("role") == "admin"
        else:
            # Guest: show only the current sandbox; public CVs may contain real data.
            gt = get_guest_token(request)
            user_id = guest_owner_id(gt) if gt else None
            is_admin = False
            include_public = False
        cvs = cv_processor.list_all_cvs(
            user_id=user_id, include_public=include_public, is_admin=is_admin
        )
        # Mask PII for CVs not owned by the viewer (admin sees all)
        if not is_admin:
            cvs = mask_cv_list(cvs, viewer_user_id=user_id)
        response.headers["Cache-Control"] = "private, no-cache"
        return {"cvs": cvs}
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/cvs/{cv_id}")
async def get_cv_detail(
    cv_id: str,
    request: Request,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Get a single CV by ID — requires Viewer visibility."""
    cv = vector_store.get_cv(cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")

    # Build viewer from authenticated user or guest token
    user_id = current_user.get("id") if current_user else None
    is_admin = current_user.get("role") == "admin" if current_user else False
    if not user_id:
        gt = get_guest_token(request)
        user_id = guest_owner_id(gt) if gt else None
    viewer = Viewer(user_id=user_id, is_admin=is_admin)

    # Require viewable before returning any metadata or text
    metadata = cv.get("metadata", {})
    try:
        require_viewable(viewer, metadata)
    except PermissionError:
        raise HTTPException(status_code=404, detail="CV not found")

    # Mask PII if viewer is not the owner
    if not is_admin:
        owner = metadata.get("owner_user_id", "")
        if viewer.user_id != owner:
            # Local application imports
            from backend.pii_masking import mask_cv_text

            masked_meta = mask_cv_metadata(metadata, is_owner=False)
            masked_text = mask_cv_text(cv.get("text", ""), metadata)
            cv = {**cv, "metadata": masked_meta, "text": masked_text}
    return cv


@app.get("/uploads/{filename:path}")
async def download_cv_file(
    filename: str,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Legacy route — removed. Use /api/cvs/{cv_id}/download instead."""
    raise HTTPException(
        status_code=410,
        detail="Use /api/cvs/{cv_id}/download",
    )


@app.get("/api/cvs/{cv_id}/download")
@limiter.limit("30/minute")
async def download_cv_by_id(
    request: Request,
    cv_id: str,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Download CV PDF file — only admin or CV owner allowed."""
    cv = vector_store.get_cv(cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")

    metadata = cv.get("metadata", {})
    owner_user_id = metadata.get("owner_user_id")

    # Fail closed: if metadata lacks owner, deny download
    if not owner_user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: CV metadata incomplete",
        )

    user_id = current_user.get("id") if current_user else None
    is_admin = current_user.get("role") == "admin" if current_user else False
    viewer = Viewer(user_id=user_id, is_admin=is_admin)
    try:
        require_downloadable(viewer, metadata)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")

    file_name = metadata.get("file_path", "")
    if not file_name:
        raise HTTPException(
            status_code=404, detail="CV file path not found in metadata"
        )

    try:
        file_full_path = safe_resolve_upload_path(file_name, cv_id, uploads_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file reference")
    if not os.path.isfile(file_full_path):
        raise HTTPException(status_code=404, detail="CV file not found on disk")

    # Use candidate name for a friendly download filename
    candidate_name = metadata.get("name", "candidate").replace(" ", "_")
    download_name = f"CV_{candidate_name}.pdf"

    logger.info(
        "CV_DOWNLOAD user_id=%s cv_id=%s filename=%s",
        user_id,
        cv_id,
        file_name,
    )

    return FileResponse(
        file_full_path,
        media_type="application/pdf",
        filename=download_name,
        headers={
            "Cache-Control": "private, no-cache",
        },
    )


# ============= SCREENING REQUEST MODEL =============


class ScreeningRequest(BaseModel):
    job_id: str = Field(..., min_length=1, max_length=100)
    top_k: int = Field(default=10, ge=1, le=MAX_TOP_K)
    owner_only: bool = False


@app.post("/api/screening")
@limiter.limit("10/minute")
async def screening_candidates(
    request: Request,
    body: ScreeningRequest,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Screen candidates for a job - returns ranked candidates with analysis"""
    # Enforce guest quota for anonymous users
    await require_guest_quota(request, "screenings", current_user=current_user)

    try:
        # Get job info for title
        job = vector_store.get_job(body.job_id)
        job_title = "Unknown"
        if job and job.get("metadata"):
            job_title = job["metadata"].get("title", "Unknown")

        user_id = resolve_owner_id(request, current_user)
        is_admin = current_user.get("role") == "admin" if current_user else False
        viewer = Viewer(user_id=user_id, is_admin=is_admin)

        # Visibility is enforced before retrieval and scoring.
        match_options = {"viewer": viewer, "top_k": body.top_k}
        if body.owner_only:
            match_options["owner_only"] = True
        candidates = await matching_engine.match_candidates_async(
            body.job_id, **match_options
        )

        # Format response for frontend

        formatted_candidates = []
        for candidate in candidates:
            cv_owner = candidate.get("metadata", {}).get("owner_user_id", "")
            cv_public = candidate.get("metadata", {}).get("is_public", True)
            # Skip private CVs that don't belong to the current user
            if not cv_public and cv_owner != user_id:
                continue
            is_owner = user_id and cv_owner == user_id
            raw = {
                "cv_id": candidate.get("cv_id"),
                "name": candidate.get("name", "Unknown"),
                "score": candidate.get("fit_score", 0),
                "matching_skills": candidate.get("strengths", []),
                "missing_skills": candidate.get("gaps", []),
                "analysis": candidate.get("reasoning", ""),
                "experience_years": candidate.get("metadata", {}).get(
                    "experience_years", 0
                ),
                "email": candidate.get("metadata", {}).get("email", ""),
                "phone": candidate.get("metadata", {}).get("phone", ""),
                "owner_user_id": cv_owner,
            }
            # Mask PII for CVs not owned by the viewer
            if not is_admin and not is_owner:
                raw = mask_candidate_result(raw, viewer_user_id=user_id)
            formatted_candidates.append(raw)

        result = {
            "job_id": body.job_id,
            "job_title": job_title,
            "candidates": formatted_candidates,
        }

        # Cache result in PostgreSQL
        try:
            # Standard library imports
            import json

            if user_id:
                db = get_db()
                db.execute(
                    "DELETE FROM screening_cache WHERE job_id = %s AND user_id = %s",
                    (body.job_id, user_id),
                )
                db.execute(
                    "INSERT INTO screening_cache (id, job_id, user_id, top_k, result) VALUES (%s, %s, %s, %s, %s)",
                    (
                        str(uuid.uuid4()),
                        body.job_id,
                        user_id,
                        body.top_k,
                        json.dumps(result),
                    ),
                )
        except Exception as cache_err:
            logger.warning("Failed to cache screening result: %s", str(cache_err))

        return result
    except Exception as e:
        logger.error("Error in screening", error_type=type(e).__name__, error=str(e))
        # Standard library imports
        import traceback

        traceback.print_exc()
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/screening/{job_id}")
async def get_cached_screening(
    request: Request,
    job_id: str,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Get cached screening results for a job. Returns 404 if no cache."""
    # Standard library imports
    import json

    user_id = current_user.get("id") if current_user else None
    if not user_id:
        gt = get_guest_token(request)
        user_id = guest_owner_id(gt) if gt else None
    is_admin = current_user.get("role") == "admin" if current_user else False
    if not user_id:
        raise HTTPException(status_code=404, detail="No cached screening results")
    db = get_db()
    row = db.fetchone(
        "SELECT result, top_k, created_at FROM screening_cache WHERE job_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
        (job_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="No cached screening results")
    result = (
        json.loads(row["result"]) if isinstance(row["result"], str) else row["result"]
    )
    # Mask PII in cached results for non-owners
    if not is_admin and "candidates" in result:
        result["candidates"] = [
            mask_candidate_result(c, viewer_user_id=user_id)
            for c in result["candidates"]
        ]
    result["cached"] = True
    result["cached_at"] = (
        row["created_at"].isoformat() + "Z"
        if hasattr(row["created_at"], "isoformat")
        else str(row["created_at"])
    )
    return result


@app.post("/api/match/{job_id}")
@limiter.limit("10/minute")
async def match_candidates(
    request: Request,
    job_id: str,
    top_k: int = 10,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Match candidates to a job without exposing stored CV metadata."""
    try:
        user_id = current_user.get("id") if current_user else None
        if not user_id:
            gt = get_guest_token(request)
            user_id = guest_owner_id(gt) if gt else None
        viewer = Viewer(
            user_id=user_id,
            is_admin=current_user.get("role") == "admin" if current_user else False,
        )
        candidates = await matching_engine.match_candidates_async(
            job_id, viewer=viewer, top_k=top_k
        )
        return {
            "candidates": [
                {
                    key: candidate[key]
                    for key in (
                        "cv_id",
                        "name",
                        "fit_score",
                        "strengths",
                        "gaps",
                        "reasoning",
                        "similarity_score",
                    )
                    if key in candidate
                }
                for candidate in candidates
            ]
        }
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/questions/{job_id}/{cv_id}")
@limiter.limit("10/minute")
async def generate_questions(
    request: Request,
    job_id: str,
    cv_id: str,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Generate interview questions for a candidate — requires viewable job AND CV."""
    try:
        # Build viewer from authenticated user or guest token
        user_id = current_user.get("id") if current_user else None
        is_admin = current_user.get("role") == "admin" if current_user else False
        if not user_id:
            gt = get_guest_token(request)
            user_id = guest_owner_id(gt) if gt else None
        viewer = Viewer(user_id=user_id, is_admin=is_admin)

        # Require both job and CV viewable before calling generator
        job = vector_store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        try:
            require_viewable(viewer, job.get("metadata", {}))
        except PermissionError:
            raise HTTPException(status_code=404, detail="Job not found")

        cv = vector_store.get_cv(cv_id)
        if not cv:
            raise HTTPException(status_code=404, detail="CV not found")
        try:
            require_viewable(viewer, cv.get("metadata", {}))
        except PermissionError:
            raise HTTPException(status_code=404, detail="CV not found")

        questions = question_generator.generate_questions(job_id, cv_id)
        return {"questions": questions}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= AI AGENT ENDPOINTS =============


class AgentQuickScreenRequest(BaseModel):
    job_text: str = Field(..., min_length=50, max_length=MAX_JOB_TEXT_LENGTH)
    cv_ids: List[str] = Field(..., max_length=50)  # Max 50 CVs at a time

    @field_validator("cv_ids")
    @classmethod
    def validate_cv_ids(cls, v):
        """Reject path-like values in cv_ids."""
        return validate_cv_id_list(v)


class AgentWorkflowRequest(BaseModel):
    task: str = Field(
        ..., pattern=r"^(analyze_job|screen_cvs|match_candidates|full_workflow)$"
    )
    job_text: Optional[str] = Field(None, max_length=MAX_JOB_TEXT_LENGTH)
    job_id: Optional[str] = Field(None, max_length=100)
    cv_ids: Optional[List[str]] = Field(None, max_length=50)
    top_k: Optional[int] = Field(default=10, ge=1, le=MAX_TOP_K)

    @field_validator("cv_ids")
    @classmethod
    def validate_cv_ids(cls, v):
        """Reject path-like values in cv_ids."""
        if v is None:
            return v
        return validate_cv_id_list(v)


@app.post("/api/agent/quick-screen")
@limiter.limit("5/minute")
async def agent_quick_screen(
    request: Request,
    body: AgentQuickScreenRequest,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """
    AI Agent: Quick screening workflow
    Automatically analyzes job, screens CVs, matches candidates, and generates questions
    """
    try:
        logger.info("AI Agent: Starting quick screen workflow")
        # Resolve owner for guest support
        resolved_owner = resolve_owner_id(request, current_user)
        user_id = current_user.get("id") if current_user else None
        is_admin = current_user.get("role") == "admin" if current_user else False
        viewer = Viewer(user_id=user_id or resolved_owner, is_admin=is_admin)
        resolved_files = []
        for cv_id in body.cv_ids:
            cv = vector_store.get_cv(cv_id)
            if not cv:
                raise HTTPException(status_code=404, detail="CV not found")
            metadata = cv.get("metadata", {})
            owner = metadata.get("owner_user_id")
            if not owner:
                raise HTTPException(status_code=404, detail="CV not found")
            try:
                require_viewable(viewer, metadata)
            except PermissionError:
                raise HTTPException(status_code=404, detail="CV not found")
            file_name = metadata.get("file_path", "")
            if not file_name:
                raise HTTPException(status_code=404, detail="CV not found")
            try:
                resolved_path = safe_resolve_upload_path(file_name, cv_id, uploads_path)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid file reference")
            if not os.path.isfile(resolved_path):
                raise HTTPException(status_code=404, detail="CV not found")
            resolved_files.append(resolved_path)
        result = recruitment_agent.quick_screen(
            job_text=body.job_text,
            cv_files=resolved_files,
            viewer_user_id=viewer.user_id,
            viewer_is_admin=viewer.is_admin,
        )
        # Compute ownership from ORIGINAL authoritative candidate data BEFORE masking.
        raw_candidates = result.get("candidates") or []
        owns_all_candidates = True
        if not viewer.is_admin and raw_candidates:
            owns_all_candidates = all(
                (
                    c.get("owner_user_id")
                    or c.get("metadata", {}).get("owner_user_id", "")
                )
                == viewer.user_id
                for c in raw_candidates
            )
        # Mask PII in candidates for non-admin viewers
        if not viewer.is_admin and raw_candidates:
            result["candidates"] = [
                mask_candidate_result(c, viewer_user_id=viewer.user_id)
                for c in raw_candidates
            ]
        # Suppress summary for non-owner, non-admin viewers (fail-closed privacy)
        if not viewer.is_admin and result.get("summary") and not owns_all_candidates:
            result["summary"] = "[Summary available to CV owner only]"
        # Suppress questions for non-owner, non-admin (LLM questions contain candidate names)
        if not viewer.is_admin and result.get("questions") and not owns_all_candidates:
            result["questions"] = "[Questions available to CV owner only]"
        return {
            "status": result.get("status"),
            "job_id": result.get("job_id"),
            "job_data": result.get("job_data"),
            "candidates": result.get("candidates"),
            "questions": result.get("questions"),
            "summary": result.get("summary"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI Agent error in quick_screen", error=str(e))
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/agent/workflow")
@limiter.limit("5/minute")
async def agent_workflow(
    request: Request,
    body: AgentWorkflowRequest,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """
    AI Agent: Custom workflow execution
    Run specific recruitment tasks autonomously
    """
    try:
        logger.info("AI Agent: Starting workflow", task=body.task)

        # Resolve owner for guest support
        resolved_owner = resolve_owner_id(request, current_user)
        resolved_files = None
        if body.cv_ids:
            user_id = current_user.get("id") if current_user else None
            is_admin = current_user.get("role") == "admin" if current_user else False
            viewer = Viewer(user_id=user_id or resolved_owner, is_admin=is_admin)
            resolved_files = []
            for cv_id in body.cv_ids:
                cv = vector_store.get_cv(cv_id)
                if not cv:
                    raise HTTPException(status_code=404, detail="CV not found")
                metadata = cv.get("metadata", {})
                owner = metadata.get("owner_user_id")
                if not owner:
                    raise HTTPException(status_code=404, detail="CV not found")
                try:
                    require_viewable(viewer, metadata)
                except PermissionError:
                    raise HTTPException(status_code=404, detail="CV not found")
                file_name = metadata.get("file_path", "")
                if not file_name:
                    raise HTTPException(status_code=404, detail="CV not found")
                try:
                    resolved_path = safe_resolve_upload_path(
                        file_name, cv_id, uploads_path
                    )
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail="Invalid file reference"
                    )
                if not os.path.isfile(resolved_path):
                    raise HTTPException(status_code=404, detail="CV not found")
                resolved_files.append(resolved_path)

        initial_state = {
            "task": body.task,
            "job_text": body.job_text,
            "job_id": body.job_id,
            "cv_files": resolved_files,
            "top_k": body.top_k,
            "viewer_user_id": resolved_owner,
            "viewer_is_admin": (
                current_user.get("role") == "admin" if current_user else False
            ),
        }

        final_state = recruitment_agent.run_workflow(initial_state)

        # Mask PII in matches for non-admin viewers
        matches = final_state.get("matches")
        is_admin = current_user.get("role") == "admin" if current_user else False
        viewer_user_id = None
        if not is_admin:
            viewer_user_id = current_user.get("id") if current_user else None
            if not viewer_user_id:
                gt = get_guest_token(request)
                viewer_user_id = guest_owner_id(gt) if gt else None

        # Compute ownership from ORIGINAL authoritative match data BEFORE masking.
        raw_matches = final_state.get("matches") or []
        owns_all_candidates = True
        if not is_admin and raw_matches:
            owns_all_candidates = all(
                (
                    m.get("owner_user_id")
                    or m.get("metadata", {}).get("owner_user_id", "")
                )
                == viewer_user_id
                for m in raw_matches
            )

        if not is_admin and matches:
            matches = [
                mask_candidate_result(m, viewer_user_id=viewer_user_id) for m in matches
            ]

        # Suppress analysis for non-owner, non-admin viewers (fail-closed privacy)
        analysis = final_state.get("analysis")
        if not is_admin and analysis and raw_matches and not owns_all_candidates:
            analysis = "[Analysis available to CV owner only]"

        # Suppress questions for non-owner, non-admin (questions contain candidate names)
        questions = final_state.get("questions")
        if not is_admin and questions and raw_matches and not owns_all_candidates:
            questions = "[Questions available to CV owner only]"

        return {
            "status": final_state.get("status"),
            "job_data": final_state.get("job_data"),
            "matches": matches,
            "questions": questions,
            "analysis": analysis,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("AI Agent error in workflow", error=str(e))
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# ============= DATA OWNERSHIP ENDPOINTS =============


class VisibilityRequest(BaseModel):
    is_public: bool


@app.patch("/api/jobs/{job_id}/visibility")
async def update_job_visibility(
    job_id: str,
    request: VisibilityRequest,
    current_user: Dict = Depends(csrf_protected_user),
):
    """Update the public visibility of a job"""

    try:
        is_admin = current_user.get("role") == "admin"
        success = vector_store.update_job_visibility(
            job_id, request.is_public, None if is_admin else current_user["id"]
        )
        if not success:
            raise HTTPException(
                status_code=404, detail="Job not found or not authorized"
            )
        return {"success": True, "is_public": request.is_public}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.patch("/api/cvs/{cv_id}/visibility")
async def update_cv_visibility(
    cv_id: str,
    request: VisibilityRequest,
    current_user: Dict = Depends(csrf_protected_user),
):
    """Update the public visibility of a CV"""

    try:
        is_admin = current_user.get("role") == "admin"
        success = vector_store.update_cv_visibility(
            cv_id, request.is_public, None if is_admin else current_user["id"]
        )
        if not success:
            raise HTTPException(
                status_code=404, detail="CV not found or not authorized"
            )
        # Invalidate all screening caches that may reference this CV
        try:
            db = get_db()
            db.execute(
                "DELETE FROM screening_cache WHERE result::text LIKE %s",
                (f"%{cv_id}%",),
            )
        except Exception as cache_err:
            logger.warning("Failed to invalidate screening cache: %s", str(cache_err))
        return {"success": True, "is_public": request.is_public}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/jobs/{job_id}")
async def delete_job(
    job_id: str,
    current_user: Dict = Depends(csrf_protected_user),
):
    """Delete a job by ID (owner or admin)."""
    is_admin = current_user.get("role") == "admin"
    success = vector_store.delete_job(job_id, None if is_admin else current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or not authorized")
    return {"success": True}


@app.delete("/api/cvs/{cv_id}")
async def delete_cv(
    cv_id: str,
    current_user: Dict = Depends(csrf_protected_user),
):
    """Delete a CV by ID (owner or admin). Also removes file from disk."""
    is_admin = current_user.get("role") == "admin"
    # Resolve file path before deletion (safe_resolve_upload_path validates ownership
    # indirectly via cv_id matching the file_name).
    cv = vector_store.get_cv(cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found or not authorized")
    file_name = cv.get("metadata", {}).get("file_path", "")
    resolved_path = None
    if file_name:
        try:
            resolved_path = safe_resolve_upload_path(file_name, cv_id, uploads_path)
        except ValueError:
            pass

    # Delete vector entry first (DB-safe ordering: if this fails, file is untouched)
    success = vector_store.delete_cv(cv_id, None if is_admin else current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="CV not found or not authorized")

    # Then delete file from disk (best-effort; DB is already clean)
    if resolved_path and os.path.isfile(resolved_path):
        try:
            os.remove(resolved_path)
        except OSError:
            logger.warning("Failed to delete CV file on disk: cv_id=%s", cv_id)

    return {"success": True}


if __name__ == "__main__":
    # Third-party imports
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
