"""
CV Processor for extracting candidate information from resumes.

This module implements Named Entity Recognition (NER) and information extraction
from CV documents using LLM-based parsing.

Academic References:
- Devlin et al. (2019). "BERT: Pre-training of Deep Bidirectional Transformers
  for Language Understanding". NAACL 2019. arXiv:1810.04805
- Luo et al. (2021). "Resume Parsing using Named Entity Recognition".
  International Journal of Computer Applications.
- Achiam et al. (2023). "GPT-4 Technical Report". arXiv:2303.08774
- Radford et al. (2019). "Language Models are Unsupervised Multitask Learners".
  OpenAI Technical Report (GPT-2 foundations).
"""

# Standard library imports
import json
import os
import time
from typing import Dict, Optional

# Third-party imports
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# Local application imports
from backend.logging_config import get_logger, log_llm_call
from src.config import Config
from src.database.vector_store import SYSTEM_USER_ID, VectorStore
from src.utils.file_utils import extract_text_from_pdf
from src.utils.prompts import CV_EXTRACTION_PROMPT

logger = get_logger(__name__)


class CVProcessor:
    """Processes CVs and stores candidate profiles in the vector database."""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize the CV processor.

        Args:
            vector_store: VectorStore instance for storage
        """
        self.vector_store = vector_store
        self.llm = ChatOpenAI(model=Config.OPENAI_MODEL, temperature=0)
        logger.info("CVProcessor initialized", model=Config.OPENAI_MODEL)

    def process_cv(
        self,
        cv_id: str,
        cv_file_path: str,
        user_id: str = SYSTEM_USER_ID,
        is_public: bool = False,
    ) -> Dict:
        """
        Process a CV file and store candidate profile.

        Args:
            cv_id: Unique identifier for the CV
            cv_file_path: Path to the CV file (PDF)
            user_id: Owner user ID
            is_public: Whether CV should be visible to all users

        Returns:
            Extracted candidate data as a dictionary
        """
        logger.info(
            "Processing CV", cv_id=cv_id, file_path=cv_file_path, user_id=user_id
        )

        # Extract text from PDF
        if not os.path.isfile(cv_file_path):
            raise FileNotFoundError(f"CV file not found: {cv_file_path}")
        cv_text = extract_text_from_pdf(cv_file_path)
        logger.debug("PDF text extracted", cv_id=cv_id, text_length=len(cv_text))

        # Reject image-only PDFs with no extractable text
        if len(cv_text.strip()) < 50:
            raise ValueError(
                "Cannot extract text from this PDF. It may be a scanned image. "
                "Please upload a text-based PDF or use OCR to convert the file first."
            )

        # Use LLM to extract structured data
        prompt = CV_EXTRACTION_PROMPT.format(cv_text=cv_text)

        start_time = time.time()
        response = self.llm.invoke([HumanMessage(content=prompt)])
        duration = time.time() - start_time

        # Count actual tokens
        # Local application imports
        from backend.token_utils import count_tokens

        prompt_tokens = count_tokens(prompt, Config.OPENAI_MODEL)
        completion_tokens = count_tokens(str(response.content), Config.OPENAI_MODEL)

        # Log LLM call with token counts
        log_llm_call(
            logger=logger,
            operation="extract_cv_profile",
            model=Config.OPENAI_MODEL,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration=duration,
            cv_id=cv_id,
            text_length=len(cv_text),
        )

        # Parse JSON response
        try:
            # Get response content as string
            content = str(response.content).strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]

            if content.endswith("```"):
                content = content[:-3]

            content = content.strip()

            # Parse JSON
            cv_data = json.loads(content)

            # Ensure required fields exist
            cv_data.setdefault("name", "Unknown Candidate")
            cv_data.setdefault("email", "")
            cv_data.setdefault("phone", "")
            cv_data.setdefault("skills", [])
            cv_data.setdefault("experience_years", 0)
            cv_data.setdefault("education", "")
            cv_data.setdefault("work_history", [])
            cv_data.setdefault("summary", "")

            # Coerce experience_years to int (LLM may return string like "5")
            exp = cv_data.get("experience_years")
            if isinstance(exp, str):
                try:
                    cv_data["experience_years"] = int(
                        "".join(c for c in exp if c.isdigit()) or "0"
                    )
                except ValueError:
                    cv_data["experience_years"] = 0
            elif not isinstance(exp, (int, float)):
                cv_data["experience_years"] = 0
            else:
                cv_data["experience_years"] = int(exp)

        except (json.JSONDecodeError, AttributeError) as e:
            # Log the error for debugging
            logger.error(
                "Error parsing CV response",
                error=str(e),
                response_length=len(response.content),
            )
            # Fallback: create basic structure
            cv_data = {
                "name": "Unknown Candidate",
                "email": "",
                "phone": "",
                "skills": [],
                "experience_years": 0,
                "education": "",
                "work_history": [],
                "summary": "",
            }

        # Add file name (not full path) to metadata
        cv_data["file_path"] = os.path.basename(cv_file_path)

        # Store in vector database with ownership
        self.vector_store.add_cv(
            cv_id, cv_text, cv_data, user_id=user_id, is_public=is_public
        )

        return cv_data

    def get_cv(self, cv_id: str) -> Dict:
        """
        Retrieve a CV by ID.

        Args:
            cv_id: CV identifier

        Returns:
            CV data dictionary
        """
        result = self.vector_store.get_cv(cv_id)
        return result if result is not None else {}

    def list_all_cvs(
        self,
        user_id: Optional[str] = None,
        include_public: bool = True,
        is_admin: bool = False,
    ):
        """
        Get all CVs from the database, optionally filtered by user.
        """
        return self.vector_store.list_all_cvs(
            user_id=user_id, include_public=include_public, is_admin=is_admin
        )
