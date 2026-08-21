"""
Interview Question Set Routes - Save, retrieve, and manage interview question sets.

Endpoints:
- POST /api/interview-questions/generate/{job_id}/{cv_id} - Generate AI questions
- POST /api/interview-questions/save - Save a question set
- GET  /api/interview-questions/job/{job_id} - List sets for a job
- GET  /api/interview-questions/set/{set_id} - Get a specific set
- DELETE /api/interview-questions/set/{set_id} - Delete a set
"""

# Standard library imports
import hashlib
import json
import logging
import uuid
from typing import Dict, List, Optional

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

# Local application imports
from backend.auth_cookies import optional_user_from_cookie
from backend.datetime_utils import format_dt, utcnow
from backend.guest_token import get_guest_token, guest_owner_id
from backend.limiter import limiter
from backend.security import csrf_protected_optional_user
from src.database.postgres_db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interview-questions", tags=["interview-questions"])


# ========== Request/Response Models ==========


class QuestionItem(BaseModel):
    question: str
    type: str = "Technical"
    focus_area: str = "General"
    source: str = "ai"
    liked: Optional[bool] = None


class SaveQuestionSetRequest(BaseModel):
    job_id: str
    cv_id: str
    candidate_name: Optional[str] = None
    questions: List[QuestionItem]


def matching_context_from_cached_screening(
    result: object, cv_id: str
) -> Optional[Dict]:
    if not isinstance(result, dict):
        return None
    candidates = result.get("candidates", [])
    if not isinstance(candidates, list) or not all(
        isinstance(candidate, dict) for candidate in candidates
    ):
        return None
    for candidate in candidates:
        if candidate.get("cv_id") == cv_id:
            strengths = candidate.get("matching_skills", [])
            gaps = candidate.get("missing_skills", [])
            if not isinstance(strengths, list) or not isinstance(gaps, list):
                return None
            if len(strengths) > 20 or len(gaps) > 20:
                return None
            if any(
                not isinstance(item, str) or not item.strip() or len(item) > 200
                for item in [*strengths, *gaps]
            ):
                return None
            return {
                "strengths": strengths.copy(),
                "gaps": gaps.copy(),
            }
    return None


def matching_context_hash(context: Dict) -> str:
    """Return opaque proof for sanitized context passed to generator."""
    payload = json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


# ========== Endpoints ==========


