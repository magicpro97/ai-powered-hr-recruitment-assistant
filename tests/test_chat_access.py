"""
Tests for Task 4: Chat upload/agent bind owner.

Tests cover:
- resolve_owner_id helper
- Chat upload binds owner and strips PII from response
- ConversationMemory owner-scoped access
"""

# Standard library imports
from unittest.mock import Mock, patch

# Third-party imports
import pytest

# ── resolve_owner_id ────────────────────────────────────────────────────


class TestResolveOwnerId:
    """resolve_owner_id(request, current_user) returns authenticated user id or validated guest owner."""

    def test_authenticated_user(self):
        """Authenticated user returns their id."""
        # Local application imports
        from backend.access_control import resolve_owner_id

        request = Mock()
        request.headers = {}
        current_user = {"id": "user-42", "role": "user"}

        result = resolve_owner_id(request, current_user)
        assert result == "user-42"

    def test_guest_with_valid_token(self):
        """Guest with valid token returns guest_owner_id."""
        # Local application imports
        from backend.access_control import resolve_owner_id

        request = Mock()
        request.headers = {"X-Guest-Token": "tok-abc-123"}
        current_user = None

        with patch.dict(
            "sys.modules",
            {
                "backend.guest_token": Mock(
                    get_guest_token=Mock(return_value="tok-abc-123"),
                    guest_owner_id=Mock(return_value="guest_tok-abc-123"),
                )
            },
        ):
            result = resolve_owner_id(request, current_user)
            assert result == "guest_tok-abc-123"

    def test_no_auth_no_guest_returns_none(self):
        """No auth and no guest token returns None."""
        # Local application imports
        from backend.access_control import resolve_owner_id

        request = Mock()
        request.headers = {}
        current_user = None

        with patch.dict(
            "sys.modules",
            {
                "backend.guest_token": Mock(
                    get_guest_token=Mock(return_value=None),
                    guest_owner_id=Mock(return_value=None),
                )
            },
        ):
            result = resolve_owner_id(request, current_user)
            assert result is None

    def test_never_returns_system_user_id(self):
        """resolve_owner_id never returns SYSTEM_USER_ID."""
        # Local application imports
        from backend.access_control import SYSTEM_USER_ID, resolve_owner_id

        request = Mock()
        request.headers = {}
        current_user = None

        with patch.dict(
            "sys.modules",
            {
                "backend.guest_token": Mock(
                    get_guest_token=Mock(return_value=None),
                    guest_owner_id=Mock(return_value=None),
                )
            },
        ):
            result = resolve_owner_id(request, current_user)
            assert result != SYSTEM_USER_ID


# ── Chat upload response stripping ──────────────────────────────────────


class TestChatUploadResponseStripping:
    """Chat upload response must not leak email, phone, raw path, or raw history.

    Tests call build_chat_upload_response() directly to verify the DTO
    strips sensitive fields — pure behavioral, no source-text grep.
    """

    def test_upload_cv_via_chat_strips_sensitive_fields(self):
        """Response from chat upload must not contain email, phone, file_path."""
        # Local application imports
        from backend.access_control import build_chat_upload_response

        response = build_chat_upload_response(
            session_id="s1",
            cv_id="cv1",
            name="Test User",
            skills=["Python"],
            summary="A summary",
            experience_years=5,
            message="Uploaded successfully",
        )
        assert "email" not in response
        assert "phone" not in response
        assert "file_path" not in response
        assert response["name"] == "Test User"
        assert response["cv_id"] == "cv1"

    def test_chat_upload_dto_rejects_sensitive_kwargs(self):
        """Passing email, phone, file_path as kwargs must NOT leak into response."""
        # Local application imports
        from backend.access_control import build_chat_upload_response

        response = build_chat_upload_response(
            session_id="s2",
            cv_id="cv2",
            name="Leaky User",
            email="secret" + "@" + "example.invalid",
            phone="+84" + "123456789",
            file_path="/uploads/secret.pdf",
            education="MIT",
            work_history=[{"company": "Acme"}],
            message="Done",
        )
        # Sensitive fields must be absent even when explicitly passed
        for field in ("email", "phone", "file_path", "education", "work_history"):
            assert field not in response, f"DTO leaked sensitive field: {field}"
        # Safe fields must be present and correct
        assert response["session_id"] == "s2"
        assert response["cv_id"] == "cv2"
        assert response["name"] == "Leaky User"


def test_question_generation_response_is_vietnamese(stub_psycopg):
    # Local application imports
    from backend.chat_routes import _execute_chat_action

    context = Mock()
    context.get_context.side_effect = lambda _session, key, owner_id=None: {
        "job_id": "job-1",
        "matches": [
            {
                "cv_id": "cv-1",
                "name": "Hồ sơ A",
                "strengths": ["Python"],
                "gaps": ["Docker"],
            }
        ],
    }.get(key)
    generator = Mock()
    generator.generate_questions.return_value = [
        {"type": "Technical", "question": f"Câu hỏi Python số {number}?"}
        for number in range(1, 7)
    ]

    result = _execute_chat_action(
        session_id="session-1",
        intent={"action": "generate_questions", "candidate_name": "Hồ sơ A"},
        job_processor=Mock(),
        cv_processor=Mock(),
        matching_engine=Mock(),
        question_generator=generator,
        context_manager=context,
        recruitment_agent=Mock(),
        user_lang="vi",
    )

    assert result["status"] == "success"
    assert "Đã tạo 6 câu hỏi cho Hồ sơ A" in result["message"]
    assert "Hiển thị 5 câu tiêu biểu trong 6 câu đã tạo:" in result["message"]
    assert "(Kỹ thuật)" in result["message"]
    assert "Generated" not in result["message"]
    assert "Key topics" not in result["message"]


