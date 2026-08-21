"""
Backend-enforced guest usage limits.

This module tracks and enforces usage limits for unauthenticated (guest) users
to prevent abuse and encourage registration. Limits are enforced server-side
using IP + User-Agent fingerprinting stored in PostgreSQL.

Guest limits are NOT a security feature - they're a freemium conversion tool.
Determined users can bypass with VPN/proxy, but that's acceptable for this use case.
"""

# Standard library imports
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

# Third-party imports
from fastapi import HTTPException, Request

# Local application imports
from backend.limiter import get_real_ip
from src.database.postgres_db import get_db

logger = logging.getLogger(__name__)


# Guest limits configuration
@dataclass(frozen=True)
class GuestLimits:
    """Guest usage limits per 24-hour window."""

    MAX_JOBS: int = 3
    MAX_CVS: int = 10
    MAX_CHAT_MESSAGES: int = 20
    MAX_SCREENINGS: int = 5
    WINDOW_HOURS: int = 24  # Rolling window for limit reset


GUEST_LIMITS = GuestLimits()

# Resource types
ResourceType = Literal["jobs", "cvs", "chat", "screenings"]


def get_guest_fingerprint(request: Request) -> str:
    """
    Create a fingerprint from IP + User-Agent for guest identification.

    This is NOT cryptographically secure - it's just for rate limiting.
    Determined users can bypass with VPN, but that's acceptable.
    """
    ip = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")

    # Create a hash of IP + User-Agent
    fingerprint_data = f"{ip}:{user_agent}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]


def get_user_agent_hash(request: Request) -> str:
    """Hash User-Agent for storage (privacy)."""
    user_agent = request.headers.get("user-agent", "unknown")
    return hashlib.sha256(user_agent.encode()).hexdigest()[:16]


async def get_guest_usage(request: Request) -> dict:
    """
    Get current usage stats for a guest user.

    Returns dict with usage counts and limits.
    """
    fingerprint = get_guest_fingerprint(request)

    db = get_db()
    with db.get_connection() as conn:
        result = conn.execute(
            """
            SELECT jobs_count, cvs_count, chat_count, screenings_count,
                   window_start_at, last_activity_at
            FROM guest_usage
            WHERE fingerprint_hash = %s
            """,
            (fingerprint,),
        ).fetchone()

        if not result:
            return {
                "usage": {
                    "jobs": 0,
                    "cvs": 0,
                    "chat": 0,
                    "screenings": 0,
                },
                "limits": {
                    "MAX_JOBS": GUEST_LIMITS.MAX_JOBS,
                    "MAX_CVS": GUEST_LIMITS.MAX_CVS,
                    "MAX_CHAT_MESSAGES": GUEST_LIMITS.MAX_CHAT_MESSAGES,
                    "MAX_SCREENINGS": GUEST_LIMITS.MAX_SCREENINGS,
                },
                "remaining": {
                    "jobs": GUEST_LIMITS.MAX_JOBS,
                    "cvs": GUEST_LIMITS.MAX_CVS,
                    "chat": GUEST_LIMITS.MAX_CHAT_MESSAGES,
                    "screenings": GUEST_LIMITS.MAX_SCREENINGS,
                },
                "window_resets_at": None,
            }

        # Result is a dict from psycopg3 dict_row
        jobs_count = result["jobs_count"]
        cvs_count = result["cvs_count"]
        chat_count = result["chat_count"]
        screenings_count = result["screenings_count"]
        window_start = result["window_start_at"]

        # Check if window should reset (24 hours)
        now = datetime.now(timezone.utc)
        if window_start:
            # Parse string to datetime if needed
            if isinstance(window_start, str):
                # Standard library imports
                from datetime import datetime as dt

                window_start = dt.fromisoformat(window_start.replace("Z", "+00:00"))
            if window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=timezone.utc)
            if now - window_start > timedelta(hours=GUEST_LIMITS.WINDOW_HOURS):
                # Window expired, reset counts
                conn.execute(
                    """
                    UPDATE guest_usage
                    SET jobs_count = 0, cvs_count = 0, chat_count = 0, screenings_count = 0,
                        window_start_at = CURRENT_TIMESTAMP
                    WHERE fingerprint_hash = %s
                    """,
                    (fingerprint,),
                )
                jobs_count = cvs_count = chat_count = screenings_count = 0
                window_start = now

        window_resets_at = (
            (window_start + timedelta(hours=GUEST_LIMITS.WINDOW_HOURS)).isoformat()
            if window_start
            else None
        )

        return {
            "usage": {
                "jobs": jobs_count,
                "cvs": cvs_count,
                "chat": chat_count,
                "screenings": screenings_count,
            },
            "limits": {
                "MAX_JOBS": GUEST_LIMITS.MAX_JOBS,
                "MAX_CVS": GUEST_LIMITS.MAX_CVS,
                "MAX_CHAT_MESSAGES": GUEST_LIMITS.MAX_CHAT_MESSAGES,
                "MAX_SCREENINGS": GUEST_LIMITS.MAX_SCREENINGS,
            },
            "remaining": {
                "jobs": max(0, GUEST_LIMITS.MAX_JOBS - jobs_count),
                "cvs": max(0, GUEST_LIMITS.MAX_CVS - cvs_count),
                "chat": max(0, GUEST_LIMITS.MAX_CHAT_MESSAGES - chat_count),
                "screenings": max(0, GUEST_LIMITS.MAX_SCREENINGS - screenings_count),
            },
            "window_resets_at": window_resets_at,
        }


