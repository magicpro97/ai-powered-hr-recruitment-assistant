"""
Security Module - CSRF validation, security headers, and rate limiting dependencies.
Centralizes all security-related dependencies for FastAPI routes.
"""

# Standard library imports
import secrets
from typing import Any, Dict, Optional

# Third-party imports
from fastapi import Depends, HTTPException, Request

# Local application imports
from backend.auth_cookies import (
    CSRF_TOKEN_COOKIE,
    get_current_user_from_cookie,
    optional_user_from_cookie,
)
from backend.logging_config import get_logger
from src.config import Config

logger = get_logger(__name__)


# ========== CSRF PROTECTION ==========


async def validate_csrf_dependency(request: Request) -> None:
    """
    FastAPI Dependency for CSRF validation on state-changing operations.
    Token from cookie must match token in X-CSRF-Token header.

    Use with: Depends(validate_csrf_dependency)
    """
    cookie_csrf = request.cookies.get(CSRF_TOKEN_COOKIE)
    header_csrf = request.headers.get("X-CSRF-Token")

    # Log for debugging
    logger.debug(
        "CSRF validation",
        has_cookie=bool(cookie_csrf),
        has_header=bool(header_csrf),
        path=request.url.path,
    )

    if not cookie_csrf or not header_csrf:
        logger.warning(
            "CSRF token missing",
            path=request.url.path,
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "SECURITY_001",
                "message": "CSRF token missing. Include X-CSRF-Token header.",
            },
        )

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(cookie_csrf, header_csrf):
        logger.warning(
            "CSRF token mismatch",
            path=request.url.path,
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "SECURITY_002",
                "message": "CSRF token mismatch. Refresh and try again.",
            },
        )


async def csrf_protected_user(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_from_cookie),
) -> Dict[str, Any]:
    """
    Combined dependency: Validates CSRF + returns authenticated user.
    Use for authenticated mutations that need CSRF protection.
    """
    await validate_csrf_dependency(request)
    return current_user


async def csrf_protected_optional_user(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(optional_user_from_cookie),
) -> Optional[Dict[str, Any]]:
    """
    Combined dependency: Validates CSRF + returns optional user.
    Use for mutations that work with or without auth (anonymous uploads).

    CSRF is only validated if a CSRF cookie exists (authenticated user).
    Anonymous users without CSRF cookies can still use the endpoint.
    """
    cookie_csrf = request.cookies.get(CSRF_TOKEN_COOKIE)

    # Only validate CSRF if cookie exists (user is authenticated)
    if cookie_csrf:
        await validate_csrf_dependency(request)

    return current_user


# ========== SECURITY HEADERS MIDDLEWARE ==========


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers to all responses.
    Implements OWASP security header recommendations.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Security headers
                security_headers = [
                    # Prevent clickjacking
                    (b"x-frame-options", b"DENY"),
                    # Prevent MIME sniffing
                    (b"x-content-type-options", b"nosniff"),
                    # XSS protection (legacy browsers)
                    (b"x-xss-protection", b"1; mode=block"),
                    # Referrer policy
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    # Permissions policy - disable unnecessary features
                    (
                        b"permissions-policy",
                        b"camera=(), microphone=(), geolocation=()",
                    ),
                    # Content Security Policy
                    (
                        b"content-security-policy",
                        (
                            "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                            f"connect-src 'self' {Config.API_URL.rstrip('/')}; frame-ancestors 'none'"
                        ).encode(),
                    ),
                    # HSTS - enforce HTTPS
                    (
                        b"strict-transport-security",
                        b"max-age=31536000; includeSubDomains",
                    ),
                ]

                headers.extend(security_headers)
                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_wrapper)


# ========== INPUT VALIDATION HELPERS ==========


def validate_text_length(text: str, max_length: int, field_name: str) -> str:
    """Validate text doesn't exceed maximum length."""
    if len(text) > max_length:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "VALIDATION_001",
                "message": f"{field_name} exceeds maximum length of {max_length} characters",
            },
        )
    return text


# ========== AUDIT LOGGING HELPER ==========


def log_security_event(
    event_type: str,
    request: Request,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """Log security-related events for audit trail."""
    logger.warning(
        "security_event",
        event_type=event_type,
        user_id=user_id,
        ip=request.client.host if request.client else None,
        path=request.url.path,
        method=request.method,
        details=details or {},
    )
