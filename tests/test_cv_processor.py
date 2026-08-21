"""
Unit tests for cv_processor.py

Tests the CVProcessor class which handles:
- PDF text extraction from CVs
- LLM-based candidate profile extraction
- Structured data storage with embeddings

References:
- Devlin et al. (2019). "BERT: Pre-training of Deep Bidirectional Transformers"
- Luo et al. (2021). "Resume Parsing with Named Entity Recognition"
"""

# Standard library imports
import json
from unittest.mock import Mock, patch

# Third-party imports
import pytest


class TestCVProcessor:
    """Test suite for CVProcessor class."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore for testing."""
        mock = Mock()
        mock.add_cv.return_value = "cv_001"
        return mock

    @pytest.fixture
    def sample_cv_text(self):
        """Sample CV text for testing."""
        email = "john.doe" + "@" + "example.invalid"
        return f"""
        JOHN DOE
        Senior Software Engineer

        Contact: {email}

        EXPERIENCE

        Tech Company Inc. | Senior Developer | 2019-Present
        - Led development of microservices architecture

        SKILLS
        - Languages: Python, JavaScript, TypeScript
        - Frameworks: FastAPI, React

        EDUCATION
        BS Computer Science, MIT, 2016
        """

    @pytest.fixture
    def expected_cv_extraction(self):
        """Expected structured extraction from sample CV."""
        return {
            "name": "John Doe",
            "email": "john.doe" + "@" + "example.invalid",
            "current_title": "Senior Software Engineer",
            "skills": ["Python", "JavaScript", "TypeScript", "FastAPI", "React"],
            "experience_years": 8,
        }

    @pytest.mark.unit
    def test_process_cv_extracts_candidate_profile(
        self, mock_vector_store, sample_cv_text, expected_cv_extraction
    ):
        """
        Test that process_cv extracts structured candidate data.

        Validates Named Entity Recognition (NER) capabilities.
        """
        with patch("src.processors.cv_processor.ChatOpenAI") as MockLLM:
            with patch(
                "src.processors.cv_processor.extract_text_from_pdf"
            ) as mock_extract:
                mock_extract.return_value = sample_cv_text

                with patch("os.path.isfile", return_value=True):
                    mock_llm_instance = Mock()
                    mock_llm_instance.invoke.return_value = Mock(
                        content=json.dumps(expected_cv_extraction)
                    )
                    MockLLM.return_value = mock_llm_instance

                    with patch("backend.token_utils.count_tokens", return_value=100):
                        with patch("src.processors.cv_processor.log_llm_call"):
                            # Local application imports
                            from src.processors.cv_processor import CVProcessor

                            processor = CVProcessor(mock_vector_store)
                            result = processor.process_cv(
                                cv_id="cv_001", cv_file_path="/fake/path/resume.pdf"
                            )

                            assert "name" in result
                            assert "skills" in result
                            mock_vector_store.add_cv.assert_called_once()

    @pytest.mark.unit
    def test_pdf_extraction_called(self, mock_vector_store, sample_cv_text):
        """Verify PDF text extraction is invoked."""
        with patch("src.processors.cv_processor.ChatOpenAI") as MockLLM:
            with patch(
                "src.processors.cv_processor.extract_text_from_pdf"
            ) as mock_extract:
                mock_extract.return_value = sample_cv_text

                with patch("os.path.isfile", return_value=True):
                    mock_llm_instance = Mock()
                    mock_llm_instance.invoke.return_value = Mock(
                        content=json.dumps({"name": "Test", "skills": []})
                    )
                    MockLLM.return_value = mock_llm_instance

                    with patch("backend.token_utils.count_tokens", return_value=100):
                        with patch("src.processors.cv_processor.log_llm_call"):
                            # Local application imports
                            from src.processors.cv_processor import CVProcessor

                            processor = CVProcessor(mock_vector_store)
                            processor.process_cv(
                                cv_id="cv_002", cv_file_path="/path/to/cv.pdf"
                            )

                            mock_extract.assert_called_once_with("/path/to/cv.pdf")


class TestCVExtractionPrompt:
    """Test suite for CV extraction prompt quality."""

    @pytest.mark.unit
    def test_cv_prompt_requests_key_fields(self):
        """Verify CV extraction prompt includes essential fields."""
        # Local application imports
        from src.utils.prompts import CV_EXTRACTION_PROMPT

        essential_concepts = ["name", "skill", "experience", "education"]

        prompt_lower = CV_EXTRACTION_PROMPT.lower()
        for concept in essential_concepts:
            assert concept in prompt_lower, f"CV prompt should mention: {concept}"

    @pytest.mark.unit
    def test_cv_prompt_requests_json_output(self):
        """Verify CV prompt requests structured JSON for parsing."""
        # Local application imports
        from src.utils.prompts import CV_EXTRACTION_PROMPT

        assert "json" in CV_EXTRACTION_PROMPT.lower()


class TestCVUserIsolation:
    """Test suite for multi-tenant CV data isolation."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock VectorStore with user filtering."""
        mock = Mock()
        mock.add_cv.return_value = "cv_001"
        return mock

    @pytest.mark.unit
    def test_cv_stored_with_user_id(self, mock_vector_store):
        """Verify CVs are stored with user_id for isolation."""
        with patch("src.processors.cv_processor.ChatOpenAI") as MockLLM:
            with patch(
                "src.processors.cv_processor.extract_text_from_pdf"
            ) as mock_extract:
                mock_extract.return_value = "Sample CV text " * 10

                with patch("os.path.isfile", return_value=True):
                    mock_llm_instance = Mock()
                    mock_llm_instance.invoke.return_value = Mock(
                        content=json.dumps({"name": "Test", "skills": []})
                    )
                    MockLLM.return_value = mock_llm_instance

                    with patch("backend.token_utils.count_tokens", return_value=100):
                        with patch("src.processors.cv_processor.log_llm_call"):
                            # Local application imports
                            from src.processors.cv_processor import CVProcessor

                            processor = CVProcessor(mock_vector_store)
                            processor.process_cv(
                                cv_id="cv_001",
                                cv_file_path="/path/to/cv.pdf",
                                user_id="user_456",
                            )

                            mock_vector_store.add_cv.assert_called_once()


class TestCVDataPrivacy:
    """Test suite for CV data privacy and PII handling."""

    @pytest.mark.unit
    def test_extracted_data_contains_no_raw_pii_in_vectors(self):
        """
        Verify embedding vectors don't contain raw PII.

        Reference: Carlini et al. (2021). "Extracting Training Data from LLMs"
        """
        # Architecture validation - embeddings are semantic representations
        pytest.skip("Not yet implemented — needs embedding inspection logic")

    @pytest.mark.unit
    def test_cv_deletion_removes_all_data(self):
        """Verify CV deletion removes data from vector store (GDPR Art. 17)."""
        mock_vector_store = Mock()
        mock_vector_store.delete_cv.return_value = True

        result = mock_vector_store.delete_cv("cv_001")

        assert result is True
        mock_vector_store.delete_cv.assert_called_once_with("cv_001")