async def check_guest_quota(
    request: Request,
    resource_type: ResourceType,
    increment: int = 1,
) -> bool:
    """
    Check if a guest can perform an action and increment the counter if allowed.

    Args:
        request: FastAPI request object
        resource_type: Type of resource being accessed ("jobs", "cvs", "chat", "screenings")
        increment: Amount to increment (default 1, can be more for batch uploads)

    Returns:
        True if action is allowed, False if limit reached
    """
    fingerprint = get_guest_fingerprint(request)
    ip_address = get_real_ip(request)
    ua_hash = get_user_agent_hash(request)

    # Map resource type to column and limit
    column_map = {
        "jobs": ("jobs_count", GUEST_LIMITS.MAX_JOBS),
        "cvs": ("cvs_count", GUEST_LIMITS.MAX_CVS),
        "chat": ("chat_count", GUEST_LIMITS.MAX_CHAT_MESSAGES),
        "screenings": ("screenings_count", GUEST_LIMITS.MAX_SCREENINGS),
    }

    column, limit = column_map[resource_type]

    db = get_db()
    with db.get_connection() as conn:
        # Get or create guest record with upsert
        result = conn.execute(
            """
            INSERT INTO guest_usage (fingerprint_hash, ip_address, user_agent_hash)
            VALUES (%s, %s, %s)
            ON CONFLICT (fingerprint_hash) DO UPDATE
            SET last_activity_at = CURRENT_TIMESTAMP,
                ip_address = EXCLUDED.ip_address
            RETURNING jobs_count, cvs_count, chat_count, screenings_count, window_start_at
            """,
            (fingerprint, ip_address, ua_hash),
        ).fetchone()

        # Result is a dict from psycopg3 dict_row
        jobs_count = result["jobs_count"]
        cvs_count = result["cvs_count"]
        chat_count = result["chat_count"]
        screenings_count = result["screenings_count"]
        window_start = result["window_start_at"]

        # Check if window should reset (atomic: reset in DB and refetch to avoid race)
        now = datetime.now(timezone.utc)
        if window_start:
            # Parse string to datetime if needed
            if isinstance(window_start, str):
                # Standard library imports
                from datetime import datetime as dt

                window_start = dt.fromisoformat(window_start.replace("Z", "+00:00"))
            if window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=timezone.utc)
            if now - window_start > timedelta(hours=GUEST_LIMITS.WINDOW_HOURS):
                # Atomic reset: only reset if window_start hasn't changed (prevents race)
                updated = conn.execute(
                    """
                    UPDATE guest_usage
                    SET jobs_count = 0, cvs_count = 0, chat_count = 0, screenings_count = 0,
                        window_start_at = CURRENT_TIMESTAMP
                    WHERE fingerprint_hash = %s
                      AND window_start_at = %s
                    RETURNING jobs_count, cvs_count, chat_count, screenings_count
                    """,
                    (fingerprint, result["window_start_at"]),
                ).fetchone()
                if updated:
                    jobs_count = cvs_count = chat_count = screenings_count = 0

        # Get current count for the resource
        current_counts = {
            "jobs": jobs_count,
            "cvs": cvs_count,
            "chat": chat_count,
            "screenings": screenings_count,
        }
        current = current_counts[resource_type]

        # Check if increment would exceed limit
        if current + increment > limit:
            logger.info(
                f"Guest quota exceeded: {resource_type}",
                extra={
                    "fingerprint": fingerprint[:8],
                    "ip": ip_address,
                    "current": current,
                    "limit": limit,
                    "requested": increment,
                },
            )
            return False

        # Increment the counter (column name validated from fixed column_map above)
        allowed_columns = {"jobs_count", "cvs_count", "chat_count", "screenings_count"}
        if column not in allowed_columns:
            raise ValueError(f"Invalid column name: {column}")
        conn.execute(
            f"""
            UPDATE guest_usage
            SET {column} = {column} + %s,
                last_activity_at = CURRENT_TIMESTAMP
            WHERE fingerprint_hash = %s
            """,
            (increment, fingerprint),
        )

        logger.debug(
            f"Guest quota incremented: {resource_type}",
            extra={
                "fingerprint": fingerprint[:8],
                "new_count": current + increment,
                "limit": limit,
            },
        )
        return True


