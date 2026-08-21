"""
Brute Force Protection Module - Account lockout after failed login attempts.
Implements secure login attempt tracking with configurable lockout duration.
"""

# Standard library imports
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

# Local application imports
from backend.datetime_utils import format_dt
from backend.logging_config import get_logger
from src.database.postgres_db import PostgresDB

logger = get_logger(__name__)

# ========== CONFIGURATION ==========

MAX_FAILED_ATTEMPTS = 5  # Lock after 5 failed attempts
LOCKOUT_DURATION_MINUTES = 15  # Lock for 15 minutes
ATTEMPT_WINDOW_MINUTES = 30  # Count failures within 30 min window


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ========== FAILED ATTEMPT TRACKING ==========


def record_failed_login(db: PostgresDB, email: str, ip_address: str) -> int:
    """
    Record a failed login attempt for an email.
    Returns the current count of failed attempts in the window.
    """
    window_start = (utcnow() - timedelta(minutes=ATTEMPT_WINDOW_MINUTES)).isoformat()

    # Insert failed attempt record
    db.execute(
        """
        INSERT INTO login_attempt (email, ip_address, success, created_at)
        VALUES (%s, %s, FALSE, %s)
        """,
        (email.lower(), ip_address, utcnow().isoformat()),
    )

    # Count recent failures
    result = db.fetchone(
        """
        SELECT COUNT(*) as count FROM login_attempt
        WHERE email = %s AND success = FALSE AND created_at > %s
        """,
        (email.lower(), window_start),
    )

    count = result["count"] if result else 0

    # If threshold reached, set lockout
    if count >= MAX_FAILED_ATTEMPTS:
        set_account_lockout(db, email)
        logger.warning(
            "Account locked due to failed attempts",
            email=email,
            attempts=count,
            ip=ip_address,
        )

    return count


def record_successful_login(db: PostgresDB, email: str, ip_address: str):
    """
    Record a successful login and clear lockout.
    """
    # Record success
    db.execute(
        """
        INSERT INTO login_attempt (email, ip_address, success, created_at)
        VALUES (%s, %s, TRUE, %s)
        """,
        (email.lower(), ip_address, utcnow().isoformat()),
    )

    # Clear any existing lockout
    clear_account_lockout(db, email)


def set_account_lockout(db: PostgresDB, email: str):
    """Set account lockout timestamp."""
    lockout_until = utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)

    db.execute(
        """
        INSERT INTO account_lockout (email, locked_until, created_at)
        VALUES (%s, %s, %s)
        ON CONFLICT(email) DO UPDATE SET locked_until = excluded.locked_until
        """,
        (email.lower(), lockout_until.isoformat(), utcnow().isoformat()),
    )


def clear_account_lockout(db: PostgresDB, email: str):
    """Clear account lockout."""
    db.execute(
        "DELETE FROM account_lockout WHERE email = %s",
        (email.lower(),),
    )

    # Also clear old failed attempts
    db.execute(
        "DELETE FROM login_attempt WHERE email = %s AND success = FALSE",
        (email.lower(),),
    )


def is_account_locked(db: PostgresDB, email: str) -> Tuple[bool, Optional[datetime]]:
    """
    Check if account is locked.
    Returns (is_locked, locked_until_datetime).
    """
    result = db.fetchone(
        "SELECT locked_until FROM account_lockout WHERE email = %s",
        (email.lower(),),
    )

    if not result:
        return False, None

    locked_until = result["locked_until"]
    if isinstance(locked_until, str):
        locked_until = datetime.fromisoformat(locked_until)

    # Ensure timezone aware
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    # Check if still locked
    if locked_until > utcnow():
        return True, locked_until

    # Lockout expired, clear it
    clear_account_lockout(db, email)
    return False, None


def get_remaining_lockout_seconds(db: PostgresDB, email: str) -> int:
    """Get remaining lockout time in seconds."""
    is_locked, locked_until = is_account_locked(db, email)

    if not is_locked or not locked_until:
        return 0

    remaining = (locked_until - utcnow()).total_seconds()
    return max(0, int(remaining))


def get_account_status(db: PostgresDB, email: str) -> Dict:
    """
    Get account lockout status for display.
    Returns dict with lockout info.
    """
    is_locked, locked_until = is_account_locked(db, email)

    if not is_locked:
        # Count recent failures
        window_start = (
            utcnow() - timedelta(minutes=ATTEMPT_WINDOW_MINUTES)
        ).isoformat()
        result = db.fetchone(
            """
            SELECT COUNT(*) as count FROM login_attempt
            WHERE email = %s AND success = FALSE AND created_at > %s
            """,
            (email.lower(), window_start),
        )
        failed_attempts = result["count"] if result else 0

        return {
            "locked": False,
            "failed_attempts": failed_attempts,
            "max_attempts": MAX_FAILED_ATTEMPTS,
            "remaining_attempts": max(0, MAX_FAILED_ATTEMPTS - failed_attempts),
        }

    return {
        "locked": True,
        "locked_until": format_dt(locked_until),
        "remaining_seconds": get_remaining_lockout_seconds(db, email),
        "lockout_duration_minutes": LOCKOUT_DURATION_MINUTES,
    }
