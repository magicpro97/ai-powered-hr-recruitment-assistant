"""Behavioral tests for resource access control on CV/job/question routes.

Tests the REAL route handler functions (backend.main.get_cv_detail, get_job,
generate_questions and backend.interview_routes.generate_questions) via
monkeypatch on their module globals — no duplicate app implementations, no
real Chroma/psycopg.  No module-level imports of backend.main or
backend.interview_routes.
"""

# Standard library imports
import hashlib
import importlib
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock

# Third-party imports
import pytest
from fastapi import APIRouter, HTTPException, Response
from starlette.requests import Request

# Local application imports
from backend.access_control import Viewer, can_view_resource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _viewer(user_id=None, is_admin=False):
    return Viewer(user_id=user_id, is_admin=is_admin)


def _meta(owner_id="owner-1", is_public=False):
    return {"owner_user_id": owner_id, "is_public": is_public}


def _make_request(headers=None):
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
# Stub helpers — all via monkeypatch so they auto-restore after each test
# ---------------------------------------------------------------------------


def _set_mod(monkeypatch, name, attrs=None, is_package=False):
    """Create a stub module and install it via monkeypatch."""
    mod = types.ModuleType(name)
    if is_package:
        mod.__path__ = []
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def _stub_src_tree(monkeypatch):
    """Stub the entire src.* dependency tree needed by backend.main."""
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _module_snapshot():
    """Capture modules and root-package attributes changed by isolated imports."""
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
    """Remove imports made under stubs, then restore prior module identities."""
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

    # Import machinery caches child modules on their parent package. Restore
    # those attributes too, otherwise later tests can retain stub-backed modules.
    for module, attrs in package_attrs.values():
        namespace = vars(module)
        for name in set(namespace) - set(attrs):
            namespace.pop(name, None)
        namespace.update(attrs)


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


@pytest.fixture
def backend_main(stub_psycopg, monkeypatch):
    """Import backend.main under stubs without leaking imported modules."""
    snapshot = _module_snapshot()
    try:
        _stub_src_tree(monkeypatch)
        _stub_chat_router(monkeypatch)
        _stub_limiter(monkeypatch)
        sys.modules.pop("backend.main", None)
        yield importlib.import_module("backend.main")
    finally:
        _restore_modules(snapshot)


@pytest.fixture
def interview_routes(stub_psycopg, monkeypatch):
    """Import interview routes under stubs without leaking imported modules."""
    snapshot = _module_snapshot()
    try:
        _stub_src_tree(monkeypatch)
        _stub_limiter(monkeypatch)
        sys.modules.pop("backend.interview_routes", None)
        yield importlib.import_module("backend.interview_routes")
    finally:
        _restore_modules(snapshot)


# ---------------------------------------------------------------------------
# 1. Pure access_control policy (no DB, no route)
# ---------------------------------------------------------------------------


class TestAccessControlPolicy:
    def test_private_resource_owner_can_view(self):
        assert can_view_resource(_viewer("owner-1"), _meta("owner-1"))

    def test_private_resource_non_owner_denied(self):
        assert not can_view_resource(_viewer("other"), _meta("owner-1"))

    def test_public_resource_anyone_can_view(self):
        assert can_view_resource(_viewer("anyone"), _meta("owner-1", True))

    def test_admin_always_viewable(self):
        assert can_view_resource(_viewer(is_admin=True), _meta("owner-1"))

    def test_anonymous_denied_private(self):
        assert not can_view_resource(_viewer(), _meta("owner-1"))

    def test_anonymous_allowed_public(self):
        assert can_view_resource(_viewer(), _meta("owner-1", True))

    def test_missing_owner_fails_closed(self):
        assert not can_view_resource(_viewer(is_admin=True), {"is_public": False})


# ---------------------------------------------------------------------------
# 2. GET /api/cvs/{cv_id} — real get_cv_detail, monkeypatched vector_store
# ---------------------------------------------------------------------------


