"""PostgreSQL storage for the public application flows."""

# Standard library imports
import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# Third-party imports
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


def _ensure_user_role_constraint(conn) -> None:
    """Atomically replace the user-role CHECK with the public roles."""
    conn.execute("""
        DO $$
        DECLARE
            role_constraint TEXT;
        BEGIN
            SELECT conname INTO role_constraint
            FROM pg_constraint
            WHERE conrelid = '"user"'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) ILIKE '%role%'
            LIMIT 1;

            IF role_constraint IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE "user" DROP CONSTRAINT %I',
                    role_constraint
                );
            END IF;

            ALTER TABLE "user"
                ADD CONSTRAINT user_role_check
                CHECK(role IN ('admin', 'recruiter', 'user'));
        END $$;
        """)


class PostgresDB:
    """PostgreSQL database manager with connection pooling."""

    _pool: Optional[ConnectionPool] = None

    def __init__(self):
        self.database_url = os.environ.get("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        self._ensure_pool()

    def _ensure_pool(self):
        """Initialize the shared connection pool once."""
        if PostgresDB._pool is None:
            PostgresDB._pool = ConnectionPool(
                self.database_url,
                min_size=2,
                max_size=10,
                kwargs={"row_factory": dict_row},
            )
            logger.info("PostgreSQL connection pool initialized")

    @contextmanager
    def get_connection(self):
        """Yield a connection and commit or roll back its work."""
        with self._pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def transaction(self):
        """Yield one connection whose work commits or rolls back together."""
        with self.get_connection() as conn:
            yield conn

    def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a query."""
        with self.get_connection() as conn:
            conn.execute(query, params)

    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a query and fetch one row."""
        with self.get_connection() as conn:
            return conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a query and fetch all rows."""
        with self.get_connection() as conn:
            return conn.execute(query, params).fetchall()

    def init_schema(self):
        """Initialize tables used by the six public application flows."""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS "user" (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                        CHECK(role IN ('admin', 'recruiter', 'user')),
                    organization TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    last_login_at TIMESTAMPTZ
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_session (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    token_jti TEXT NOT NULL,
                    refresh_jti TEXT UNIQUE,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMPTZ NOT NULL,
                    is_revoked BOOLEAN DEFAULT FALSE,
                    revoked_at TIMESTAMPTZ,
                    revoked_reason TEXT
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    user_id TEXT REFERENCES "user"(id) ON DELETE SET NULL,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    severity TEXT DEFAULT 'info'
                        CHECK(severity IN ('info', 'warning', 'error', 'critical')),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_token (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    used_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS login_attempt (
                    id SERIAL PRIMARY KEY,
                    email TEXT NOT NULL,
                    ip_address TEXT,
                    success BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS account_lockout (
                    email TEXT PRIMARY KEY,
                    locked_until TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_ownership (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cv_ownership (
                    cv_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS guest_usage (
                    fingerprint_hash TEXT PRIMARY KEY,
                    ip_address TEXT NOT NULL,
                    user_agent_hash TEXT,
                    jobs_count INTEGER DEFAULT 0,
                    cvs_count INTEGER DEFAULT 0,
                    chat_count INTEGER DEFAULT 0,
                    screenings_count INTEGER DEFAULT 0,
                    first_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    last_activity_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    window_start_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interview_question_set (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    cv_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    candidate_name TEXT,
                    questions TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screening_cache (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    user_id TEXT,
                    top_k INTEGER NOT NULL,
                    result JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_refresh_jti
                ON user_session(refresh_jti) WHERE refresh_jti IS NOT NULL
                """)
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_role ON "user"(role)')
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_session_jti ON user_session(token_jti)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_session_user ON user_session(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reset_token_hash ON password_reset_token(token_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reset_token_user ON password_reset_token(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_login_attempt_email_created ON login_attempt(email, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_ownership_user ON job_ownership(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cv_ownership_user ON cv_ownership(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cv_ownership_job ON cv_ownership(job_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_guest_usage_ip ON guest_usage(ip_address)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_guest_usage_window ON guest_usage(window_start_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iq_set_job ON interview_question_set(job_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iq_set_user ON interview_question_set(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_screening_cache_job ON screening_cache(job_id, user_id)"
            )

            _ensure_user_role_constraint(conn)
            logger.info("PostgreSQL schema initialized")


_db_instance: Optional[PostgresDB] = None


def get_db() -> PostgresDB:
    """Get or create the database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = PostgresDB()
        _db_instance.init_schema()
    return _db_instance
