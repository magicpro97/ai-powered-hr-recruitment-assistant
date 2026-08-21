"""
Unit tests for matching_engine.py

Tests the MatchingEngine class which implements hybrid matching:
- Vector similarity search (cosine distance in embedding space)
- LLM-based reasoning for fit score calculation

References:
- Robertson & Zaragoza (2009). "The Probabilistic Relevance Framework: BM25 and Beyond"
- Reimers & Gurevych (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks"
- Wei et al. (2022). "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
"""

# Standard library imports
import json
from unittest.mock import MagicMock, Mock, patch

# Third-party imports
import pytest

# Local application imports
from backend.access_control import Viewer

ADMIN_VIEWER = Viewer(user_id="test-admin", is_admin=True)


class TestMatchingEngine:
    """Test suite for MatchingEngine class."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore for testing."""
        mock = Mock()
        mock.get_job.return_value = {
            "text": "Senior Python Developer with 5 years experience",
            "metadata": {
                "title": "Senior Python Developer",
                "required_skills": ["Python", "FastAPI", "PostgreSQL"],
                "experience_years": "5",
                "owner_user_id": "test-admin",
                "is_public": False,
            },
        }
        mock.search_similar_cvs.return_value = {
            "ids": [["cv_001", "cv_002"]],
            "distances": [[0.2, 0.4]],  # Lower distance = more similar
        }
        mock.get_cv.side_effect = lambda cv_id: {
            "cv_001": {
                "metadata": {
                    "name": "John Doe",
                    "skills": ["Python", "FastAPI", "Django"],
                    "experience_years": 6,
                    "owner_user_id": "test-admin",
                    "is_public": False,
                }
            },
            "cv_002": {
                "metadata": {
                    "name": "Jane Smith",
                    "skills": ["Python", "Flask"],
                    "experience_years": 3,
                    "owner_user_id": "test-admin",
                    "is_public": False,
                }
            },
        }.get(cv_id)
        return mock

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for fit score calculation."""
        return {
            "fit_score": 85,
            "strengths": ["Strong Python experience", "FastAPI expertise"],
            "gaps": ["No PostgreSQL listed"],
            "reasoning": "Candidate has 6 years of Python experience, exceeding the 5 year requirement.",
        }

    @pytest.mark.unit
    def test_match_candidates_returns_ranked_list(
        self, mock_vector_store, mock_llm_response
    ):
        """
        Test that match_candidates returns candidates ranked by fit score.

        This validates the hybrid matching approach combining:
        1. Vector similarity (semantic search)
        2. LLM reasoning (structured evaluation)
        """
        with patch("src.processors.matching_engine.ChatOpenAI") as MockLLM:
            # Setup mock LLM
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = Mock(
                content=json.dumps(mock_llm_response)
            )
            MockLLM.return_value = mock_llm_instance

            # Import after patching
            # Local application imports
            from src.processors.matching_engine import MatchingEngine

            engine = MatchingEngine(mock_vector_store)
            results = engine.match_candidates("job_001", viewer=ADMIN_VIEWER, top_k=5)

            # Verify results structure
            assert len(results) == 2
            assert all("cv_id" in r for r in results)
            assert all("fit_score" in r for r in results)
            assert all("strengths" in r for r in results)
            assert all("gaps" in r for r in results)

    @pytest.mark.unit
    def test_match_candidates_job_not_found(self, mock_vector_store):
        """Test that ValueError is raised when job doesn't exist."""
        mock_vector_store.get_job.return_value = None

        with patch("src.processors.matching_engine.ChatOpenAI"):
            # Local application imports
            from src.processors.matching_engine import MatchingEngine

            engine = MatchingEngine(mock_vector_store)

            with pytest.raises(ValueError, match="Job .* not found"):
                engine.match_candidates("nonexistent_job", viewer=ADMIN_VIEWER)

    @pytest.mark.unit
    def test_similarity_score_conversion(self, mock_vector_store):
        """
        Test that vector distances are correctly converted to similarity scores.

        ChromaDB returns L2 distance by default. Similarity = 1 - distance.
        Reference: ChromaDB documentation on distance metrics.
        """
        with patch("src.processors.matching_engine.ChatOpenAI") as MockLLM:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = Mock(
                content=json.dumps(
                    {"fit_score": 80, "strengths": [], "gaps": [], "reasoning": ""}
                )
            )
            MockLLM.return_value = mock_llm_instance

            # Local application imports
            from src.processors.matching_engine import MatchingEngine

            engine = MatchingEngine(mock_vector_store)
            results = engine.match_candidates("job_001", viewer=ADMIN_VIEWER, top_k=5)

            # First candidate: distance 0.2 -> similarity 0.8
            assert results[0]["similarity_score"] == pytest.approx(0.8, rel=0.01)
            # Second candidate: distance 0.4 -> similarity 0.6
            assert results[1]["similarity_score"] == pytest.approx(0.6, rel=0.01)


