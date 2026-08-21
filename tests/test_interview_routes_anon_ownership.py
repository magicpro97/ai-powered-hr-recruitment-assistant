"""Behavioral tests for anonymous ownership isolation on interview question routes.

Tests that guest users are isolated: guest A cannot access question sets
saved by guest B, and missing guest tokens are rejected.

TDD: These tests should FAIL with the current code (RED) and PASS after
applying the guest-token ownership fix (GREEN).
"""

# Standard library imports
import importlib
import sys
import types
from unittest.mock import MagicMock

# Third-party imports
import pytest
from fastapi import APIRouter, HTTPException
from starlette.requests import Request

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(headers=None):
    """Build a fake Request with optional headers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


async def _call_route(fn, **kwargs):
    """Call a real route coroutine; return (status_code, data_or_none)."""
    try:
        data = await fn(**kwargs)
        return (200, data)
    except HTTPException as exc:
        return (exc.status_code, None)


# ---------------------------------------------------------------------------
# Fake DB -- simulates SQL WHERE filtering for interview_question_set
# ---------------------------------------------------------------------------


class FakeDB:
    """Stores rows in-memory and filters by user_id for fetchall/fetchone."""

    _INSERT_SQL = "INSERT INTO interview_question_set"
    _DELETE_SQL = "DELETE FROM interview_question_set"
    _COLS = (
        "id",
        "job_id",
        "cv_id",
        "user_id",
        "candidate_name",
        "questions",
        "created_at",
        "updated_at",
    )

    def __init__(self):
        self.execute_calls = []
        self.fetchall_calls = []
        self.fetchone_calls = []
        self._rows = []

    def execute(self, sql, params=None):
        self.execute_calls.append({"sql": sql, "params": params})
        if self._INSERT_SQL in sql and params:
            self._rows.append(dict(zip(self._COLS, params)))
        elif self._DELETE_SQL in sql and params:
            self._rows = [r for r in self._rows if r["id"] != params[0]]

    def fetchall(self, sql, params=None):
        self.fetchall_calls.append({"sql": sql, "params": params})
        # WHERE job_id = %s AND user_id = %s
        if params and len(params) >= 2:
            job_id, user_id = params[0], params[1]
            return [
                r
                for r in self._rows
                if r.get("job_id") == job_id and r.get("user_id") == user_id
            ]
        return []

    def fetchone(self, sql, params=None):
        self.fetchone_calls.append({"sql": sql, "params": params})
        if not params:
            return None
        set_id = params[0]
        for r in self._rows:
            if r["id"] == set_id:
                if len(params) >= 2:
                    # WHERE id = %s AND user_id = %s  (get_question_set)
                    if r.get("user_id") == params[1]:
                        return r
                    return None
                # WHERE id = %s only  (delete_question_set owner check)
                return {"id": r["id"], "user_id": r["user_id"]}
        return None


# ---------------------------------------------------------------------------
# Stub helpers (from test_resource_access_routes.py)
# ---------------------------------------------------------------------------


def _set_mod(monkeypatch, name, attrs=None, is_package=False):
    mod = types.ModuleType(name)
    if is_package:
        mod.__path__ = []
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def _stub_src_tree(monkeypatch):
    M = MagicMock
    _set_mod(monkeypatch, "src", is_package=True)
    _set_mod(
        monkeypatch,
        "src.config",
        {
            "Config": M(
                validate=M(),
                validate_auth=M(),
                UPLOAD_DIR="/tmp/test-uploads",
                CHROMA_PERSIST_DIR="/tmp/test-chroma",
                FRONTEND_URL=None,
                TRUSTED_PROXY_CIDRS=(),
                DEBUG=True,
                JWT_SECRET="test-jwt-secret-must-be-at-least-32-characters",
                JWT_ALGORITHM="HS256",
            )
        },
    )
    _set_mod(monkeypatch, "src.database", is_package=True)
    _set_mod(
        monkeypatch,
        "src.database.vector_store",
        {"VectorStore": lambda *a, **kw: M(), "SYSTEM_USER_ID": "system"},
    )
    _set_mod(
        monkeypatch,
        "src.database.postgres_db",
        {"get_db": M(), "PostgresDB": M},
    )
    _set_mod(monkeypatch, "src.processors", is_package=True)
    for mn, cls in [
        ("job_processor", "JobProcessor"),
        ("cv_processor", "CVProcessor"),
        ("matching_engine", "MatchingEngine"),
        ("question_generator", "QuestionGenerator"),
    ]:
        _set_mod(monkeypatch, f"src.processors.{mn}", {cls: lambda *a, **kw: M()})
    _set_mod(monkeypatch, "src.agents", is_package=True)
    _set_mod(
        monkeypatch,
        "src.agents.recruitment_agent",
        {"RecruitmentAgent": lambda *a, **kw: M()},
    )
    _set_mod(
        monkeypatch,
        "src.agents.memory",
        {
            "ContextManager": M,
            "ConversationMemory": M,
            "SessionOwnershipError": type("SessionOwnershipError", (Exception,), {}),
            "enforce_session_claim": M(),
        },
    )
    _set_mod(monkeypatch, "src.utils", is_package=True)
    _set_mod(monkeypatch, "src.utils.file_utils", {"save_uploaded_file": M()})
    _set_mod(
        monkeypatch,
        "src.dependencies",
        {
            "get_vector_store": M(),
            "get_context_manager": M(),
            "get_cv_processor": M(),
            "get_job_processor": M(),
            "get_matching_engine": M(),
            "get_question_generator": M(),
            "get_recruitment_agent": M(),
            "get_memory_dep": M(),
            "get_conversation_memory": M(),
            "get_context_manager_dep": M(),
            "get_context_manager_singleton": M(),
            "get_memory_singleton": M(),
            "get_vector_store_singleton": M(),
        },
    )


def _stub_chat_router(monkeypatch):
    _set_mod(monkeypatch, "backend.chat_routes", {"router": APIRouter()})


class _NoOpLimiter:
    def limit(self, _limit_string):
        def decorator(fn):
            return fn

        return decorator


def _stub_limiter(monkeypatch):
    limiter_mod = types.ModuleType("backend.limiter")
    limiter_mod.limiter = _NoOpLimiter()
    limiter_mod.get_real_ip = lambda request: "127.0.0.1"
    monkeypatch.setitem(sys.modules, "backend.limiter", limiter_mod)


# Module snapshot / restore (from test_resource_access_routes.py)


def _module_snapshot():
    modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "backend"
        or name.startswith("backend.")
        or name == "src"
        or name.startswith("src.")
    }
    package_attrs = {
        name: (module, dict(vars(module)))
        for name, module in modules.items()
        if name in {"backend", "src"}
    }
    return modules, package_attrs


def _restore_modules(snapshot):
    modules, package_attrs = snapshot
    for name in list(sys.modules):
        if (
            name == "backend"
            or name.startswith("backend.")
            or name == "src"
            or name.startswith("src.")
        ) and name not in modules:
            sys.modules.pop(name, None)
    sys.modules.update(modules)
    for module, attrs in package_attrs.values():
        namespace = vars(module)
        for name in set(namespace) - set(attrs):
            namespace.pop(name, None)
        namespace.update(attrs)


@pytest.fixture
def interview_routes(stub_psycopg, monkeypatch):
    """Import interview routes under stubs without leaking imported modules."""
    snapshot = _module_snapshot()
    try:
        _stub_src_tree(monkeypatch)
        _stub_chat_router(monkeypatch)
        _stub_limiter(monkeypatch)
        sys.modules.pop("backend.interview_routes", None)
        yield importlib.import_module("backend.interview_routes")
    finally:
        _restore_modules(snapshot)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnonOwnershipIsolation:
    """Guest users must be isolated: different tokens -> different owners."""

    @pytest.mark.asyncio
    async def test_save_derives_owner_from_guest_token(
        self, interview_routes, monkeypatch
    ):
        """save_question_set uses guest token to derive owner, not literal 'guest'."""
        fake_db = FakeDB()
        monkeypatch.setattr(interview_routes, "get_db", lambda: fake_db)

        body = interview_routes.SaveQuestionSetRequest(
            job_id="job-1",
            cv_id="cv-1",
            questions=[{"question": "Q1", "type": "Technical"}],
        )

        code, data = await _call_route(
            interview_routes.save_question_set,
            request=_make_request({"X-Guest-Token": "abc123"}),
            body=body,
            current_user=None,
        )

        assert code == 200
        # Verify user_id in INSERT is derived from guest token
        assert len(fake_db.execute_calls) == 1
        params = fake_db.execute_calls[0]["params"]
        user_id_in_insert = params[3]  # 4th positional param is user_id
        assert (
            user_id_in_insert == "guest_abc123"
        ), f"Expected 'guest_abc123' but got '{user_id_in_insert}'"

    @pytest.mark.asyncio
    async def test_guest_isolation_on_list(self, interview_routes, monkeypatch):
        """Guest A cannot see question sets saved by guest B."""
        fake_db = FakeDB()
        monkeypatch.setattr(interview_routes, "get_db", lambda: fake_db)
        monkeypatch.setattr(interview_routes, "format_dt", lambda x: str(x))

        # Guest B saves a set
        body_b = interview_routes.SaveQuestionSetRequest(
            job_id="job-1",
            cv_id="cv-1",
            questions=[{"question": "Q1", "type": "Technical"}],
        )
        code, _ = await _call_route(
            interview_routes.save_question_set,
            request=_make_request({"X-Guest-Token": "token-b"}),
            body=body_b,
            current_user=None,
        )
        assert code == 200

        # Guest A lists -> should see nothing (different owner)
        code, data = await _call_route(
            interview_routes.list_question_sets,
            request=_make_request({"X-Guest-Token": "token-a"}),
            job_id="job-1",
            current_user=None,
        )
        assert code == 200
        assert (
            data["sets"] == []
        ), f"Guest A should see no sets but saw {len(data['sets'])}"

        # Guest B lists -> should see their own set
        code, data = await _call_route(
            interview_routes.list_question_sets,
            request=_make_request({"X-Guest-Token": "token-b"}),
            job_id="job-1",
            current_user=None,
        )
        assert code == 200
        assert len(data["sets"]) == 1, "Guest B should see their own set"

    @pytest.mark.asyncio
    async def test_guest_isolation_on_get(self, interview_routes, monkeypatch):
        """Guest A cannot get a question set saved by guest B."""
        fake_db = FakeDB()
        monkeypatch.setattr(interview_routes, "get_db", lambda: fake_db)
        monkeypatch.setattr(interview_routes, "format_dt", lambda x: str(x))

        # Guest B saves a set
        body_b = interview_routes.SaveQuestionSetRequest(
            job_id="job-1",
            cv_id="cv-1",
            questions=[{"question": "Q1", "type": "Technical"}],
        )
        code, data = await _call_route(
            interview_routes.save_question_set,
            request=_make_request({"X-Guest-Token": "token-b"}),
            body=body_b,
            current_user=None,
        )
        assert code == 200
        set_id = data["id"]

        # Guest A tries to get -> 404 (wrong owner)
        code, _ = await _call_route(
            interview_routes.get_question_set,
            request=_make_request({"X-Guest-Token": "token-a"}),
            set_id=set_id,
            current_user=None,
        )
        assert code == 404

        # Guest B can get their own set
        code, data = await _call_route(
            interview_routes.get_question_set,
            request=_make_request({"X-Guest-Token": "token-b"}),
            set_id=set_id,
            current_user=None,
        )
        assert code == 200

    @pytest.mark.asyncio
    async def test_guest_isolation_on_delete(self, interview_routes, monkeypatch):
        """Guest A cannot delete a question set saved by guest B."""
        fake_db = FakeDB()
        monkeypatch.setattr(interview_routes, "get_db", lambda: fake_db)

        # Guest B saves a set
        body_b = interview_routes.SaveQuestionSetRequest(
            job_id="job-1",
            cv_id="cv-1",
            questions=[{"question": "Q1", "type": "Technical"}],
        )
        code, data = await _call_route(
            interview_routes.save_question_set,
            request=_make_request({"X-Guest-Token": "token-b"}),
            body=body_b,
            current_user=None,
        )
        assert code == 200
        set_id = data["id"]

        # Guest A tries to delete -> 403 (not owner)
        code, _ = await _call_route(
            interview_routes.delete_question_set,
            request=_make_request({"X-Guest-Token": "token-a"}),
            set_id=set_id,
            current_user=None,
        )
        assert code == 403

        # Guest B can delete their own set
        code, data = await _call_route(
            interview_routes.delete_question_set,
            request=_make_request({"X-Guest-Token": "token-b"}),
            set_id=set_id,
            current_user=None,
        )
        assert code == 200

    @pytest.mark.asyncio
    async def test_missing_guest_token_rejected(self, interview_routes, monkeypatch):
        """Anonymous request without guest token is rejected (403)."""
        fake_db = FakeDB()
        monkeypatch.setattr(interview_routes, "get_db", lambda: fake_db)

        body = interview_routes.SaveQuestionSetRequest(
            job_id="job-1",
            cv_id="cv-1",
            questions=[{"question": "Q1", "type": "Technical"}],
        )

        code, _ = await _call_route(
            interview_routes.save_question_set,
            request=_make_request(),  # No X-Guest-Token header
            body=body,
            current_user=None,
        )
        assert code == 403, f"Expected 403 but got {code}"

    @pytest.mark.asyncio
    async def test_authenticated_user_still_works(self, interview_routes, monkeypatch):
        """Authenticated user flow is not broken by guest token changes."""
        fake_db = FakeDB()
        monkeypatch.setattr(interview_routes, "get_db", lambda: fake_db)

        body = interview_routes.SaveQuestionSetRequest(
            job_id="job-1",
            cv_id="cv-1",
            questions=[{"question": "Q1", "type": "Technical"}],
        )

        code, data = await _call_route(
            interview_routes.save_question_set,
            request=_make_request(),
            body=body,
            current_user={"id": "auth-user-1", "role": "user"},
        )

        assert code == 200
        params = fake_db.execute_calls[0]["params"]
        assert (
            params[3] == "auth-user-1"
        ), f"Expected 'auth-user-1' but got '{params[3]}'"
