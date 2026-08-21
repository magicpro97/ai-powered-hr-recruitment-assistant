"""Central resource visibility policy."""

# Standard library imports
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

# Third-party imports
from fastapi import Request

# Canonical home for SYSTEM_USER_ID (was in vector_store, moved here to avoid circular import)
SYSTEM_USER_ID = "system"


@dataclass(frozen=True)
class Viewer:
    user_id: Optional[str] = None
    is_admin: bool = False


def can_view_resource(viewer: Viewer, metadata: Mapping) -> bool:
    """Return whether viewer may read metadata-bearing resource."""
    owner_user_id = metadata.get("owner_user_id")
    if not owner_user_id:
        return False
    if viewer.is_admin:
        return True
    if metadata.get("is_public") is True:
        return True
    return viewer.user_id == owner_user_id


def require_viewable(viewer: Viewer, metadata: Mapping) -> None:
    """Raise when resource is not visible to viewer."""
    if not can_view_resource(viewer, metadata):
        raise PermissionError("Resource is not viewable by this viewer")


def visibility_where(viewer: Viewer) -> Optional[dict]:
    """Build Chroma visibility filter; None means unrestricted admin query."""
    if viewer.is_admin:
        return None
    if viewer.user_id:
        return {
            "$or": [
                {"owner_user_id": viewer.user_id},
                {"is_public": True},
            ]
        }
    return {"is_public": True}


def resolve_owner_id(request: Request, current_user) -> Optional[str]:
    """Resolve the owner ID from the current request context.

    Priority: authenticated user id > validated guest owner > None.
    Never returns SYSTEM_USER_ID.
    """
    if current_user:
        return current_user.get("id")
    # Lazy import to avoid circular dependency at module level
    # Local application imports
    from backend.guest_token import get_guest_token, guest_owner_id

    gt = get_guest_token(request)
    if gt:
        return guest_owner_id(gt)
    return None


# ── cv_ids validation ────────────────────────────────────────────────────

_CV_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_cv_id_list(cv_ids: List[str]) -> List[str]:
    """Validate a list of CV ID strings.

    Each ID must be alphanumeric with dashes/underscores only — no path
    separators, no ``..``, no special characters.  Raises ``ValueError``
    on the first invalid ID so Pydantic's ``@field_validator`` surfaces it.
    """
    if not cv_ids:
        raise ValueError("cv_ids must not be empty")
    for cv_id in cv_ids:
        if "/" in cv_id or "\\" in cv_id or ".." in cv_id:
            raise ValueError(f"Invalid cv_id: {cv_id}")
        if not _CV_ID_RE.match(cv_id):
            raise ValueError(f"Invalid cv_id format: {cv_id}")
    return cv_ids


# ── Download-only predicate ──────────────────────────────────────────────


def can_download_resource(viewer: Viewer, metadata: Mapping) -> bool:
    """Return whether viewer may download the raw file.

    Unlike ``can_view_resource`` this does **not** grant access for public
    resources — only the owner or an admin may download.
    """
    owner_user_id = metadata.get("owner_user_id")
    if not owner_user_id:
        return False
    if viewer.is_admin:
        return True
    return viewer.user_id == owner_user_id


def require_downloadable(viewer: Viewer, metadata: Mapping) -> None:
    """Raise PermissionError when resource is not downloadable."""
    if not can_download_resource(viewer, metadata):
        raise PermissionError("Download not permitted for this viewer")


# ── Safe file_path resolution ────────────────────────────────────────────


def safe_resolve_upload_path(file_name: str, cv_id: str, uploads_root: str) -> str:
    """Resolve *file_name* against *uploads_root* with identity checks.

    * Rejects traversal (``..``, ``/``, ``\\``) and absolute paths.
    * Requires *file_name* to equal ``{cv_id}.pdf`` — the server-controlled
      identity established at upload time.
    * Guaranteed to stay under *uploads_root*.

    Returns the absolute resolved path, or raises ``ValueError``.
    """
    if not file_name or not cv_id:
        raise ValueError("file_name and cv_id are required")

    # Reject null bytes, traversal, absolute paths
    if "\0" in file_name:
        raise ValueError("Invalid file name")
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        raise ValueError("Invalid file path in CV metadata")
    if os.path.isabs(file_name):
        raise ValueError("Invalid file path in CV metadata")

    expected = f"{cv_id}.pdf"
    if Path(file_name).name != expected:
        raise ValueError(
            f"file_path '{file_name}' does not match expected '{expected}'"
        )

    resolved = str(Path(uploads_root).resolve() / expected)
    return resolved


# ── Chat upload response DTO ─────────────────────────────────────────────

_SAFE_CHAT_UPLOAD_FIELDS = frozenset(
    {
        "session_id",
        "cv_id",
        "name",
        "skills",
        "summary",
        "experience_years",
        "message",
    }
)


def chat_upload_response_fields() -> frozenset:
    """Return the set of fields allowed in a chat upload response."""
    return _SAFE_CHAT_UPLOAD_FIELDS


def build_chat_upload_response(
    *,
    session_id: str,
    cv_id: str,
    name: str,
    skills: Optional[List[str]] = None,
    summary: Optional[str] = None,
    experience_years: int = 0,
    education: Optional[str] = None,
    work_history: Optional[List[Dict[str, Any]]] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    file_path: Optional[str] = None,
    message: str = "",
) -> Dict[str, Any]:
    """Build a safe chat upload response dict.

    Only contractually safe fields are included regardless of what was
    passed in.  Sensitive fields (education, work_history, email, phone,
    file_path) are silently dropped.
    """
    return {
        "session_id": session_id,
        "cv_id": cv_id,
        "name": name,
        "skills": skills or [],
        "summary": summary or "",
        "experience_years": experience_years,
        "message": message,
    }