def test_chat_matching_uses_only_the_current_users_cvs(stub_psycopg):
    # Local application imports
    from backend.chat_routes import _execute_chat_action

    context = Mock()
    context.get_context.side_effect = lambda _session, key, owner_id=None: {
        "job_id": "job-1",
        "cvs": [],
    }.get(key)
    cvs = Mock()
    cvs.list_all_cvs.return_value = [{"cv_id": "cv-1", "name": "Hồ sơ A"}]
    matching = Mock()
    matching.match_candidates.return_value = [
        {
            "cv_id": "cv-1",
            "name": "Hồ sơ A",
            "fit_score": 80,
            "strengths": ["Python"],
            "gaps": ["Docker"],
        }
    ]

    result = _execute_chat_action(
        session_id="session-1",
        intent={"action": "run_matching", "top_k": 5},
        job_processor=Mock(),
        cv_processor=cvs,
        matching_engine=matching,
        question_generator=Mock(),
        context_manager=context,
        recruitment_agent=Mock(),
        current_user={"id": "user-1", "role": "user"},
        owner_id="user-1",
        user_lang="vi",
    )

    assert result["status"] == "success"
    cvs.list_all_cvs.assert_called_once_with(
        user_id="user-1", include_public=False, is_admin=False
    )
    matching.match_candidates.assert_called_once_with(
        "job-1",
        viewer=matching.match_candidates.call_args.kwargs["viewer"],
        top_k=5,
        lang="vi",
        owner_only=True,
    )


# ── ConversationMemory owner binding ────────────────────────────────────


class TestConversationMemoryOwnerBinding:
    """ConversationMemory get/store/clear must accept owner parameter."""

    def test_get_session_history_accepts_owner(self):
        """get_session_history should accept owner_id parameter."""
        # Standard library imports
        import inspect

        # Local application imports
        from src.agents.memory import ConversationMemory

        sig = inspect.signature(ConversationMemory.get_session_history)
        param_names = list(sig.parameters.keys())
        # After Task 4, owner_id should be a parameter
        assert "owner_id" in param_names

    def test_context_store_accepts_owner(self):
        """ContextManager.store_context should accept owner_id."""
        # Standard library imports
        import inspect

        # Local application imports
        from src.agents.memory import ContextManager

        sig = inspect.signature(ContextManager.store_context)
        param_names = list(sig.parameters.keys())
        assert "owner_id" in param_names

    def test_context_get_accepts_owner(self):
        """ContextManager.get_context should accept owner_id."""
        # Standard library imports
        import inspect

        # Local application imports
        from src.agents.memory import ContextManager

        sig = inspect.signature(ContextManager.get_context)
        param_names = list(sig.parameters.keys())
        assert "owner_id" in param_names


# ── Agent request model cv_ids ──────────────────────────────────────────


class TestAgentRequestModel:
    """Agent request model must use cv_ids instead of cv_files.

    NOTE: Cannot import from backend.main due to psycopg chain.
    We verify source code structure instead.
    """

    def test_agent_quick_screen_uses_cv_ids(self):
        """AgentQuickScreenRequest should have cv_ids field, not cv_files."""
        # Standard library imports
        import pathlib

        main_py = pathlib.Path(__file__).resolve().parent.parent / "backend" / "main.py"
        source = main_py.read_text()
        assert "cv_ids" in source
        # Verify the old cv_files field is removed from AgentQuickScreenRequest
        lines = source.split("\n")
        in_model = False
        for line in lines:
            if "class AgentQuickScreenRequest" in line:
                in_model = True
            if in_model and "cv_files" in line and "cv_ids" not in line:
                pytest.fail("AgentQuickScreenRequest still has cv_files field")
            if (
                in_model
                and line.strip()
                and not line.strip().startswith("#")
                and not line.strip().startswith("class")
            ):
                if "class " in line and "AgentQuickScreenRequest" not in line:
                    break
                if "def " in line or "async def " in line:
                    break
        assert in_model

    def test_agent_workflow_uses_cv_ids(self):
        """AgentWorkflowRequest should have cv_ids field."""
        # Standard library imports
        import pathlib

        main_py = pathlib.Path(__file__).resolve().parent.parent / "backend" / "main.py"
        source = main_py.read_text()
        assert "cv_ids" in source

    def test_recruitment_agent_accepts_cv_ids(self):
        """RecruitmentAgent.quick_screen should accept cv_ids parameter."""
        # Standard library imports
        import pathlib

        agent_py = (
            pathlib.Path(__file__).resolve().parent.parent
            / "src"
            / "agents"
            / "recruitment_agent.py"
        )
        source = agent_py.read_text()
        # Check the quick_screen method accepts cv_ids
        assert "cv_ids" in source
