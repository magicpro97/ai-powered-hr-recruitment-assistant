"""
Conversation Memory Manager for AI Agent
Maintains context across multiple interactions
"""

# Standard library imports
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionOwnershipError(Exception):
    """Raised when a caller attempts to access a session they don't own."""

    def __init__(
        self, session_id: str, owner_id: Optional[str], reason: str = "not owner"
    ):
        self.session_id = session_id
        self.owner_id = owner_id
        self.reason = reason
        super().__init__(
            f"Session '{session_id}' owner mismatch: caller={owner_id}, reason={reason}"
        )


def enforce_session_claim(
    memory: "ConversationMemory",
    session_id: str,
    owner_id: Optional[str],
    is_admin: bool = False,
) -> None:
    """Enforce session ownership: claim new session or validate existing.

    Must be called BEFORE any context_manager.get/store operations in
    upload endpoints to prevent cross-owner context mutation.

    Raises SessionOwnershipError when:
    - owner_id is None (anonymous caller)
    - session is legacy unowned and caller is not admin
    - session is owned by a different owner (cross-owner)
    """
    if owner_id is None:
        raise SessionOwnershipError(
            session_id=session_id, owner_id=None, reason="anonymous caller"
        )

    # Auto-load session if it exists on disk
    if session_id not in memory.sessions:
        memory.load_session(session_id)

    if session_id not in memory._session_owners:
        if session_id in memory.sessions:
            # Legacy unowned session — only admin can access
            if not is_admin:
                raise SessionOwnershipError(
                    session_id=session_id,
                    owner_id=owner_id,
                    reason="legacy unowned session",
                )
        else:
            # New session — claim it for this owner
            memory.create_session(session_id, owner_id=owner_id)
    else:
        # Session exists — validate owner
        memory.require_session_owner(session_id, owner_id, is_admin=is_admin)