@router.post("/generate/{job_id}/{cv_id}")
@limiter.limit("5/minute")
async def generate_questions(
    request: Request,
    job_id: str,
    cv_id: str,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Generate AI interview questions for a candidate and job.

    Requires both job and CV to be viewable by the caller.
    """
    try:
        # Local application imports
        from backend.access_control import Viewer, require_viewable, resolve_owner_id
        from src.config import Config
        from src.database.vector_store import VectorStore
        from src.processors.question_generator import QuestionGenerator

        # Build viewer from authenticated user or guest token
        user_id = resolve_owner_id(request, current_user)
        is_admin = current_user.get("role") == "admin" if current_user else False
        viewer = Viewer(user_id=user_id, is_admin=is_admin)

        # Require both job and CV viewable before calling generator
        vs = VectorStore(Config.CHROMA_PERSIST_DIR)
        job = vs.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Resource not found")
        try:
            require_viewable(viewer, job.get("metadata", {}))
        except PermissionError:
            raise HTTPException(status_code=404, detail="Resource not found")

        cv = vs.get_cv(cv_id)
        if not cv:
            raise HTTPException(status_code=404, detail="Resource not found")
        try:
            require_viewable(viewer, cv.get("metadata", {}))
        except PermissionError:
            raise HTTPException(status_code=404, detail="Resource not found")

        matching_context = None
        if user_id:
            try:
                row = get_db().fetchone(
                    """
                    SELECT result FROM screening_cache
                    WHERE job_id = %s AND user_id = %s
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (job_id, user_id),
                )
                if row and row.get("result") is not None:
                    result = row["result"]
                    if isinstance(result, str):
                        result = json.loads(result)
                    matching_context = matching_context_from_cached_screening(
                        result, cv_id
                    )
            except Exception:
                logger.warning(
                    "Screening cache unavailable; generating questions without matching context"
                )

        qg = QuestionGenerator(vs)
        questions = qg.generate_questions(
            job_id, cv_id, matching_context=matching_context
        )

        logger.info(
            "Generated %s questions for job=%s cv=%s",
            len(questions),
            job_id,
            cv_id,
        )
        return {
            "questions": questions,
            "job_id": job_id,
            "cv_id": cv_id,
            "matching_context_used": matching_context is not None,
            "matching_context_hash": (
                matching_context_hash(matching_context)
                if matching_context is not None
                else None
            ),
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("Question generation failed: %s", str(e))
        raise HTTPException(status_code=404, detail="Resource not found")
    except Exception as e:
        logger.error(
            "Question generation error for job=%s cv=%s: %s", job_id, cv_id, str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to generate questions")


@router.post("/save")
@limiter.limit("10/minute")
async def save_question_set(
    request: Request,
    body: SaveQuestionSetRequest,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Save a question set."""
    user_id = current_user.get("id") if current_user else None
    if not user_id:
        gt = get_guest_token(request)
        user_id = guest_owner_id(gt) if gt else None
    if not user_id:
        raise HTTPException(
            status_code=403, detail="Guest token required for anonymous access"
        )
    set_id = str(uuid.uuid4())
    now = utcnow()
    questions_json = json.dumps([q.model_dump() for q in body.questions])

    try:
        db = get_db()
        db.execute(
            """
            INSERT INTO interview_question_set
                (id, job_id, cv_id, user_id, candidate_name, questions, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                set_id,
                body.job_id,
                body.cv_id,
                user_id,
                body.candidate_name,
                questions_json,
                now,
                now,
            ),
        )
        logger.info(
            "Saved question set %s for user=%s job=%s", set_id, user_id, body.job_id
        )
        return {"id": set_id, "message": "saved"}

    except Exception as e:
        logger.error("Failed to save question set: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to save question set")


@router.get("/job/{job_id}")
async def list_question_sets(
    request: Request,
    job_id: str,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """List saved question sets for a job (filtered by user)."""
    user_id = current_user.get("id") if current_user else None
    if not user_id:
        gt = get_guest_token(request)
        user_id = guest_owner_id(gt) if gt else None
    if not user_id:
        raise HTTPException(
            status_code=403, detail="Guest token required for anonymous access"
        )

    try:
        db = get_db()
        rows = db.fetchall(
            """
            SELECT id, cv_id, candidate_name, questions, created_at
            FROM interview_question_set
            WHERE job_id = %s AND user_id = %s
            ORDER BY created_at DESC
            """,
            (job_id, user_id),
        )

        sets = []
        for row in rows:
            questions = json.loads(row["questions"]) if row["questions"] else []
            sets.append(
                {
                    "id": row["id"],
                    "cv_id": row["cv_id"],
                    "candidate_name": row["candidate_name"],
                    "question_count": len(questions),
                    "created_at": format_dt(row["created_at"]),
                }
            )

        return {"sets": sets}

    except Exception as e:
        logger.error("Failed to list question sets for job=%s: %s", job_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to list question sets")


@router.get("/set/{set_id}")
async def get_question_set(
    request: Request,
    set_id: str,
    current_user: Optional[Dict] = Depends(optional_user_from_cookie),
):
    """Get a specific question set."""
    user_id = current_user.get("id") if current_user else None
    if not user_id:
        gt = get_guest_token(request)
        user_id = guest_owner_id(gt) if gt else None
    if not user_id:
        raise HTTPException(
            status_code=403, detail="Guest token required for anonymous access"
        )

    try:
        db = get_db()
        row = db.fetchone(
            """
            SELECT id, job_id, cv_id, user_id, candidate_name, questions, created_at, updated_at
            FROM interview_question_set
            WHERE id = %s AND user_id = %s
            """,
            (set_id, user_id),
        )

        if not row:
            raise HTTPException(status_code=404, detail="Question set not found")

        questions = json.loads(row["questions"]) if row["questions"] else []
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "cv_id": row["cv_id"],
            "candidate_name": row["candidate_name"],
            "questions": questions,
            "created_at": format_dt(row["created_at"]),
            "updated_at": format_dt(row["updated_at"]),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get question set %s: %s", set_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to get question set")


@router.delete("/set/{set_id}")
async def delete_question_set(
    request: Request,
    set_id: str,
    current_user: Optional[Dict] = Depends(csrf_protected_optional_user),
):
    """Delete a question set (owner only)."""
    user_id = current_user.get("id") if current_user else None
    if not user_id:
        gt = get_guest_token(request)
        user_id = guest_owner_id(gt) if gt else None
    if not user_id:
        raise HTTPException(
            status_code=403, detail="Guest token required for anonymous access"
        )

    try:
        db = get_db()
        row = db.fetchone(
            "SELECT id, user_id FROM interview_question_set WHERE id = %s",
            (set_id,),
        )

        if not row:
            raise HTTPException(status_code=404, detail="Question set not found")

        if row["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this set"
            )

        db.execute("DELETE FROM interview_question_set WHERE id = %s", (set_id,))
        logger.info("Deleted question set %s by user=%s", set_id, user_id)
        return {"message": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete question set %s: %s", set_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to delete question set")
