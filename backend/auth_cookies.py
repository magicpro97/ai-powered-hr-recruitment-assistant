"""
Cookie-based Authentication - Dual Token System with HttpOnly Cookies.
Implements secure auth pattern with:
- Access token: 15min, HttpOnly cookie
- Refresh token: 7 days, HttpOnly cookie
- CSRF protection: SameSite=Strict + optional CSRF token for state-changing ops
"""

# Standard library imports
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

# Third-party imports
import jwt
from fastapi import Depends, HTTPException, Request, Response

# Local application imports
from backend.cookie_policy import cookie_transport_for_frontend
from src.config import Config
from src.database.postgres_db import PostgresDB, get_db

# ========== CONSTANTS ==========

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
CSRF_TOKEN_EXPIRE_HOURS = 24

# Cookie names
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
CSRF_TOKEN_COOKIE = "csrf_token"

# Cookie settings
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)  # e.g. ".example.test" in production
COOKIE_SECURE, COOKIE_EFFECTIVE_DOMAIN = cookie_transport_for_frontend(
    Config.FRONTEND_URL, COOKIE_DOMAIN
)

COOKIE_SETTINGS = {
    "httponly": True,
    "secure": COOKIE_SECURE,
    "samesite": "lax",
    "path": "/",
}


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ========== TOKEN CREATION ==========


def create_access_token_v2(user_id: str, role: str) -> Tuple[str, str, datetime]:
    """
    Create short-lived access token (15 min).
    Returns: (token, jti, expires_at)
    """
    jti = str(uuid4())
    expires_at = utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "type": "access",
        "exp": expires_at,
        "iat": utcnow(),
    }
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)
    return token, jti, expires_at


def create_refresh_token(user_id: str) -> Tuple[str, str, datetime]:
    """
    Create long-lived refresh token (7 days).
    Returns: (token, jti, expires_at)
    """
    jti = str(uuid4())
    expires_at = utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": "refresh",
        "exp": expires_at,
        "iat": utcnow(),
    }
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)
    return token, jti, expires_at


def create_csrf_token() -> str:
    """Create a CSRF token for state-changing operations."""
    return secrets.token_urlsafe(32)


# ========== TOKEN VALIDATION ==========


def decode_token_v2(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Decode and validate a JWT token with type checking."""
    try:
        payload = jwt.decode(
            token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM]
        )

        # Verify token type
        if payload.get("type") != expected_type:
            raise HTTPException(
                401,
                {
                    "error": "AUTH_020",
                    "message": f"Invalid token type, expected {expected_type}",
                },
            )

        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, {"error": "AUTH_005", "message": "Token expired"})
    except jwt.InvalidTokenError:
        raise HTTPException(401, {"error": "AUTH_006", "message": "Invalid token"})


def get_token_from_cookie(request: Request, cookie_name: str) -> Optional[str]:
    """Extract token from HttpOnly cookie."""
    return request.cookies.get(cookie_name)


# ========== COOKIE HELPERS ==========


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_expires: datetime,
    refresh_expires: datetime,
    csrf_token: Optional[str] = None,
):
    """Set authentication cookies on response."""
    # Access token cookie
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=int((access_expires - utcnow()).total_seconds()),
        **COOKIE_SETTINGS,
        domain=COOKIE_EFFECTIVE_DOMAIN,
    )

    # Refresh token cookie - longer lived, more restrictive path
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=int((refresh_expires - utcnow()).total_seconds()),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/api/auth",  # Only sent to auth endpoints
        domain=COOKIE_EFFECTIVE_DOMAIN,
    )

    # CSRF token - NOT HttpOnly so JS can read it for headers
    if csrf_token:
        response.set_cookie(
            key=CSRF_TOKEN_COOKIE,
            value=csrf_token,
            max_age=CSRF_TOKEN_EXPIRE_HOURS * 3600,
            httponly=False,  # JS needs to read this
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/",
            domain=COOKIE_EFFECTIVE_DOMAIN,
        )


def clear_auth_cookies(response: Response):
    """Clear all authentication cookies."""
    domain_kwargs = {"domain": COOKIE_DOMAIN} if COOKIE_DOMAIN else {}
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", **domain_kwargs)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/api/auth", **domain_kwargs)
    response.delete_cookie(CSRF_TOKEN_COOKIE, path="/", **domain_kwargs)
    if domain_kwargs:
        response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
        response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/api/auth")
        response.delete_cookie(CSRF_TOKEN_COOKIE, path="/")


# ========== SESSION MANAGEMENT ==========


def create_session_v2(
    db: PostgresDB,
    user_id: str,
    access_jti: str,
    refresh_jti: str,
    ip_address: str = None,
    user_agent: str = None,
) -> str:
    """Create a new user session with both token JTIs."""
    session_id = str(uuid4())
    expires_at = utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db.execute(
        """
        INSERT INTO user_session (id, user_id, token_jti, refresh_jti, ip_address, user_agent, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            session_id,
            user_id,
            access_jti,
            refresh_jti,
            ip_address,
            user_agent,
            expires_at.isoformat(),
        ),
    )

    return session_id