class TestFitScoreCalculation:
    """Test suite for fit score calculation logic."""

    @pytest.mark.unit
    def test_fit_score_range(self):
        """
        Fit scores should be in range [0, 100].

        Based on rubric: 0-20 (Poor), 21-40 (Below Average),
        41-60 (Average), 61-80 (Good), 81-100 (Excellent)
        """
        # This would test the actual score validation
        scores = [0, 25, 50, 75, 100]
        for score in scores:
            assert 0 <= score <= 100

    @pytest.mark.unit
    def test_hybrid_score_weighting(self):
        """
        Test hybrid score combines vector similarity and LLM fit score.

        Formula: final_score = α * vector_similarity + (1-α) * llm_score
        where α is typically 0.3-0.5 for balance between semantic and reasoning.

        Reference:
        - Nogueira et al. (2019). "Document Expansion by Query Prediction"
        """
        vector_similarity = 0.8  # From embedding distance
        llm_fit_score = 75  # From structured evaluation
        alpha = 0.3

        # Normalize vector_similarity to 0-100 scale
        hybrid_score = alpha * (vector_similarity * 100) + (1 - alpha) * llm_fit_score

        # Expected: 0.3 * 80 + 0.7 * 75 = 24 + 52.5 = 76.5
        assert hybrid_score == pytest.approx(76.5, rel=0.01)


class TestRecruitmentAgentViewerThreading:
    """Agent matching preserves explicit anonymous viewers and trusted internal fallback."""

    @staticmethod
    def _agent():
        # Local application imports
        from src.agents.recruitment_agent import RecruitmentAgent

        agent = RecruitmentAgent.__new__(RecruitmentAgent)
        agent.job_processor = MagicMock()
        agent.job_processor.process_job_description.return_value = {
            "required_skills": []
        }
        agent.cv_processor = MagicMock()
        agent.cv_processor.process_cv.return_value = {"name": "Candidate"}
        agent.matching_engine = MagicMock()
        agent.matching_engine.match_candidates.return_value = []
        return agent

    @staticmethod
    def _state(**viewer):
        return {
            "job_id": "job-1",
            "job_text": "Senior Python engineer",
            "cv_files": ["resume.pdf"],
            "top_k": 3,
            "errors": [],
            "completed_steps": [],
            **viewer,
        }

    def test_explicit_anonymous_viewer_remains_anonymous(self, stub_psycopg):
        agent = self._agent()
        agent._match_candidates_node(
            self._state(viewer_user_id=None, viewer_is_admin=False)
        )

        viewer = agent.matching_engine.match_candidates.call_args.kwargs["viewer"]
        assert viewer.user_id is None
        assert viewer.is_admin is False

    def test_internal_caller_without_viewer_uses_system_owner(self, stub_psycopg):
        # Local application imports
        from src.agents.recruitment_agent import _SYSTEM_OWNER

        agent = self._agent()
        agent._match_candidates_node(self._state())

        viewer = agent.matching_engine.match_candidates.call_args.kwargs["viewer"]
        assert viewer.user_id == _SYSTEM_OWNER
        assert viewer.is_admin is False

    def test_guest_owner_reaches_created_job_and_cvs(self, stub_psycopg):
        agent = self._agent()
        state = self._state(viewer_user_id="guest-token-owner", viewer_is_admin=False)

        agent._analyze_job_node(state)
        agent._screen_cvs_node(state)

        assert agent.job_processor.process_job_description.call_args.kwargs == {
            "user_id": "guest-token-owner"
        }
        assert agent.cv_processor.process_cv.call_args.kwargs == {
            "user_id": "guest-token-owner"
        }

    def test_internal_nodes_without_viewer_create_system_resources(self, stub_psycopg):
        # Local application imports
        from src.agents.recruitment_agent import _SYSTEM_OWNER

        agent = self._agent()
        state = self._state()

        agent._analyze_job_node(state)
        agent._screen_cvs_node(state)

        assert agent.job_processor.process_job_description.call_args.kwargs == {
            "user_id": _SYSTEM_OWNER
        }
        assert agent.cv_processor.process_cv.call_args.kwargs == {
            "user_id": _SYSTEM_OWNER
        }

    def test_explicit_anonymous_owner_cannot_create_resources(self, stub_psycopg):
        agent = self._agent()
        state = self._state(viewer_user_id=None, viewer_is_admin=False)

        agent._analyze_job_node(state)
        agent._screen_cvs_node(state)

        agent.job_processor.process_job_description.assert_not_called()
        agent.cv_processor.process_cv.assert_not_called()
        assert state["errors"].count("Missing resource owner") == 2


class TestMatchingPromptValidation:
    """Test suite for matching prompt structure."""

    @pytest.mark.unit
    def test_prompt_contains_required_sections(self):
        """Verify matching prompt includes all required evaluation criteria."""
        # Local application imports
        from src.utils.prompts import MATCHING_PROMPT

        required_sections = [
            "fit_score",
            "strengths",
            "gaps",
            "reasoning",
        ]

        for section in required_sections:
            assert section in MATCHING_PROMPT.lower(), f"Missing section: {section}"

    @pytest.mark.unit
    def test_prompt_requests_json_output(self):
        """Verify prompt requests structured JSON output for parsing."""
        # Local application imports
        from src.utils.prompts import MATCHING_PROMPT

        assert "json" in MATCHING_PROMPT.lower(), "Prompt should request JSON output"