class ConversationMemory:
    """
    Manages conversation history and context for AI Agent
    Supports persistent storage and retrieval
    """

    def __init__(self, memory_dir: str = "./memory"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(exist_ok=True)

        self.sessions: Dict[str, List[Dict[str, Any]]] = {}
        self.current_session_id: Optional[str] = None
        self._session_owners: Dict[str, Optional[str]] = {}  # session_id -> owner_id

    def require_session_owner(
        self, session_id: str, owner_id: Optional[str], is_admin: bool = False
    ) -> None:
        """Validate that caller owns the session, or is admin.

        Raises SessionOwnershipError when:
        - caller is anonymous (owner_id=None)
        - session exists with a different owner (cross-owner)
        - session is legacy/unowned and caller is not admin
        """
        if owner_id is None:
            raise SessionOwnershipError(
                session_id=session_id, owner_id=None, reason="anonymous caller"
            )

        stored_owner = self._session_owners.get(session_id)

        if stored_owner is not None:
            # Session has a claimed owner
            if stored_owner != owner_id and not is_admin:
                raise SessionOwnershipError(
                    session_id=session_id,
                    owner_id=owner_id,
                    reason="cross-owner",
                )
        elif session_id in self.sessions:
            # Session exists but has NO owner (legacy unowned)
            if not is_admin:
                raise SessionOwnershipError(
                    session_id=session_id,
                    owner_id=owner_id,
                    reason="legacy unowned session",
                )
        # else: session doesn't exist yet — will be created by create_session

    def create_session(self, session_id: str, owner_id: Optional[str] = None) -> str:
        """Create new conversation session, claiming it for owner_id.

        Raises SessionOwnershipError if owner_id is None — all new sessions
        must be explicitly owned. Admin access to legacy unowned data is
        preserved through is_admin=True on read methods.
        """
        if owner_id is None:
            raise SessionOwnershipError(
                session_id=session_id,
                owner_id=None,
                reason="new session requires explicit owner",
            )
        if session_id in self._session_owners:
            existing_owner = self._session_owners[session_id]
            if existing_owner is not None and existing_owner != owner_id:
                raise SessionOwnershipError(
                    session_id=session_id,
                    owner_id=owner_id,
                    reason="session already claimed by different owner",
                )
        self.sessions[session_id] = []
        self.current_session_id = session_id
        self._session_owners[session_id] = owner_id
        return session_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
        message_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ):
        """Add message to conversation history.

        Raises SessionOwnershipError if owner_id is None — all message writes
        require an explicit owner. No normal caller may create or write to an
        unowned session.
        """
        if owner_id is None:
            raise SessionOwnershipError(
                session_id=session_id,
                owner_id=None,
                reason="message write requires explicit owner",
            )

        if session_id not in self.sessions:
            self.create_session(session_id, owner_id=owner_id)

        self.require_session_owner(session_id, owner_id)

        message = {
            "role": role,  # "user", "assistant", "system"
            "content": content,
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "metadata": metadata or {},
        }

        # Preserve stable message identity for API clients.
        if message_id:
            message["message_id"] = message_id

        self.sessions[session_id].append(message)

    def get_session_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
        owner_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session, enforcing owner access control."""
        self.require_session_owner(session_id, owner_id, is_admin=is_admin)
        history = self.sessions.get(session_id, [])
        if limit:
            history = history[-limit:]
        return history

    def get_context_summary(
        self, session_id: str, owner_id: Optional[str] = None, is_admin: bool = False
    ) -> str:
        """Generate summary of conversation context, enforcing owner access."""
        self.require_session_owner(session_id, owner_id, is_admin=is_admin)
        history = self.get_session_history(
            session_id, owner_id=owner_id, is_admin=is_admin
        )

        if not history:
            return "No previous conversation context."

        summary_lines = [f"Conversation History (Last {len(history)} messages):"]

        for msg in history[-10:]:  # Last 10 messages
            role = msg["role"].upper()
            content = (
                msg["content"][:100] + "..."
                if len(msg["content"]) > 100
                else msg["content"]
            )
            summary_lines.append(f"[{role}] {content}")

        return "\n".join(summary_lines)

    def save_session(self, session_id: str):
        """Persist session to disk, including owner_id."""
        file_path = self.memory_dir / f"{session_id}.json"
        owner_id = self._session_owners.get(session_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "session_id": session_id,
                    "owner_id": owner_id,
                    "created_at": datetime.now(timezone.utc)
                    .replace(tzinfo=None)
                    .isoformat(),
                    "messages": self.sessions.get(session_id, []),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

    def load_session(self, session_id: str) -> bool:
        """Load session from disk, restoring owner_id."""
        file_path = self.memory_dir / f"{session_id}.json"

        if not file_path.exists():
            return False

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.sessions[session_id] = data.get("messages", [])
            # Restore owner_id from persisted data (may be None for legacy)
            if "owner_id" in data and session_id not in self._session_owners:
                self._session_owners[session_id] = data["owner_id"]
            return True

    def clear_session(
        self, session_id: str, owner_id: Optional[str] = None, is_admin: bool = False
    ):
        """Clear session history, enforcing owner access."""
        self.require_session_owner(session_id, owner_id, is_admin=is_admin)
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self._session_owners:
            del self._session_owners[session_id]


class ContextManager:
    """
    Advanced context management for AI Agent
    Tracks job data, CV data, decisions, and workflow state
    """

    def __init__(
        self, memory: ConversationMemory, context_dir: str = "./memory/contexts"
    ):
        self.memory = memory
        self.context_store: Dict[str, Dict[str, Any]] = {}
        self.context_dir = Path(context_dir)
        self.context_dir.mkdir(parents=True, exist_ok=True)

    def store_context(
        self,
        session_id: str,
        key: str,
        value: Any,
        owner_id: Optional[str] = None,
        is_admin: bool = False,
    ):
        """Store context data, scoped to an owner. Validates session ownership."""
        if owner_id is not None or session_id in self.memory.sessions:
            self.memory.require_session_owner(session_id, owner_id, is_admin=is_admin)
        scoped_key = f"{owner_id}:{key}" if owner_id else key
        if session_id not in self.context_store:
            self.context_store[session_id] = {}

        self.context_store[session_id][scoped_key] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "owner_id": owner_id,
        }

    def save_context(self, session_id: str):
        """Persist context to disk"""
        if session_id not in self.context_store:
            return

        file_path = self.context_dir / f"{session_id}_context.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "session_id": session_id,
                    "saved_at": datetime.now(timezone.utc)
                    .replace(tzinfo=None)
                    .isoformat(),
                    "context": self.context_store[session_id],
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

    def load_context(self, session_id: str) -> bool:
        """Load context from disk"""
        file_path = self.context_dir / f"{session_id}_context.json"

        if not file_path.exists():
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.context_store[session_id] = data.get("context", {})
            return True
        except Exception:
            return False

    def get_context(
        self,
        session_id: str,
        key: str,
        owner_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Optional[Any]:
        """Retrieve context data, scoped to an owner. Validates session ownership."""
        if owner_id is not None or session_id in self.memory.sessions:
            self.memory.require_session_owner(session_id, owner_id, is_admin=is_admin)
        # Auto-load if not in memory
        if session_id not in self.context_store:
            self.load_context(session_id)

        scoped_key = f"{owner_id}:{key}" if owner_id else key
        session_context = self.context_store.get(session_id, {})
        context_item = session_context.get(scoped_key)

        # Admin bypass: if scoped key not found, also search unscoped and other owners' keys
        if context_item is None and is_admin and scoped_key != key:
            context_item = session_context.get(key)
            # Also search owner-prefixed keys (admin sees all owners' data)
            if context_item is None:
                for k, v in session_context.items():
                    if k.endswith(f":{key}"):
                        context_item = v
                        break

        if context_item:
            return context_item["value"]
        return None

    def get_all_context(
        self, session_id: str, owner_id: Optional[str] = None, is_admin: bool = False
    ) -> Dict[str, Any]:
        """Get all context for session, scoped to an owner. Validates session ownership."""
        if owner_id is not None or session_id in self.memory.sessions:
            self.memory.require_session_owner(session_id, owner_id, is_admin=is_admin)
        session_context = self.context_store.get(session_id, {})
        if owner_id is not None:
            prefix = f"{owner_id}:"
            return {
                k[len(prefix) :]: v["value"]
                for k, v in session_context.items()
                if k.startswith(prefix) and v.get("owner_id") == owner_id
            }
        return {k: v["value"] for k, v in session_context.items()}

    def build_context_prompt(
        self, session_id: str, owner_id: Optional[str] = None, is_admin: bool = False
    ) -> str:
        """Build context-aware prompt for LLM, scoped to an owner. Validates session ownership."""
        # Conversation history
        conv_summary = self.memory.get_context_summary(
            session_id, owner_id=owner_id, is_admin=is_admin
        )

        # Stored context
        all_context = self.get_all_context(
            session_id, owner_id=owner_id, is_admin=is_admin
        )

        prompt_parts = [
            "=== CONVERSATION CONTEXT ===",
            conv_summary,
            "",
            "=== STORED DATA ===",
        ]

        if all_context.get("job_data"):
            job = all_context["job_data"]
            prompt_parts.append(f"Current Job: {job.get('title', 'N/A')}")
            prompt_parts.append(
                f"Required Skills: {', '.join(job.get('required_skills', [])[:5])}"
            )

        if all_context.get("cv_count"):
            prompt_parts.append(f"CVs Processed: {all_context['cv_count']}")

        if all_context.get("matches"):
            matches = all_context["matches"]
            prompt_parts.append(f"Candidates Matched: {len(matches)}")
            if matches:
                top = matches[0]
                prompt_parts.append(
                    f"Top Candidate: {top.get('name', 'Unknown')} ({top.get('fit_score', 0)}%)"
                )

        if all_context.get("workflow_stage"):
            prompt_parts.append(f"Current Stage: {all_context['workflow_stage']}")

        prompt_parts.append("\n=== END CONTEXT ===\n")

        return "\n".join(prompt_parts)

    def track_decision(
        self,
        session_id: str,
        decision: str,
        reasoning: str,
        owner_id: Optional[str] = None,
        is_admin: bool = False,
    ):
        """Track AI decisions for transparency, scoped to an owner. Validates session ownership."""
        decisions = (
            self.get_context(
                session_id, "decisions", owner_id=owner_id, is_admin=is_admin
            )
            or []
        )
        decisions.append(
            {
                "decision": decision,
                "reasoning": reasoning,
                "timestamp": datetime.now(timezone.utc)
                .replace(tzinfo=None)
                .isoformat(),
            }
        )
        self.store_context(
            session_id, "decisions", decisions, owner_id=owner_id, is_admin=is_admin
        )

    def get_decision_history(
        self, session_id: str, owner_id: Optional[str] = None, is_admin: bool = False
    ) -> List[Dict[str, Any]]:
        """Get history of AI decisions, scoped to an owner. Validates session ownership."""
        return (
            self.get_context(
                session_id, "decisions", owner_id=owner_id, is_admin=is_admin
            )
            or []
        )

    def clear_context(
        self, session_id: str, owner_id: Optional[str] = None, is_admin: bool = False
    ):
        """Reset stored context for a session, scoped to an owner. Validates session ownership."""
        if owner_id is not None or session_id in self.memory.sessions:
            self.memory.require_session_owner(session_id, owner_id, is_admin=is_admin)
        if session_id in self.context_store:
            if owner_id:
                # Only clear keys scoped to this owner
                to_delete = [
                    k
                    for k, v in self.context_store[session_id].items()
                    if v.get("owner_id") == owner_id
                ]
                for k in to_delete:
                    del self.context_store[session_id][k]
            else:
                del self.context_store[session_id]


# Singleton instances
_global_memory = ConversationMemory()
_global_context = ContextManager(_global_memory)


def get_memory() -> ConversationMemory:
    """Get global memory instance"""
    return _global_memory


def get_context_manager() -> ContextManager:
    """Get global context manager instance"""
    return _global_context
