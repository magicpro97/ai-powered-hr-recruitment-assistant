"""Question Generator for creating tailored interview questions."""

# Standard library imports
import json
from typing import Dict, List, Optional

# Third-party imports
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# Local application imports
from backend.logging_config import get_logger, log_llm_call
from src.config import Config
from src.database.vector_store import VectorStore
from src.utils.prompts import QUESTION_GENERATION_PROMPT

logger = get_logger(__name__)


class QuestionGenerator:
    """Generates tailored interview questions for candidates."""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize the question generator.

        Args:
            vector_store: VectorStore instance
        """
        self.vector_store = vector_store
        self.llm = ChatOpenAI(
            model=Config.OPENAI_MODEL,
            temperature=0.8,  # Higher temperature for more creative/diverse questions
        )
        logger.info(
            "QuestionGenerator initialized", model=Config.OPENAI_MODEL, temperature=0.8
        )

    def generate_questions(
        self, job_id: str, cv_id: str, matching_context: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Generate interview questions for a specific candidate and job.

        Args:
            job_id: Job identifier
            cv_id: Candidate CV identifier
            matching_context: Optional dict with 'strengths' and 'gaps' from matching results

        Returns:
            List of interview questions with metadata
        """
        # Get job and CV data
        job = self.vector_store.get_job(job_id)
        cv = self.vector_store.get_cv(cv_id)

        if not job or not cv:
            raise ValueError("Job or CV not found")

        job_data = job["metadata"]
        cv_data = cv["metadata"]

        # Format matching context if provided
        matching_info = ""
        if matching_context:
            strengths = matching_context.get("strengths", [])
            gaps = matching_context.get("gaps", [])

            if strengths:
                matching_info += "\n**Candidate's Key Strengths:**\n"
                matching_info += "\n".join([f"- {s}" for s in strengths])

            if gaps:
                matching_info += "\n\n**Areas to Explore (Gaps):**\n"
                matching_info += "\n".join([f"- {g}" for g in gaps])

        # Generate questions using LLM
        prompt = QUESTION_GENERATION_PROMPT.format(
            job_title=job_data.get("title", "Unknown Position"),
            job_requirements=json.dumps(job_data, indent=2),
            candidate_profile=json.dumps(cv_data, indent=2),
            matching_context=matching_info or "No matching analysis available.",
        )

        # Standard library imports
        import time

        start_time = time.time()
        response = self.llm.invoke([HumanMessage(content=prompt)])
        duration = time.time() - start_time

        # Count actual tokens
        # Local application imports
        from backend.token_utils import count_tokens

        prompt_tokens = count_tokens(prompt, Config.OPENAI_MODEL)
        completion_tokens = count_tokens(str(response.content), Config.OPENAI_MODEL)

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
            questions = json.loads(content)

            # Ensure it's a list
            if not isinstance(questions, list):
                questions = []

            # Validate each question has required fields
            validated_questions = []
            for q in questions:
                if isinstance(q, dict) and "question" in q:
                    q.setdefault("type", "Technical")
                    q.setdefault("focus_area", "General")
                    validated_questions.append(q)

            questions = validated_questions if validated_questions else []

            # Log successful LLM call with metrics
            log_llm_call(
                logger=logger,
                operation="generate_interview_questions",
                model=Config.OPENAI_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=duration,
                job_id=job_id,
                cv_id=cv_id,
                question_count=len(questions),
            )
            logger.info(
                "question_generation_success",
                job_id=job_id,
                cv_id=cv_id,
                question_count=len(questions),
            )

        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            # Log the error for debugging
            logger.error(
                "question_parsing_error",
                error=str(e),
                job_id=job_id,
                cv_id=cv_id,
                response_length=len(response.content),
            )
            # Fallback
            questions = []

        # If we still don't have questions, return empty list (will be handled by caller)
        return questions
