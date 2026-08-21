"""
Audit Logging System - Track security-relevant events for compliance and debugging.

Events logged:
- Authentication: login, logout, register, password changes
- Authorization: access denied, role changes
- Data: sensitive data access, modifications
- Security: suspicious activity, rate limiting
"""

# Standard library imports
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

# Local application imports
from src.database.postgres_db import PostgresDB


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def log_audit_event(
    db: PostgresDB,
    action: str,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    severity: str = "info",
):
    """
    Log an audit event to the database.

    Args:
        db: Database connection
        action: Event type (e.g., 'login', 'logout', 'access_denied')
        user_id: User who performed the action (None for unauthenticated)
        target_type: Type of resource affected (e.g., 'job', 'cv', 'user')
        target_id: ID of the affected resource
        details: Additional context as JSON-serializable dict
        ip_address: Client IP address
        user_agent: Client user agent string
        severity: Log level ('info', 'warning', 'error', 'critical')
    """
    # Standard library imports
    import json

    event_id = str(uuid4())

    try:
        db.execute(
            """
            INSERT INTO audit_log (
                id, user_id, action, target_type, target_id,
                details, ip_address, user_agent, severity, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_id,
                user_id,
                action,
                target_type,
                target_id,
                json.dumps(details) if details else None,
                ip_address,
                user_agent[:500] if user_agent else None,  # Limit length
                severity,
                utcnow().isoformat(),
            ),
        )
    except Exception as e:
        # Don't let audit logging failures break the application
        logging.getLogger(__name__).error("Failed to log audit event", exc_info=e)


def get_audit_logs(
    db: PostgresDB,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Query audit logs with filters.

    Returns list of audit events matching criteria.
    """
    query = """
        SELECT id, user_id, action, target_type, target_id,
               details, ip_address, user_agent, severity, created_at
        FROM audit_log
        WHERE 1=1
    """
    params = []

    if user_id:
        query += " AND user_id = %s"
        params.append(user_id)

    if action:
        query += " AND action = %s"
        params.append(action)

    if severity:
        query += " AND severity = %s"
        params.append(severity)

    if start_date:
        query += " AND created_at >= %s"
        params.append(start_date.isoformat())

    if end_date:
        query += " AND created_at <= %s"
        params.append(end_date.isoformat())

    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    results = db.fetchall(query, tuple(params))
    return [dict(r) for r in results]


def get_audit_stats(
    db: PostgresDB,
    days: int = 7,
):
    """
    Get audit statistics for dashboard.

    Returns aggregated counts by action type and severity.
    """
    query = """
        SELECT
            action,
            severity,
            COUNT(*) as count
        FROM audit_log
        WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
        GROUP BY action, severity
        ORDER BY count DESC
    """

    results = db.fetchall(query, (days,))
    return [dict(r) for r in results]


def cleanup_old_audit_logs(db: PostgresDB, retention_days: int = 90):
    """
    Remove audit logs older than retention period.
    Called by scheduled cleanup job.
    """
    db.execute(
        """
        DELETE FROM audit_log
        WHERE created_at < NOW() - (%s * INTERVAL '1 day')
        """,
        (retention_days,),
    )


# ========== AUDIT EVENT TYPES ==========

# Authentication events
AUDIT_LOGIN = "login"
AUDIT_LOGIN_FAILED = "login_failed"
AUDIT_LOGOUT = "logout"
AUDIT_LOGOUT_ALL = "logout_all"
AUDIT_REGISTER = "register"
AUDIT_REGISTER_FAILED = "register_failed"

# Password events
AUDIT_PASSWORD_CHANGE = "change_password"
AUDIT_PASSWORD_CHANGE_FAILED = "change_password_failed"
AUDIT_PASSWORD_RESET = "password_reset"
AUDIT_FORGOT_PASSWORD = "forgot_password"

# Session events
AUDIT_REFRESH_TOKEN = "refresh_token"
AUDIT_REFRESH_FAILED = "refresh_failed"
AUDIT_REVOKE_SESSION = "revoke_session"

# Authorization events
AUDIT_ACCESS_DENIED = "access_denied"
AUDIT_ROLE_CHANGED = "role_changed"
AUDIT_USER_DEACTIVATED = "user_deactivated"
AUDIT_USER_ACTIVATED = "user_activated"

# Data events
AUDIT_JOB_CREATED = "job_created"
AUDIT_JOB_DELETED = "job_deleted"
AUDIT_CV_UPLOADED = "cv_uploaded"
AUDIT_CV_DELETED = "cv_deleted"
AUDIT_EVALUATION_CREATED = "evaluation_created"

# Security events
AUDIT_RATE_LIMITED = "rate_limited"
AUDIT_SUSPICIOUS_ACTIVITY = "suspicious_activity"
AUDIT_CSRF_FAILED = "csrf_failed"
