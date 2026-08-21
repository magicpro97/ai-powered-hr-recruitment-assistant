"""
Cookie-based Authentication Routes - Secure dual token endpoints.
All auth operations use HttpOnly cookies for token storage.
"""

# Standard library imports
import os
import re
from typing import Optional

# Third-party imports
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, EmailStr, Field, field_validator

# Local application imports
from backend.audit_logger import log_audit_event
from backend.auth import (
    create_password_reset_token,
    create_user,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    reset_password_atomically,
    revoke_all_user_sessions,
    update_last_login,
    verify_password,
)
from backend.auth_cookies import (
    REFRESH_TOKEN_COOKIE,
    clear_auth_cookies,
    create_access_token_v2,
    create_csrf_token,
    create_refresh_token,
    create_session_v2,
    decode_token_v2,
    get_current_user_from_cookie,
    get_token_from_cookie,
    is_refresh_token_valid,
    revoke_session_by_refresh,
    set_auth_cookies,
    validate_csrf_token,
)
from backend.brute_force import (
    get_account_status,
    is_account_locked,
    record_failed_login,
    record_successful_login,
)
from backend.datetime_utils import format_dt, format_row_dates, utcnow
from backend.guest_token import get_guest_token, migrate_guest_data
from backend.limiter import limiter
from backend.logging_config import get_logger
from backend.sanitization import sanitize_user_input
from src.database.postgres_db import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth/v2", tags=["auth-v2"])


# ========== PASSWORD VALIDATION ==========


def validate_password_complexity(password: str) -> str:
    """Validate password meets complexity requirements."""
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one digit")
    return password


