"""
Job Description Processor for extracting and storing job requirements.

This module implements information extraction from unstructured job descriptions
using Large Language Models with structured output parsing.

Academic References:
- Brown et al. (2020). "Language Models are Few-Shot Learners". NeurIPS 2020.
  arXiv:2005.14165 (GPT-3 and prompt engineering foundations)
- Ouyang et al. (2022). "Training language models to follow instructions with
  human feedback". NeurIPS 2022. arXiv:2203.02155 (InstructGPT/RLHF)
- Wei et al. (2022). "Emergent Abilities of Large Language Models".
  TMLR 2022. arXiv:2206.07682
- Sanh et al. (2022). "Multitask Prompted Training Enables Zero-Shot Task
  Generalization". ICLR 2022. arXiv:2110.08207
"""

# Standard library imports
import json
import time
from typing import Dict, Optional

# Third-party imports
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# Local application imports
from backend.logging_config import get_logger, log_llm_call
from src.config import Config
from src.database.vector_store import SYSTEM_USER_ID, VectorStore
from src.utils.prompts import JOB_EXTRACTION_PROMPT

logger = get_logger(__name__)


class JobProcessor:
    """Processes job descriptions and stores them in the vector database."""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize the job processor.

        Args:
            vector_store: VectorStore instance for storage
        """
        self.vector_store = vector_store
        self.llm = ChatOpenAI(model=Config.OPENAI_MODEL, temperature=0)
        logger.info("JobProcessor initialized", model=Config.OPENAI_MODEL)

    def process_job_description(
        self,
        job_id: str,
        job_text: str,
        user_id: str = SYSTEM_USER_ID,
        is_public: bool = False,
    ) -> Dict:
        """
        Process a job description and store it.

        Args:
            job_id: Unique identifier for the job
            job_text: Raw job description text
            user_id: Owner user ID
            is_public: Whether job should be visible to all users

        Returns:
            Extracted job data as a dictionary
        """
        logger.info(
            "Processing job description",
            job_id=job_id,
            text_length=len(job_text),
            user_id=user_id,
        )

        # Use LLM to extract structured data
        prompt = JOB_EXTRACTION_PROMPT.format(job_description=job_text)

        start_time = time.time()
        response = self.llm.invoke([HumanMessage(content=prompt)])
        duration = time.time() - start_time

        # Count actual tokens
        # Local application imports
        from backend.token_utils import count_tokens

        prompt_tokens = count_tokens(prompt, Config.OPENAI_MODEL)
        completion_tokens = count_tokens(str(response.content), Config.OPENAI_MODEL)

        # Parse JSON response
        try:
            # Get response content as string
            content = str(response.content).strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            elif content.startswith("```"):
                content = content[3:]  # Remove ```

            if content.endswith("```"):
                content = content[:-3]  # Remove trailing ```

            content = content.strip()

            # Parse JSON
            job_data = json.loads(content)

            # Ensure required fields exist with proper defaults
            job_data.setdefault("title", "Unknown Position")
            job_data.setdefault("required_skills", [])
            job_data.setdefault("preferred_skills", [])
            job_data.setdefault("experience_years", "0")
            job_data.setdefault("education", "")
            job_data.setdefault("responsibilities", [])
            job_data.setdefault("requirements", [])

            # Convert experience_years to string if it's a number
            if isinstance(job_data.get("experience_years"), (int, float)):
                job_data["experience_years"] = str(job_data["experience_years"])

            # Log successful LLM call with token counts
            log_llm_call(
                logger=logger,
                operation="extract_job_requirements",
                model=Config.OPENAI_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=duration,
                job_id=job_id,
                skill_count=len(job_data.get("required_skills", [])),
            )

            logger.info(
                "Job extraction successful",
                job_id=job_id,
                title=job_data.get("title"),
                required_skills_count=len(job_data.get("required_skills", [])),
            )

        except (json.JSONDecodeError, AttributeError) as e:
            # Log the error for debugging
            logger.error(
                "Error parsing job description response",
                job_id=job_id,
                error=str(e),
                response_length=len(response.content),
            )
            # Fallback: create basic structure
            job_data = {
                "title": "Unknown Position",
                "required_skills": [],
                "preferred_skills": [],
                "experience_years": "0",
                "education": "",
                "responsibilities": [],
                "requirements": [],
            }

        # Store in vector database with ownership
        self.vector_store.add_job(
            job_id, job_text, job_data, user_id=user_id, is_public=is_public
        )

        return job_data

    def get_job(self, job_id: str) -> Dict:
        """
        Retrieve a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job data dictionary
        """
        result = self.vector_store.get_job(job_id)
        return result if result is not None else {}

    def list_all_jobs(
        self,
        user_id: Optional[str] = None,
        include_public: bool = True,
        is_admin: bool = False,
    ):
        """
        Get all jobs from the database, optionally filtered by user.
        """
        return self.vector_store.list_all_jobs(
            user_id=user_id, include_public=include_public, is_admin=is_admin
        )
