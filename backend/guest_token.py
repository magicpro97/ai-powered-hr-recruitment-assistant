"""
Guest Token Utilities — track guest-created data for migration on login.

Guest users receive a UUID token (stored in localStorage, sent as X-Guest-Token header).
When a guest creates jobs/CVs, data is tagged with `guest_{token}` as owner.
On login, `migrate_guest_data()` transfers ownership to the authenticated user.
"""

# Standard library imports
import logging
from typing import Optional

# Third-party imports
from fastapi import Request

# Local application imports
from src.database.postgres_db import PostgresDB
from src.database.vector_store import VectorStore

logger = logging.getLogger(__name__)

GUEST_OWNER_PREFIX = "guest_"


def get_guest_token(request: Request) -> Optional[str]:
    """Extract guest token from X-Guest-Token header."""
    return request.headers.get("X-Guest-Token")


def guest_owner_id(token: str) -> str:
    """Convert guest token to owner_user_id format."""
    return f"{GUEST_OWNER_PREFIX}{token}"


def is_guest_owner(owner_id: str) -> bool:
    """Check if an owner_user_id belongs to a guest."""
    return owner_id.startswith(GUEST_OWNER_PREFIX) if owner_id else False


def migrate_guest_data(db: PostgresDB, guest_token: str, user_id: str) -> dict:
    """
    Migrate all data owned by a guest token to an authenticated user.

    Updates:
    - ChromaDB: job/CV metadata owner_user_id
    - PostgreSQL: job_ownership, cv_ownership tables

    Returns:
        Dict with migration counts: {"jobs": N, "cvs": N}
    """
    old_owner = guest_owner_id(guest_token)
    migrated = {"jobs": 0, "cvs": 0}

    try:
        vs = VectorStore()

        # Migrate jobs
        all_jobs = vs.list_all_jobs(is_admin=True)
        for job in all_jobs:
            if job["metadata"].get("owner_user_id") == old_owner:
                job_id = job["id"]
                # Update ChromaDB metadata
                new_meta = dict(job["metadata"])
                new_meta["owner_user_id"] = user_id
                vs.update_job_metadata(job_id, new_meta)
                # Upsert PostgreSQL ownership
                _upsert_ownership(db, "job_ownership", "job_id", job_id, user_id)
                migrated["jobs"] += 1

        # Migrate CVs
        all_cvs = vs.list_all_cvs(is_admin=True)
        for cv in all_cvs:
            if cv["metadata"].get("owner_user_id") == old_owner:
                cv_id = cv["id"]
                new_meta = dict(cv["metadata"])
                new_meta["owner_user_id"] = user_id
                vs.update_cv_metadata(cv_id, new_meta)
                _upsert_ownership(db, "cv_ownership", "cv_id", cv_id, user_id)
                migrated["cvs"] += 1

        if migrated["jobs"] > 0 or migrated["cvs"] > 0:
            logger.info(
                "Migrated guest data: %d jobs, %d CVs from %s to user %s",
                migrated["jobs"],
                migrated["cvs"],
                guest_token[:8],
                user_id[:8],
            )

    except Exception as e:
        logger.error(
            "Guest data migration failed for token %s: %s", guest_token[:8], str(e)
        )

    return migrated


def _upsert_ownership(
    db: PostgresDB, table: str, id_col: str, item_id: str, user_id: str
):
    """Insert or update ownership record."""
    try:
        db.execute(
            f"""
            INSERT INTO {table} ({id_col}, user_id)
            VALUES (%s, %s)
            ON CONFLICT ({id_col}) DO UPDATE SET user_id = EXCLUDED.user_id
            """,
            (item_id, user_id),
        )
    except Exception as e:
        logger.error("Failed to upsert %s for %s: %s", table, item_id, str(e))