def update_session_access_token(db: PostgresDB, refresh_jti: str, new_access_jti: str):
    """Update session with new access token JTI after refresh."""
    # Local application imports
    from backend.datetime_utils import utcnow

    db.execute(
        """
        UPDATE user_session
        SET token_jti = %s, updated_at = %s
        WHERE refresh_jti = %s AND is_revoked = FALSE
        """,
        (new_access_jti, utcnow().isoformat(), refresh_jti),
    )


def is_refresh_token_valid(db: PostgresDB, refresh_jti: str) -> Optional[str]:
    """
    Check if refresh token is valid and not revoked.
    Returns user_id if valid, None otherwise.
    """
    result = db.fetchone(
        """
        SELECT user_id, is_revoked, expires_at
        FROM user_session
        WHERE refresh_jti = %s
        """,
        (refresh_jti,),
    )

    if not result:
        return None

    if result["is_revoked"]:
        return None

    # Check expiration
    expires_at = result["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < utcnow():
        return None

    return result["user_id"]


def revoke_session_by_refresh(db: PostgresDB, refresh_jti: str, reason: str = "logout"):
    """Revoke a session using its refresh token JTI."""
    db.execute(
        """
        UPDATE user_session
        SET is_revoked = TRUE, revoked_at = %s, revoked_reason = %s
        WHERE refresh_jti = %s
        """,
        (utcnow().isoformat(), reason, refresh_jti),
    )


# ========== CSRF VALIDATION ==========


def validate_csrf_token(request: Request):
    """
    Validate CSRF token for state-changing operations.
    Token from cookie must match token in header.
    """
    cookie_csrf = request.cookies.get(CSRF_TOKEN_COOKIE)
    header_csrf = request.headers.get("X-CSRF-Token")

    if not cookie_csrf or not header_csrf:
        raise HTTPException(403, {"error": "AUTH_021", "message": "CSRF token missing"})

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(cookie_csrf, header_csrf):
        raise HTTPException(
            403, {"error": "AUTH_022", "message": "CSRF token mismatch"}
        )


# ========== DEPENDENCY FUNCTIONS ==========


async def get_current_user_from_cookie(request: Request) -> Dict[str, Any]:
    """
    Get current user from access token cookie.
    Falls back to Authorization header for API clients.
    """
    # Local application imports
    from backend.auth import get_user_by_id, is_session_revoked

    db = get_db()
    token = None

    # Try cookie first
    token = get_token_from_cookie(request, ACCESS_TOKEN_COOKIE)

    # Fallback to Authorization header for API clients
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(401, {"error": "AUTH_023", "message": "Not authenticated"})

    # Decode token
    payload = decode_token_v2(token, expected_type="access")

    # Check if session is revoked
    jti = payload.get("jti")
    if jti and is_session_revoked(db, jti):
        raise HTTPException(
            401, {"error": "AUTH_014", "message": "Token has been revoked"}
        )

    # Get user
    user = get_user_by_id(db, payload["sub"])
    if not user or not user["is_active"]:
        raise HTTPException(
            401, {"error": "AUTH_007", "message": "User not found or inactive"}
        )

    return user


async def optional_user_from_cookie(request: Request) -> Optional[Dict[str, Any]]:
    """Optionally get current user (for endpoints that work with or without auth)."""
    try:
        return await get_current_user_from_cookie(request)
    except HTTPException:
        return None


async def require_admin_cookie(
    current_user: Dict[str, Any] = Depends(get_current_user_from_cookie),
) -> Dict[str, Any]:
    """Require admin role (cookie-based auth)."""
    if current_user["role"] != "admin":
        raise HTTPException(
            403, {"error": "AUTH_008", "message": "Admin access required"}
        )
    return current_user


async def require_recruiter_cookie(
    current_user: Dict[str, Any] = Depends(get_current_user_from_cookie),
) -> Dict[str, Any]:
    """Require recruiter or admin role (cookie-based auth)."""
    if current_user["role"] not in ("admin", "recruiter"):
        raise HTTPException(
            403, {"error": "AUTH_009", "message": "Recruiter access required"}
        )
    return current_user