async def require_guest_quota(
    request: Request,
    resource_type: ResourceType,
    increment: int = 1,
    current_user: Optional[dict] = None,
) -> None:
    """
    FastAPI dependency that enforces guest quota.

    Raises HTTPException 429 if guest limit is exceeded.
    Authenticated users bypass this check entirely.

    Usage:
        @app.post("/api/jobs")
        async def create_job(
            request: Request,
            current_user: Optional[Dict] = Depends(optional_user),
        ):
            await require_guest_quota(request, "jobs", current_user=current_user)
            # ... rest of endpoint
    """
    # Authenticated users bypass limits
    if current_user:
        return

    # Check guest quota
    allowed = await check_guest_quota(request, resource_type, increment)

    if not allowed:
        limit_map = {
            "jobs": GUEST_LIMITS.MAX_JOBS,
            "cvs": GUEST_LIMITS.MAX_CVS,
            "chat": GUEST_LIMITS.MAX_CHAT_MESSAGES,
            "screenings": GUEST_LIMITS.MAX_SCREENINGS,
        }

        raise HTTPException(
            status_code=429,
            detail={
                "error": f"GUEST_LIMIT_{resource_type.upper()}",
                "message": f"Guest {resource_type} limit reached ({limit_map[resource_type]}). Please sign in to continue.",
                "limit": limit_map[resource_type],
                "resource": resource_type,
                "sign_in_url": "/login",
            },
            headers={
                "Retry-After": str(GUEST_LIMITS.WINDOW_HOURS * 3600),
                "X-RateLimit-Limit": str(limit_map[resource_type]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(
                    int(
                        (
                            datetime.now(timezone.utc)
                            + timedelta(hours=GUEST_LIMITS.WINDOW_HOURS)
                        ).timestamp()
                    )
                ),
            },
        )
