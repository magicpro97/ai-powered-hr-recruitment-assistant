"""
Authentication Module - JWT-based authentication with bcrypt password hashing.
"""

# Standard library imports
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

# Third-party imports
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Local application imports
from src.config import Config
from src.database.postgres_db import PostgresDB, get_db

# ========== TIMEZONE-AWARE DATETIME HELPER ==========


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


# ========== PASSWORD HASHING ==========


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ========== JWT TOKEN MANAGEMENT ==========


def create_access_token(user_id: str, role: str) -> Tuple[str, str]:
    """
    Create JWT with jti for revocation support.
    Returns (token, jti).
    """
    jti = str(uuid4())
    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "exp": utcnow() + timedelta(hours=Config.JWT_EXPIRE_HOURS),
        "iat": utcnow(),
    }
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, {"error": "AUTH_005", "message": "Token expired"})
    except jwt.InvalidTokenError:
        raise HTTPException(401, {"error": "AUTH_006", "message": "Invalid token"})


# ========== SESSION MANAGEMENT ==========


def create_session(
    db: PostgresDB,
    user_id: str,
    jti: str,
    ip_address: str = None,
    user_agent: str = None,
) -> str:
    """Create a new user session."""
    session_id = str(uuid4())
    expires_at = utcnow() + timedelta(hours=Config.JWT_EXPIRE_HOURS)

    db.execute(
        """
        INSERT INTO user_session (id, user_id, token_jti, ip_address, user_agent, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
        (session_id, user_id, jti, ip_address, user_agent, expires_at.isoformat()),
    )

    return session_id


def revoke_session(db: PostgresDB, jti: str, reason: str = "logout"):
    """Revoke a session by its JTI."""
    db.execute(
        """
        UPDATE user_session
        SET is_revoked = TRUE, revoked_at = %s, revoked_reason = %s
        WHERE token_jti = %s
    """,
        (utcnow().isoformat(), reason, jti),
    )


def revoke_all_user_sessions(
    db: PostgresDB, user_id: str, reason: str = "password_changed"
):
    """Revoke all active sessions for a user (e.g., after password change)."""
    db.execute(
        """
        UPDATE user_session
        SET is_revoked = TRUE, revoked_at = %s, revoked_reason = %s
        WHERE user_id = %s AND is_revoked = FALSE
    """,
        (utcnow().isoformat(), reason, user_id),
    )


def is_session_revoked(db: PostgresDB, jti: str) -> bool:
    """Check if a session is revoked."""
    result = db.fetchone(
        "SELECT is_revoked FROM user_session WHERE token_jti = %s", (jti,)
    )
    return result is not None and result["is_revoked"] is True


# ========== USER MANAGEMENT ==========


def get_user_by_email(db: PostgresDB, email: str) -> Optional[Dict[str, Any]]:
    """Get user by email."""
    result = db.fetchone('SELECT * FROM "user" WHERE email = %s', (email.lower(),))
    return dict(result) if result else None


def get_user_by_id(db: PostgresDB, user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    result = db.fetchone('SELECT * FROM "user" WHERE id = %s', (user_id,))
    return dict(result) if result else None


def create_user(
    db: PostgresDB,
    email: str,
    password: str,
    name: str,
    role: str = "user",
    organization: str = None,
) -> Dict[str, Any]:
    """Create a new user."""
    user_id = str(uuid4())
    password_hash = hash_password(password)

    db.execute(
        """
        INSERT INTO "user" (id, email, password_hash, name, role, organization)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
        (user_id, email.lower(), password_hash, name, role, organization),
    )

    return {
        "id": user_id,
        "email": email.lower(),
        "name": name,
        "role": role,
        "organization": organization,
    }


def update_last_login(db: PostgresDB, user_id: str):
    """Update user's last login timestamp."""
    db.execute(
        'UPDATE "user" SET last_login_at = %s WHERE id = %s',
        (utcnow().isoformat(), user_id),
    )


# ========== PASSWORD RESET ==========


def create_password_reset_token(db: PostgresDB, user_id: str) -> str:
    """Create a password reset token."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_id = str(uuid4())
    expires_at = utcnow() + timedelta(hours=1)

    db.execute(
        """
        INSERT INTO password_reset_token (id, user_id, token_hash, expires_at)
        VALUES (%s, %s, %s, %s)
    """,
        (token_id, user_id, token_hash, expires_at.isoformat()),
    )

    return raw_token


def verify_reset_token(db: PostgresDB, token: str) -> Optional[str]:
    """Verify a password reset token. Returns user_id if valid."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    result = db.fetchone(
        """
        SELECT user_id, expires_at, used_at
        FROM password_reset_token
        WHERE token_hash = %s
    """,
        (token_hash,),
    )

    if not result:
        raise HTTPException(
            400, {"error": "AUTH_015", "message": "Invalid reset token"}
        )

    if result["used_at"]:
        raise HTTPException(
            400, {"error": "AUTH_016", "message": "Reset token already used"}
        )

    expires_at = (
        result["expires_at"]
        if isinstance(result["expires_at"], datetime)
        else datetime.fromisoformat(result["expires_at"])
    )
    if expires_at < utcnow():
        raise HTTPException(
            400, {"error": "AUTH_017", "message": "Reset token expired"}
        )

    return result["user_id"]