class TestRealCvDetail:
    @pytest.mark.asyncio
    async def test_private_cv_denied_non_owner(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_cv.return_value = {"metadata": _meta("owner-1"), "text": "secret"}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_cv_detail,
            cv_id="cv-1",
            request=_make_request(),
            current_user={"id": "other", "role": "user", "is_active": True},
        )
        assert code == 404

    @pytest.mark.asyncio
    async def test_private_cv_allowed_owner(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_cv.return_value = {"metadata": _meta("owner-1"), "text": "my cv"}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, data = await _call_route(
            backend_main.get_cv_detail,
            cv_id="cv-1",
            request=_make_request(),
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )
        assert code == 200

    @pytest.mark.asyncio
    async def test_private_cv_allowed_admin(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_cv.return_value = {
            "metadata": _meta("owner-1"),
            "text": "secret cv",
        }
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_cv_detail,
            cv_id="cv-1",
            request=_make_request(),
            current_user={"id": "admin-1", "role": "admin", "is_active": True},
        )
        assert code == 200

    @pytest.mark.asyncio
    async def test_public_cv_allowed_non_owner(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_cv.return_value = {
            "metadata": _meta("owner-1", True),
            "text": "public cv",
        }
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_cv_detail,
            cv_id="cv-1",
            request=_make_request(),
            current_user={"id": "anyone", "role": "user", "is_active": True},
        )
        assert code == 200

    @pytest.mark.asyncio
    async def test_missing_cv_returns_404(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_cv.return_value = None
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_cv_detail,
            cv_id="nonexistent",
            request=_make_request(),
            current_user={"id": "u1", "role": "user", "is_active": True},
        )
        assert code == 404

    @pytest.mark.asyncio
    async def test_guest_token_used_when_no_user(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_cv.return_value = {
            "metadata": _meta("guest_tok-abc"),
            "text": "guest cv",
        }
        monkeypatch.setattr(backend_main, "vector_store", vs)
        monkeypatch.setattr(backend_main, "get_guest_token", lambda req: "abc")
        monkeypatch.setattr(backend_main, "guest_owner_id", lambda t: f"guest_tok-{t}")

        code, _ = await _call_route(
            backend_main.get_cv_detail,
            cv_id="cv-1",
            request=_make_request(),
            current_user=None,
        )
        assert code == 200


class TestGuestCVListing:
    @pytest.mark.asyncio
    async def test_guest_list_excludes_public_cvs_owned_by_others(
        self, backend_main, monkeypatch
    ):
        """Guest CV list must only load the current guest sandbox."""
        processor = MagicMock()
        processor.list_all_cvs.return_value = []
        monkeypatch.setattr(backend_main, "cv_processor", processor)
        monkeypatch.setattr(
            backend_main, "get_guest_token", lambda request: "demo-token"
        )
        monkeypatch.setattr(
            backend_main, "guest_owner_id", lambda token: f"guest_{token}"
        )

        response = Response()
        await backend_main.list_cvs(
            request=_make_request({"X-Guest-Token": "demo-token"}),
            response=response,
            current_user=None,
        )

        processor.list_all_cvs.assert_called_once_with(
            user_id="guest_demo-token", include_public=False, is_admin=False
        )


# ---------------------------------------------------------------------------
# 3. GET /api/jobs/{job_id} — real get_job, monkeypatched vector_store
# ---------------------------------------------------------------------------


class TestRealJobDetail:
    @pytest.mark.asyncio
    async def test_private_job_denied_non_owner(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("owner-1")}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_job,
            job_id="job-1",
            request=_make_request(),
            current_user={"id": "other", "role": "user", "is_active": True},
        )
        assert code == 404

    @pytest.mark.asyncio
    async def test_private_job_allowed_owner(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("owner-1")}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_job,
            job_id="job-1",
            request=_make_request(),
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )
        assert code == 200

    @pytest.mark.asyncio
    async def test_private_job_allowed_admin(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("owner-1")}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_job,
            job_id="job-1",
            request=_make_request(),
            current_user={"id": "admin-1", "role": "admin", "is_active": True},
        )
        assert code == 200

    @pytest.mark.asyncio
    async def test_missing_job_returns_404(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = None
        monkeypatch.setattr(backend_main, "vector_store", vs)

        code, _ = await _call_route(
            backend_main.get_job,
            job_id="nonexistent",
            request=_make_request(),
            current_user={"id": "u1", "role": "user", "is_active": True},
        )
        assert code == 404

    @pytest.mark.asyncio
    async def test_guest_token_fallback(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("guest_tok-guest-tok")}
        monkeypatch.setattr(backend_main, "vector_store", vs)
        monkeypatch.setattr(backend_main, "get_guest_token", lambda req: "guest-tok")
        monkeypatch.setattr(backend_main, "guest_owner_id", lambda t: f"guest_tok-{t}")

        code, _ = await _call_route(
            backend_main.get_job,
            job_id="job-1",
            request=_make_request(),
            current_user=None,
        )
        assert code == 200


# ---------------------------------------------------------------------------
# Agent workflow viewer propagation — guest ownership must not become system
# ---------------------------------------------------------------------------


class TestAgentWorkflowViewerPropagation:
    @pytest.mark.asyncio
    async def test_guest_owner_reaches_matching_state(self, backend_main, monkeypatch):
        agent = MagicMock()
        captured_state = {}

        def run_workflow(state):
            captured_state.update(state)
            return {"status": "completed"}

        agent.run_workflow.side_effect = run_workflow
        monkeypatch.setattr(backend_main, "recruitment_agent", agent)
        monkeypatch.setattr(
            backend_main,
            "resolve_owner_id",
            lambda request, current_user: "guest_guest-token",
        )

        body = backend_main.AgentWorkflowRequest(
            task="match_candidates", job_id="job-1"
        )
        response = await backend_main.agent_workflow(
            request=_make_request({"X-Guest-Token": "guest-token"}),
            body=body,
            current_user=None,
        )

        assert response["status"] == "completed"
        assert captured_state["viewer_user_id"] == "guest_guest-token"
        assert captured_state["viewer_is_admin"] is False

    @pytest.mark.asyncio
    async def test_anonymous_owner_reaches_matching_state(
        self, backend_main, monkeypatch
    ):
        agent = MagicMock()
        captured_state = {}

        def run_workflow(state):
            captured_state.update(state)
            return {"status": "completed"}

        agent.run_workflow.side_effect = run_workflow
        monkeypatch.setattr(backend_main, "recruitment_agent", agent)
        monkeypatch.setattr(
            backend_main,
            "resolve_owner_id",
            lambda request, current_user: None,
        )

        body = backend_main.AgentWorkflowRequest(
            task="match_candidates", job_id="job-1"
        )
        response = await backend_main.agent_workflow(
            request=_make_request(),
            body=body,
            current_user=None,
        )

        assert response["status"] == "completed"
        assert captured_state["viewer_user_id"] is None
        assert captured_state["viewer_is_admin"] is False


# ---------------------------------------------------------------------------
# Screening cache ownership — real route, fake external dependencies
# ---------------------------------------------------------------------------


class TestScreeningCacheOwnership:
    @pytest.mark.asyncio
    async def test_ownerless_cache_reader_returns_404_without_null_namespace_query(
        self, backend_main, monkeypatch
    ):
        db = MagicMock()
        monkeypatch.setattr(backend_main, "get_db", lambda: db)

        code, _ = await _call_route(
            backend_main.get_cached_screening,
            request=_make_request(),
            job_id="job-1",
            current_user=None,
        )

        assert code == 404
        db.fetchone.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticated_owner_only_screening_reaches_matching_engine(
        self, backend_main, monkeypatch
    ):
        vs = MagicMock()
        vs.get_job.return_value = {
            "metadata": {"title": "Test Job", "owner_user_id": "demo-owner"}
        }
        monkeypatch.setattr(backend_main, "vector_store", vs)
        matching_engine = MagicMock()
        matching_engine.match_candidates_async = AsyncMock(return_value=[])
        monkeypatch.setattr(backend_main, "matching_engine", matching_engine)
        monkeypatch.setattr(
            backend_main, "require_guest_quota", AsyncMock(return_value=None)
        )
        monkeypatch.setattr(backend_main, "get_db", MagicMock())

        await backend_main.screening_candidates(
            request=_make_request(),
            body=backend_main.ScreeningRequest(job_id="job-1", owner_only=True),
            current_user={"id": "demo-owner", "role": "user"},
        )

        matching_engine.match_candidates_async.assert_awaited_once_with(
            "job-1",
            viewer=backend_main.Viewer(user_id="demo-owner", is_admin=False),
            top_k=10,
            owner_only=True,
        )

    @pytest.mark.asyncio
    async def test_screening_cache_persists_resolved_guest_owner(
        self, backend_main, monkeypatch
    ):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": {"title": "Test Job"}}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        matching_engine = MagicMock()
        matching_engine.match_candidates_async = AsyncMock(
            return_value=[
                {
                    "cv_id": "cv-1",
                    "name": "Candidate",
                    "fit_score": 0.9,
                    "strengths": ["Python"],
                    "gaps": ["SQL"],
                    "reasoning": "Test result",
                    "metadata": {
                        "owner_user_id": "guest_demo-token",
                        "is_public": False,
                        "experience_years": 3,
                        "email": "candidate" + "@" + "example.test",
                        "phone": "000",
                    },
                }
            ]
        )
        monkeypatch.setattr(backend_main, "matching_engine", matching_engine)
        monkeypatch.setattr(
            backend_main, "require_guest_quota", AsyncMock(return_value=None)
        )

        db = MagicMock()
        monkeypatch.setattr(backend_main, "get_db", lambda: db)

        response = await backend_main.screening_candidates(
            request=_make_request({"X-Guest-Token": "demo-token"}),
            body=backend_main.ScreeningRequest(job_id="job-1"),
            current_user=None,
        )

        assert response["candidates"]
        assert db.execute.call_count == 2
        delete, insert = db.execute.call_args_list
        assert "user_id = %s" in delete.args[0]
        assert delete.args[1] == ("job-1", "guest_demo-token")
        assert "INSERT INTO screening_cache" in insert.args[0]
        assert insert.args[1][2] == "guest_demo-token"
        assert all(
            "user_id IS NULL" not in call.args[0] for call in db.execute.call_args_list
        )

    @pytest.mark.asyncio
    async def test_screening_cache_skips_ownerless_anonymous_result(
        self, backend_main, monkeypatch
    ):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": {"title": "Test Job"}}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        matching_engine = MagicMock()
        matching_engine.match_candidates_async = AsyncMock(
            return_value=[
                {
                    "cv_id": "cv-1",
                    "name": "Candidate",
                    "fit_score": 0.9,
                    "strengths": ["Python"],
                    "gaps": ["SQL"],
                    "reasoning": "Test result",
                    "metadata": {
                        "owner_user_id": "owner-1",
                        "is_public": True,
                        "experience_years": 3,
                        "email": "candidate" + "@" + "example.test",
                        "phone": "000",
                    },
                }
            ]
        )
        monkeypatch.setattr(backend_main, "matching_engine", matching_engine)
        monkeypatch.setattr(
            backend_main, "require_guest_quota", AsyncMock(return_value=None)
        )

        db = MagicMock()
        monkeypatch.setattr(backend_main, "get_db", lambda: db)

        response = await backend_main.screening_candidates(
            request=_make_request(),
            body=backend_main.ScreeningRequest(job_id="job-1"),
            current_user=None,
        )

        assert response["candidates"]
        db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# 4. POST /api/questions/{job_id}/{cv_id} — real main.generate_questions
# ---------------------------------------------------------------------------


class TestRealMainGenerateQuestions:
    @pytest.mark.asyncio
    async def test_generator_not_called_on_private_job(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("owner-1")}
        vs.get_cv.return_value = {"metadata": _meta("owner-1", True)}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        gen = MagicMock()
        monkeypatch.setattr(backend_main, "question_generator", gen)

        code, _ = await _call_route(
            backend_main.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "other", "role": "user", "is_active": True},
        )
        assert code == 404
        gen.generate_questions.assert_not_called()

    @pytest.mark.asyncio
    async def test_generator_not_called_on_private_cv(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("owner-1", True)}
        vs.get_cv.return_value = {"metadata": _meta("owner-1")}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        gen = MagicMock()
        monkeypatch.setattr(backend_main, "question_generator", gen)

        code, _ = await _call_route(
            backend_main.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "other", "role": "user", "is_active": True},
        )
        assert code == 404
        gen.generate_questions.assert_not_called()

    @pytest.mark.asyncio
    async def test_generator_called_after_visibility(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("owner-1", True)}
        vs.get_cv.return_value = {"metadata": _meta("owner-1", True)}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        gen = MagicMock()
        gen.generate_questions.return_value = [{"question": "Q1"}]
        monkeypatch.setattr(backend_main, "question_generator", gen)

        code, data = await _call_route(
            backend_main.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "any-user", "role": "user", "is_active": True},
        )
        assert code == 200
        gen.generate_questions.assert_called_once_with("job-1", "cv-1")

    @pytest.mark.asyncio
    async def test_generator_called_for_owner_private(self, backend_main, monkeypatch):
        vs = MagicMock()
        vs.get_job.return_value = {"metadata": _meta("owner-1")}
        vs.get_cv.return_value = {"metadata": _meta("owner-1")}
        monkeypatch.setattr(backend_main, "vector_store", vs)

        gen = MagicMock()
        gen.generate_questions.return_value = []
        monkeypatch.setattr(backend_main, "question_generator", gen)

        code, _ = await _call_route(
            backend_main.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )
        assert code == 200
        gen.generate_questions.assert_called_once_with("job-1", "cv-1")