# ========== REQUEST MODELS ==========


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    organization: Optional[str] = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    guest_token: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_complexity(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_complexity(v)


# ========== HELPER ==========


def get_client_info(request: Request) -> tuple:
    """Extract client IP and user agent from request."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:500]  # Limit length
    return ip_address, user_agent


# ========== AUTH ENDPOINTS ==========


@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, response: Response, data: RegisterRequest):
    """
    Register a new user account.
    Does NOT auto-login - user must login separately.
    """
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    # Sanitize inputs
    sanitized_name = sanitize_user_input(data.name)
    sanitized_org = (
        sanitize_user_input(data.organization) if data.organization else None
    )

    logger.info(
        "User registration attempt",
        email=data.email,
        ip=ip_address,
    )

    # Check if email exists
    if get_user_by_email(db, data.email):
        logger.warning(
            "Registration failed - email exists", email=data.email, ip=ip_address
        )
        log_audit_event(
            db=db,
            action="register_failed",
            details={"reason": "email_exists", "email": data.email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            400, {"error": "AUTH_001", "message": "Email already registered"}
        )

    # Create user
    user = create_user(
        db=db,
        email=data.email,
        password=data.password,
        name=sanitized_name,
        role="user",
        organization=sanitized_org,
    )

    logger.info("User registered successfully", user_id=user["id"], email=user["email"])
    log_audit_event(
        db=db,
        action="register",
        user_id=user["id"],
        details={"email": user["email"]},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {
        "success": True,
        "message": "Registration successful. Please login.",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        },
    }


@router.post("/account-status")
@limiter.limit("20/minute")
async def check_account_status(request: Request, data: LoginRequest):
    """
    Check if an account is locked due to failed login attempts.
    Returns lockout status without requiring authentication.
    Used by frontend to show appropriate UI.
    """
    db = get_db()
    status = get_account_status(db, data.email)
    return status


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, response: Response, data: LoginRequest):
    """
    Login with email and password.
    Sets HttpOnly cookies for access_token, refresh_token, and csrf_token.
    Implements brute force protection with account lockout.
    """
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    logger.info("Login attempt", email=data.email, ip=ip_address)

    # Check if account is locked
    is_locked, locked_until = is_account_locked(db, data.email)
    if is_locked:
        logger.warning(
            "Login blocked - account locked",
            email=data.email,
            locked_until=locked_until.isoformat() if locked_until else None,
            ip=ip_address,
        )
        log_audit_event(
            db=db,
            action="login_blocked",
            details={"reason": "account_locked", "email": data.email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            423,
            {
                "error": "AUTH_030",
                "message": "Account is temporarily locked due to too many failed attempts",
                "locked_until": format_dt(locked_until),
            },
        )

    # Get user
    user = get_user_by_email(db, data.email)
    if not user:
        # Record failed attempt even for non-existent users (prevents enumeration)
        record_failed_login(db, data.email, ip_address)
        logger.warning("Login failed - user not found", email=data.email, ip=ip_address)
        log_audit_event(
            db=db,
            action="login_failed",
            details={"reason": "user_not_found", "email": data.email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            401, {"error": "AUTH_002", "message": "Invalid email or password"}
        )

    # Check if active
    if not user["is_active"]:
        logger.warning(
            "Login failed - account deactivated", user_id=user["id"], ip=ip_address
        )
        log_audit_event(
            db=db,
            action="login_failed",
            user_id=user["id"],
            details={"reason": "account_deactivated"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            403, {"error": "AUTH_003", "message": "Account is deactivated"}
        )

    # Verify password
    if not verify_password(data.password, user["password_hash"]):
        # Record failed attempt
        failed_count = record_failed_login(db, data.email, ip_address)
        logger.warning(
            "Login failed - invalid password",
            user_id=user["id"],
            failed_attempts=failed_count,
            ip=ip_address,
        )
        log_audit_event(
            db=db,
            action="login_failed",
            user_id=user["id"],
            details={"reason": "invalid_password", "failed_attempts": failed_count},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            401, {"error": "AUTH_002", "message": "Invalid email or password"}
        )

    # Successful login - clear any lockout and record success
    record_successful_login(db, data.email, ip_address)

    # Create tokens
    access_token, access_jti, access_expires = create_access_token_v2(
        user["id"], user["role"]
    )
    refresh_token, refresh_jti, refresh_expires = create_refresh_token(user["id"])
    csrf_token = create_csrf_token()

    # Create session
    create_session_v2(db, user["id"], access_jti, refresh_jti, ip_address, user_agent)

    # Update last login
    update_last_login(db, user["id"])

    # Set cookies using trusted frontend configuration.
    set_auth_cookies(
        response=response,
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires=access_expires,
        refresh_expires=refresh_expires,
        csrf_token=csrf_token,
    )

    logger.info(
        "Login successful", user_id=user["id"], email=user["email"], ip=ip_address
    )
    log_audit_event(
        db=db,
        action="login",
        user_id=user["id"],
        details={"email": user["email"]},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Migrate guest data if guest_token provided (or from header)
    gt = data.guest_token or get_guest_token(request)
    migrated = None
    if gt:
        migrated = migrate_guest_data(db, gt, user["id"])
        if migrated and (migrated["jobs"] > 0 or migrated["cvs"] > 0):
            log_audit_event(
                db=db,
                action="guest_data_migrated",
                user_id=user["id"],
                details={"guest_token": gt[:8], **migrated},
                ip_address=ip_address,
                user_agent=user_agent,
            )

    # Return user info (NO token in body - it's in cookies)
    result = {
        "success": True,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "organization": user.get("organization"),
        },
    }
    if migrated and (migrated["jobs"] > 0 or migrated["cvs"] > 0):
        result["migrated"] = migrated
    return result


@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh_tokens(request: Request, response: Response):
    """
    Refresh access token using refresh token from cookie.
    Issues new access token and rotates refresh token for security.
    """
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    # Get refresh token from cookie
    refresh_token = get_token_from_cookie(request, REFRESH_TOKEN_COOKIE)
    if not refresh_token:
        raise HTTPException(401, {"error": "AUTH_024", "message": "No refresh token"})

    # Decode and validate refresh token
    try:
        payload = decode_token_v2(refresh_token, expected_type="refresh")
    except HTTPException as e:
        clear_auth_cookies(response)
        raise e

    refresh_jti = payload.get("jti")
    user_id = payload.get("sub")

    # Check if refresh token is still valid in DB
    valid_user_id = is_refresh_token_valid(db, refresh_jti)
    if not valid_user_id or valid_user_id != user_id:
        clear_auth_cookies(response)
        log_audit_event(
            db=db,
            action="refresh_failed",
            user_id=user_id,
            details={"reason": "invalid_refresh_token"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            401, {"error": "AUTH_025", "message": "Invalid refresh token"}
        )

    # Get user
    user = get_user_by_id(db, user_id)
    if not user or not user["is_active"]:
        clear_auth_cookies(response)
        raise HTTPException(
            401, {"error": "AUTH_007", "message": "User not found or inactive"}
        )

    # Revoke old refresh token
    revoke_session_by_refresh(db, refresh_jti, reason="token_refresh")

    # Create new tokens (token rotation)
    new_access_token, new_access_jti, access_expires = create_access_token_v2(
        user["id"], user["role"]
    )
    new_refresh_token, new_refresh_jti, refresh_expires = create_refresh_token(
        user["id"]
    )
    csrf_token = create_csrf_token()

    # Create new session
    create_session_v2(
        db, user["id"], new_access_jti, new_refresh_jti, ip_address, user_agent
    )

    # Set new cookies
    set_auth_cookies(
        response=response,
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        access_expires=access_expires,
        refresh_expires=refresh_expires,
        csrf_token=csrf_token,
    )

    logger.debug("Tokens refreshed", user_id=user["id"], ip=ip_address)

    return {"success": True, "message": "Tokens refreshed"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Logout current session. Clears cookies and revokes refresh token.
    """
    validate_csrf_token(request)
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    # Try to get user info for audit
    user_id = None
    try:
        user = await get_current_user_from_cookie(request)
        user_id = user["id"]
    except HTTPException:
        pass

    # Revoke refresh token if present
    refresh_token = get_token_from_cookie(request, REFRESH_TOKEN_COOKIE)
    if refresh_token:
        try:
            payload = decode_token_v2(refresh_token, expected_type="refresh")
            revoke_session_by_refresh(db, payload.get("jti"), reason="logout")
        except HTTPException:
            pass  # Token already invalid, just clear cookies

    # Clear all auth cookies
    clear_auth_cookies(response)

    if user_id:
        logger.info("Logout successful", user_id=user_id, ip=ip_address)
        log_audit_event(
            db=db,
            action="logout",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    return {"success": True, "message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all_sessions(request: Request, response: Response):
    """
    Logout all sessions for current user. Requires valid access token.
    """
    validate_csrf_token(request)
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    # Must be authenticated
    user = await get_current_user_from_cookie(request)

    # Revoke all sessions
    revoke_all_user_sessions(db, user["id"], reason="logout_all")

    # Clear cookies
    clear_auth_cookies(response)

    logger.info("All sessions revoked", user_id=user["id"], ip=ip_address)
    log_audit_event(
        db=db,
        action="logout_all",
        user_id=user["id"],
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"success": True, "message": "All sessions revoked"}


@router.get("/me")
async def get_me(request: Request):
    """Get current user info from cookie."""
    user = await get_current_user_from_cookie(request)
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "organization": user.get("organization"),
        "created_at": format_dt(user.get("created_at")),
        "last_login_at": format_dt(user.get("last_login_at")),
    }


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request, data: ForgotPasswordRequest, background_tasks: BackgroundTasks
):
    """Request password reset. Always returns success to prevent email enumeration."""
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    sanitized_email = sanitize_user_input(data.email)
    logger.info("Password reset requested", email=sanitized_email, ip=ip_address)

    user = get_user_by_email(db, sanitized_email)

    response = {
        "success": True,
        "message": "If email exists, reset instructions will be sent",
    }

    if not user:
        log_audit_event(
            db=db,
            action="forgot_password",
            details={"email": sanitized_email, "found": False},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return response

    if not user["is_active"]:
        log_audit_event(
            db=db,
            action="forgot_password",
            user_id=user["id"],
            details={"reason": "account_inactive"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return response

    # Create reset token
    reset_token = create_password_reset_token(db, user["id"])

    logger.info(
        "Password reset token created",
        user_id=user["id"],
        email=user["email"],
        # token intentionally omitted from logs for security
    )

    log_audit_event(
        db=db,
        action="forgot_password",
        user_id=user["id"],
        details={"email": user["email"]},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Send reset email in background
    # Local application imports
    from backend.email_service import is_email_configured, send_reset_email

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    if is_email_configured():
        background_tasks.add_task(
            send_reset_email, user["email"], reset_token, frontend_url
        )
    else:
        logger.warning(
            "SMTP not configured — reset token created but email not sent for %s",
            user["email"],
        )

    return response


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request, response: Response, data: ResetPasswordRequest
):
    """Reset password using token. Invalidates all sessions."""
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    sanitized_token = sanitize_user_input(data.token)
    logger.info("Password reset attempt", ip=ip_address)

    user_id = reset_password_atomically(db, sanitized_token, data.new_password)

    # Clear any existing cookies
    clear_auth_cookies(response)

    logger.info("Password reset completed", user_id=user_id, ip=ip_address)
    log_audit_event(
        db=db,
        action="password_reset",
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {
        "success": True,
        "message": "Password updated. Please login with new password.",
    }


@router.post("/change-password")
async def change_password(
    request: Request, response: Response, data: ChangePasswordRequest
):
    """Change password for logged-in user. Revokes other sessions."""
    db = get_db()
    ip_address, user_agent = get_client_info(request)

    # Validate CSRF
    validate_csrf_token(request)

    # Must be authenticated
    user = await get_current_user_from_cookie(request)

    logger.info("Password change attempt", user_id=user["id"], ip=ip_address)

    # Verify current password
    if not verify_password(data.current_password, user["password_hash"]):
        logger.warning(
            "Password change failed - wrong password", user_id=user["id"], ip=ip_address
        )
        log_audit_event(
            db=db,
            action="change_password_failed",
            user_id=user["id"],
            details={"reason": "wrong_current_password"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(
            400, {"error": "AUTH_010", "message": "Current password is incorrect"}
        )

    # Update password
    # Get current session's refresh JTI before transaction
    refresh_token = get_token_from_cookie(request, REFRESH_TOKEN_COOKIE)
    current_refresh_jti = None
    if refresh_token:
        try:
            payload = decode_token_v2(refresh_token, expected_type="refresh")
            current_refresh_jti = payload.get("jti")
        except HTTPException:
            pass

    # Atomic: update password + revoke other sessions in one transaction
    with db.transaction() as conn:
        password_hash = hash_password(data.new_password)
        conn.execute(
            'UPDATE "user" SET password_hash = %s, updated_at = %s WHERE id = %s',
            (password_hash, utcnow().isoformat(), user["id"]),
        )

        if current_refresh_jti:
            conn.execute(
                """
                UPDATE user_session
                SET is_revoked = TRUE, revoked_at = %s, revoked_reason = 'password_changed'
                WHERE user_id = %s AND is_revoked = FALSE AND refresh_jti != %s
                """,
                (utcnow().isoformat(), user["id"], current_refresh_jti),
            )
        else:
            conn.execute(
                """
                UPDATE user_session
                SET is_revoked = TRUE, revoked_at = %s, revoked_reason = %s
                WHERE user_id = %s AND is_revoked = FALSE
                """,
                (utcnow().isoformat(), "password_changed", user["id"]),
            )
            clear_auth_cookies(response)

    logger.info("Password changed", user_id=user["id"], ip=ip_address)
    log_audit_event(
        db=db,
        action="change_password",
        user_id=user["id"],
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"success": True, "message": "Password changed successfully"}


@router.get("/sessions")
async def list_sessions(request: Request):
    """List active sessions for current user."""
    user = await get_current_user_from_cookie(request)
    db = get_db()

    sessions = db.fetchall(
        """
        SELECT id, ip_address, user_agent, created_at, expires_at
        FROM user_session
        WHERE user_id = %s AND is_revoked = FALSE AND expires_at > NOW() AT TIME ZONE 'UTC'
        ORDER BY created_at DESC
        """,
        (user["id"],),
    )

    return {
        "sessions": [
            format_row_dates(dict(s), "created_at", "expires_at") for s in sessions
        ]
    }


@router.delete("/sessions/{session_id}")
async def revoke_session_by_id(session_id: str, request: Request):
    """Revoke a specific session."""
    # Validate CSRF
    validate_csrf_token(request)

    user = await get_current_user_from_cookie(request)
    db = get_db()
    ip_address, _ = get_client_info(request)

    # Check session belongs to user
    session = db.fetchone(
        "SELECT refresh_jti FROM user_session WHERE id = %s AND user_id = %s",
        (session_id, user["id"]),
    )

    if not session:
        raise HTTPException(404, {"error": "AUTH_011", "message": "Session not found"})

    # Revoke session
    revoke_session_by_refresh(db, session["refresh_jti"], reason="user_revoked")

    log_audit_event(
        db=db,
        action="revoke_session",
        user_id=user["id"],
        details={"session_id": session_id},
        ip_address=ip_address,
    )

    return {"success": True, "message": "Session revoked"}


# ========== HEALTH CHECK ==========


@router.get("/status")
async def auth_status(request: Request):
    """Check authentication status without requiring valid token."""
    try:
        user = await get_current_user_from_cookie(request)
        return {
            "authenticated": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }
    except HTTPException:
        return {"authenticated": False, "user": None}