def mark_reset_token_used(db: PostgresDB, token: str):
    """Mark a reset token as used."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.execute(
        "UPDATE password_reset_token SET used_at = %s WHERE token_hash = %s",
        (utcnow().isoformat(), token_hash),
    )


def reset_password_atomically(db: PostgresDB, token: str, new_password: str) -> str:
    """Claim reset token, update password, and revoke sessions in one transaction.

    CONTRACT CHANGE (intentional): this atomic claim collapses the former
    AUTH_016 (already used) and AUTH_017 (expired) codes into AUTH_015
    (invalid) for the failure case. The single conditional UPDATE
    (used_at IS NULL AND expires_at > NOW()) is what makes the claim atomic and
    immune to the TOCTOU race the old verify-then-update path had. Distinguishing
    used vs expired vs missing would require a second SELECT, which either
    reintroduces that race on the happy path or leaks token state to callers.
    Security (atomicity + no enumeration of token state) is preferred over the
    finer-grained diagnostic codes, so all three failure modes return AUTH_015.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with db.transaction() as conn:
        result = conn.execute(
            """
            UPDATE password_reset_token
            SET used_at = NOW()
            WHERE token_hash = %s AND used_at IS NULL AND expires_at > NOW()
            RETURNING user_id
            """,
            (token_hash,),
        ).fetchone()
        if not result:
            # AUTH_015 intentionally covers missing/used/expired — see docstring.
            raise HTTPException(
                400, {"error": "AUTH_015", "message": "Invalid reset token"}
            )

        user_id = result["user_id"]
        password_hash = hash_password(new_password)
        conn.execute(
            'UPDATE "user" SET password_hash = %s, updated_at = %s WHERE id = %s',
            (password_hash, utcnow().isoformat(), user_id),
        )
        conn.execute(
            """
            UPDATE user_session
            SET is_revoked = TRUE, revoked_at = %s, revoked_reason = %s
            WHERE user_id = %s AND is_revoked = FALSE
            """,
            (utcnow().isoformat(), "password_reset", user_id),
        )

    return user_id


def update_password(db: PostgresDB, user_id: str, new_password: str):
    """Update user's password."""
    password_hash = hash_password(new_password)
    db.execute(
        'UPDATE "user" SET password_hash = %s, updated_at = %s WHERE id = %s',
        (password_hash, utcnow().isoformat(), user_id),
    )


# ========== CLEANUP JOBS ==========


def cleanup_expired_reset_tokens(db: PostgresDB):
    """Remove password reset tokens older than 7 days."""
    db.execute("""
        DELETE FROM password_reset_token
        WHERE expires_at < NOW() - INTERVAL '7 days'
           OR used_at < NOW() - INTERVAL '7 days'
    """)


def cleanup_old_sessions(db: PostgresDB):
    """Remove old sessions (30 days) or revoked sessions (7 days)."""
    db.execute("""
        DELETE FROM user_session
        WHERE created_at < NOW() - INTERVAL '30 days'
           OR (is_revoked = TRUE AND created_at < NOW() - INTERVAL '7 days')
    """)


def run_all_cleanup_jobs(db: PostgresDB):
    """Run all cleanup jobs."""
    cleanup_expired_reset_tokens(db)
    cleanup_old_sessions(db)


# ========== FASTAPI DEPENDENCIES ==========

security = HTTPBearer()


async def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get current user from JWT token with revocation check."""
    db = get_db()
    payload = decode_token(credentials.credentials)

    # Check if token is revoked
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


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require admin role."""
    if current_user["role"] != "admin":
        raise HTTPException(
            403, {"error": "AUTH_008", "message": "Admin access required"}
        )
    return current_user


async def require_recruiter(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require recruiter or admin role."""
    if current_user["role"] not in ("admin", "recruiter"):
        raise HTTPException(
            403, {"error": "AUTH_009", "message": "Recruiter access required"}
        )
    return current_user


async def optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[Dict[str, Any]]:
    """Optionally get current user (for endpoints that work with or without auth)."""
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


# ========== DATA ISOLATION HELPER ==========

ALLOWED_USER_FIELDS = frozenset(
    {"user_id", "created_by_user_id", "uploaded_by_user_id"}
)


def apply_user_filter(
    query: str, current_user: Dict[str, Any], user_field: str = "user_id"
) -> Tuple[str, tuple]:
    """
    Apply user-based data isolation to a query.
    Admin sees all, others see only their own data.
    """
    if user_field not in ALLOWED_USER_FIELDS:
        raise ValueError(
            f"Invalid user field: {user_field}. Allowed: {ALLOWED_USER_FIELDS}"
        )

    if current_user["role"] == "admin":
        return query, ()

    # Add WHERE clause for non-admin users
    if "WHERE" in query.upper():
        filtered_query = query + f" AND {user_field} = %s"
    else:
        # Insert WHERE before ORDER BY, LIMIT, etc.
        order_idx = query.upper().find("ORDER BY")
        limit_idx = query.upper().find("LIMIT")
        insert_idx = min(
            order_idx if order_idx > 0 else len(query),
            limit_idx if limit_idx > 0 else len(query),
        )
        filtered_query = (
            query[:insert_idx] + f" WHERE {user_field} = %s " + query[insert_idx:]
        )

    return filtered_query, (current_user["id"],)