# ---------------------------------------------------------------------------
# 5. POST /api/interview-questions/generate/{job_id}/{cv_id} — real route
# ---------------------------------------------------------------------------


def test_matching_context_from_cached_screening_returns_selected_candidate_context(
    interview_routes,
):
    result = {
        "candidates": [
            {
                "cv_id": "cv-2",
                "matching_skills": ["AWS"],
                "missing_skills": [],
            },
            {
                "cv_id": "cv-1",
                "matching_skills": ["Python", "FastAPI"],
                "missing_skills": ["PostgreSQL"],
            },
        ]
    }

    assert interview_routes.matching_context_from_cached_screening(result, "cv-1") == {
        "strengths": ["Python", "FastAPI"],
        "gaps": ["PostgreSQL"],
    }


def test_matching_context_hash_is_deterministic_and_opaque(interview_routes):
    context = {"strengths": ["Python", "FastAPI"], "gaps": ["PostgreSQL"]}

    digest = interview_routes.matching_context_hash(context)

    assert (
        digest
        == hashlib.sha256(
            json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    assert len(digest) == 64
    assert "Python" not in digest


def test_matching_context_from_cached_screening_does_not_use_other_candidate(
    interview_routes,
):
    result = {
        "candidates": [
            {
                "cv_id": "cv-2",
                "matching_skills": ["AWS"],
                "missing_skills": [],
            }
        ]
    }

    assert (
        interview_routes.matching_context_from_cached_screening(result, "cv-1") is None
    )


@pytest.mark.parametrize(
    "cached_result",
    [
        pytest.param("null", id="json_null"),
        pytest.param({"candidates": None}, id="null_candidates"),
        pytest.param({"candidates": ["not-a-candidate"]}, id="non_dict_candidate"),
        pytest.param(
            {
                "candidates": [
                    {
                        "cv_id": "cv-1",
                        "matching_skills": "Python",
                        "missing_skills": [],
                    }
                ]
            },
            id="matching_skills_string",
        ),
        pytest.param(
            {
                "candidates": [
                    {
                        "cv_id": "cv-1",
                        "matching_skills": [],
                        "missing_skills": None,
                    }
                ]
            },
            id="missing_skills_null",
        ),
        pytest.param(
            {
                "candidates": [
                    {
                        "cv_id": "cv-1",
                        "matching_skills": [{"nested": "PII"}],
                        "missing_skills": [],
                    }
                ]
            },
            id="nested_skill_object",
        ),
        pytest.param(
            {
                "candidates": [
                    {
                        "cv_id": "cv-1",
                        "matching_skills": [""],
                        "missing_skills": [],
                    }
                ]
            },
            id="empty_skill",
        ),
    ],
)
@pytest.mark.asyncio
async def test_matching_context_from_cached_screening_invalid_shapes_fail_open(
    interview_routes, monkeypatch, cached_result
):
    vs_inst = MagicMock()
    vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
    vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
    vs_mod = sys.modules["src.database.vector_store"]
    monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

    db = MagicMock()
    db.fetchone.return_value = {"result": cached_result}
    monkeypatch.setattr(interview_routes, "get_db", lambda: db)

    qg_inst = MagicMock()
    qg_inst.generate_questions.return_value = []
    qg_mod = sys.modules["src.processors.question_generator"]
    monkeypatch.setattr(qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst))

    code, _ = await _call_route(
        interview_routes.generate_questions,
        request=_make_request(),
        job_id="job-1",
        cv_id="cv-1",
        current_user={"id": "owner-1", "role": "user", "is_active": True},
    )

    assert code == 200
    qg_inst.generate_questions.assert_called_once_with(
        "job-1", "cv-1", matching_context=None
    )
    parsed_result = (
        json.loads(cached_result) if isinstance(cached_result, str) else cached_result
    )
    assert (
        interview_routes.matching_context_from_cached_screening(parsed_result, "cv-1")
        is None
    )


class TestRealInterviewGenerateQuestions:
    @pytest.mark.asyncio
    async def test_generator_uses_configured_vector_store(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        constructor = MagicMock(return_value=vs_inst)
        monkeypatch.setattr(
            sys.modules["src.database.vector_store"], "VectorStore", constructor
        )

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        monkeypatch.setattr(
            sys.modules["src.processors.question_generator"],
            "QuestionGenerator",
            MagicMock(return_value=qg_inst),
        )
        db = MagicMock()
        db.fetchone.return_value = None
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )

        assert code == 200
        constructor.assert_called_once_with("/tmp/test-chroma")

    @pytest.mark.asyncio
    async def test_generator_not_called_on_private_job(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1", True)}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        qg_inst = MagicMock()
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )
        get_db = MagicMock()
        monkeypatch.setattr(interview_routes, "get_db", get_db)

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "other", "role": "user", "is_active": True},
        )
        assert code == 404
        qg_inst.generate_questions.assert_not_called()
        get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_generator_not_called_on_private_cv(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1", True)}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        qg_inst = MagicMock()
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )
        get_db = MagicMock()
        monkeypatch.setattr(interview_routes, "get_db", get_db)

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "other", "role": "user", "is_active": True},
        )
        assert code == 404
        qg_inst.generate_questions.assert_not_called()
        get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_generator_called_for_public_resources(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1", True)}
        vs_inst.get_cv.return_value = {"metadata": _meta("other-owner", True)}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = [{"question": "Q1"}]
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )
        db = MagicMock()
        db.fetchone.return_value = None
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        code, data = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "anyone", "role": "user", "is_active": True},
        )
        assert code == 200
        qg_inst.generate_questions.assert_called_once_with(
            "job-1", "cv-1", matching_context=None
        )
        db.fetchone.assert_called_once()
        query, params = db.fetchone.call_args.args
        normalized_query = " ".join(query.split())
        assert "WHERE job_id = %s AND user_id = %s" in normalized_query
        assert "ORDER BY created_at DESC LIMIT 1" in normalized_query
        assert "user_id IS NULL" not in query
        assert params == ("job-1", "anyone")

    @pytest.mark.asyncio
    async def test_generator_called_for_owner_private(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )
        db = MagicMock()
        db.fetchone.return_value = None
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )
        assert code == 200
        qg_inst.generate_questions.assert_called_once_with(
            "job-1", "cv-1", matching_context=None
        )

    @pytest.mark.asyncio
    async def test_admin_allowed_on_private_resources(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )
        db = MagicMock()
        db.fetchone.return_value = None
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "admin-1", "role": "admin", "is_active": True},
        )
        assert code == 200
        qg_inst.generate_questions.assert_called_once_with(
            "job-1", "cv-1", matching_context=None
        )
        db.fetchone.assert_called_once()
        query, params = db.fetchone.call_args.args
        normalized_query = " ".join(query.split())
        assert "WHERE job_id = %s AND user_id = %s" in normalized_query
        assert "ORDER BY created_at DESC LIMIT 1" in normalized_query
        assert "user_id IS NULL" not in query
        assert params == ("job-1", "admin-1")

    @pytest.mark.asyncio
    async def test_generator_receives_owner_scoped_cached_matching_context(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        db = MagicMock()
        db.fetchone.return_value = {
            "result": json.dumps(
                {
                    "candidates": [
                        {
                            "cv_id": "cv-1",
                            "matching_skills": ["Python"],
                            "missing_skills": ["SQL"],
                        }
                    ]
                }
            )
        }
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )

        code, data = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )

        assert code == 200
        assert data["matching_context_used"] is True
        assert data["matching_context_hash"] == interview_routes.matching_context_hash(
            {"strengths": ["Python"], "gaps": ["SQL"]}
        )
        db.fetchone.assert_called_once()
        query, params = db.fetchone.call_args.args
        assert "WHERE job_id = %s AND user_id = %s" in " ".join(query.split())
        assert "user_id IS NULL" not in query
        assert params == ("job-1", "owner-1")
        qg_inst.generate_questions.assert_called_once_with(
            "job-1",
            "cv-1",
            matching_context={"strengths": ["Python"], "gaps": ["SQL"]},
        )

    @pytest.mark.asyncio
    async def test_generator_uses_no_context_when_cache_has_no_selected_candidate(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        db = MagicMock()
        db.fetchone.return_value = {
            "result": {
                "candidates": [
                    {
                        "cv_id": "cv-2",
                        "matching_skills": ["AWS"],
                        "missing_skills": [],
                    }
                ]
            }
        }
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )

        assert code == 200
        qg_inst.generate_questions.assert_called_once_with(
            "job-1", "cv-1", matching_context=None
        )

    @pytest.mark.asyncio
    async def test_generator_uses_no_context_when_cached_result_is_malformed(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        db = MagicMock()
        db.fetchone.return_value = {"result": "not-json"}
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )

        assert code == 200
        qg_inst.generate_questions.assert_called_once_with(
            "job-1", "cv-1", matching_context=None
        )

    @pytest.mark.asyncio
    async def test_cache_read_failure_calls_generator_without_context(
        self, interview_routes, monkeypatch, caplog
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1")}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        db = MagicMock()
        db.fetchone.side_effect = RuntimeError("RAW-CV-CONTENT")
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )
        caplog.set_level("WARNING", logger=interview_routes.__name__)

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user={"id": "owner-1", "role": "user", "is_active": True},
        )

        assert code == 200
        db.fetchone.assert_called_once()
        qg_inst.generate_questions.assert_called_once_with(
            "job-1", "cv-1", matching_context=None
        )
        warnings = [
            record
            for record in caplog.records
            if record.name == interview_routes.__name__
            and record.levelname == "WARNING"
        ]
        assert [record.getMessage() for record in warnings] == [
            "Screening cache unavailable; generating questions without matching context"
        ]
        assert "RAW-CV-CONTENT" not in caplog.text

    @pytest.mark.asyncio
    async def test_guest_generator_queries_only_resolved_guest_cache(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("guest_demo-token")}
        vs_inst.get_cv.return_value = {"metadata": _meta("guest_demo-token")}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        db = MagicMock()
        db.fetchone.return_value = {
            "result": {
                "candidates": [
                    {
                        "cv_id": "cv-1",
                        "matching_skills": ["FastAPI"],
                        "missing_skills": [],
                    }
                ]
            }
        }
        monkeypatch.setattr(interview_routes, "get_db", lambda: db)

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request({"X-Guest-Token": "demo-token"}),
            job_id="job-1",
            cv_id="cv-1",
            current_user=None,
        )

        assert code == 200
        db.fetchone.assert_called_once()
        query, params = db.fetchone.call_args.args
        assert "WHERE job_id = %s AND user_id = %s" in " ".join(query.split())
        assert "user_id IS NULL" not in query
        assert params == ("job-1", "guest_demo-token")
        qg_inst.generate_questions.assert_called_once_with(
            "job-1",
            "cv-1",
            matching_context={"strengths": ["FastAPI"], "gaps": []},
        )

    @pytest.mark.asyncio
    async def test_ownerless_generator_skips_context_cache_lookup(
        self, interview_routes, monkeypatch
    ):
        vs_inst = MagicMock()
        vs_inst.get_job.return_value = {"metadata": _meta("owner-1", True)}
        vs_inst.get_cv.return_value = {"metadata": _meta("owner-1", True)}
        vs_mod = sys.modules["src.database.vector_store"]
        monkeypatch.setattr(vs_mod, "VectorStore", MagicMock(return_value=vs_inst))

        get_db = MagicMock()
        monkeypatch.setattr(interview_routes, "get_db", get_db)

        qg_inst = MagicMock()
        qg_inst.generate_questions.return_value = []
        qg_mod = sys.modules["src.processors.question_generator"]
        monkeypatch.setattr(
            qg_mod, "QuestionGenerator", MagicMock(return_value=qg_inst)
        )

        code, _ = await _call_route(
            interview_routes.generate_questions,
            request=_make_request(),
            job_id="job-1",
            cv_id="cv-1",
            current_user=None,
        )

        assert code == 200
        get_db.assert_not_called()
        qg_inst.generate_questions.assert_called_once_with(
            "job-1", "cv-1", matching_context=None
        )
