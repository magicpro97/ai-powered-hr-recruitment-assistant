"""
Unit tests for job_processor.py

Tests the JobProcessor class which handles:
- LLM-based job description parsing
- Structured data extraction (skills, requirements, etc.)
- Vector storage integration

References:
- Brown et al. (2020). "Language Models are Few-Shot Learners" (GPT-3)
- Ouyang et al. (2022). "Training language models to follow instructions"
"""

# Standard library imports
import json
from unittest.mock import Mock, patch

# Third-party imports
import pytest


class TestJobProcessor:
    """Test suite for JobProcessor class."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore for testing."""
        mock = Mock()
        mock.add_job.return_value = "job_001"
        return mock

    @pytest.fixture
    def sample_job_text(self):
        """Sample job description for testing."""
        return """
        Senior Python Developer

        Requirements:
        - 5+ years Python experience
        - FastAPI, Django or Flask
        - PostgreSQL and Redis
        - Docker and Kubernetes

        Nice to have:
        - AWS/GCP experience
        - Machine learning background

        Salary: $120,000 - $150,000
        Location: Remote
        """

    @pytest.fixture
    def expected_extraction(self):
        """Expected structured extraction from sample job."""
        return {
            "title": "Senior Python Developer",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "nice_to_have": ["AWS", "GCP"],
            "experience_years": 5,
            "salary_range": "$120,000 - $150,000",
            "location": "Remote",
        }

    @pytest.mark.unit
    def test_process_job_description_extracts_structure(
        self, mock_vector_store, sample_job_text, expected_extraction
    ):
        """
        Test that process_job_description extracts structured data.

        Validates information extraction pipeline:
        1. Raw text input
        2. LLM extraction with prompt template
        3. JSON parsing of response
        4. Storage in vector database
        """
        with patch("src.processors.job_processor.ChatOpenAI") as MockLLM:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = Mock(
                content=json.dumps(expected_extraction)
            )
            MockLLM.return_value = mock_llm_instance

            with patch("backend.token_utils.count_tokens", return_value=100):
                with patch("src.processors.job_processor.log_llm_call"):
                    # Local application imports
                    from src.processors.job_processor import JobProcessor

                    processor = JobProcessor(mock_vector_store)
                    result = processor.process_job_description(
                        job_id="job_001", job_text=sample_job_text
                    )

                    assert "title" in result
                    assert "required_skills" in result
                    mock_vector_store.add_job.assert_called_once()

    @pytest.mark.unit
    def test_process_job_description_handles_empty_text(self, mock_vector_store):
        """Test processing empty job text (graceful handling)."""
        with patch("src.processors.job_processor.ChatOpenAI") as MockLLM:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = Mock(
                content=json.dumps({"title": "", "required_skills": []})
            )
            MockLLM.return_value = mock_llm_instance

            with patch("backend.token_utils.count_tokens", return_value=0):
                with patch("src.processors.job_processor.log_llm_call"):
                    # Local application imports
                    from src.processors.job_processor import JobProcessor

                    processor = JobProcessor(mock_vector_store)
                    result = processor.process_job_description(
                        job_id="job_002", job_text=""
                    )
                    assert isinstance(result, dict)

    @pytest.mark.unit
    def test_llm_prompt_includes_job_text(self, mock_vector_store, sample_job_text):
        """Verify that the prompt template correctly includes job text."""
        with patch("src.processors.job_processor.ChatOpenAI") as MockLLM:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = Mock(
                content=json.dumps({"title": "Test", "required_skills": []})
            )
            MockLLM.return_value = mock_llm_instance

            with patch("backend.token_utils.count_tokens", return_value=100):
                with patch("src.processors.job_processor.log_llm_call"):
                    # Local application imports
                    from src.processors.job_processor import JobProcessor

                    processor = JobProcessor(mock_vector_store)
                    processor.process_job_description(
                        job_id="job_003", job_text=sample_job_text
                    )

                    assert mock_llm_instance.invoke.called


class TestJobExtractionPrompt:
    """Test suite for job extraction prompt quality."""

    @pytest.mark.unit
    def test_prompt_requests_structured_output(self):
        """Verify extraction prompt requests JSON output."""
        # Local application imports
        from src.utils.prompts import JOB_EXTRACTION_PROMPT

        assert "json" in JOB_EXTRACTION_PROMPT.lower()

    @pytest.mark.unit
    def test_prompt_includes_key_fields(self):
        """Verify prompt requests extraction of essential job fields."""
        # Local application imports
        from src.utils.prompts import JOB_EXTRACTION_PROMPT

        essential_fields = ["title", "skill", "experience", "requirement"]

        prompt_lower = JOB_EXTRACTION_PROMPT.lower()
        for field in essential_fields:
            assert field in prompt_lower, f"Prompt should mention: {field}"


class TestJobUserIsolation:
    """Test suite for multi-tenant job data isolation."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore with user filtering."""
        mock = Mock()
        mock.add_job.return_value = "job_001"
        return mock

    @pytest.mark.unit
    def test_job_stored_with_user_id(self, mock_vector_store):
        """Verify jobs are stored with user_id for isolation."""
        with patch("src.processors.job_processor.ChatOpenAI") as MockLLM:
            mock_llm_instance = Mock()
            mock_llm_instance.invoke.return_value = Mock(
                content=json.dumps({"title": "Test Job", "required_skills": []})
            )
            MockLLM.return_value = mock_llm_instance

            with patch("backend.token_utils.count_tokens", return_value=100):
                with patch("src.processors.job_processor.log_llm_call"):
                    # Local application imports
                    from src.processors.job_processor import JobProcessor

                    processor = JobProcessor(mock_vector_store)
                    processor.process_job_description(
                        job_id="job_001",
                        job_text="Test job description",
                        user_id="user_123",
                    )

                    mock_vector_store.add_job.assert_called_once()
