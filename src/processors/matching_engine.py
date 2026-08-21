"""
Matching Engine for ranking candidates against job requirements.

This module implements a hybrid matching approach combining:
1. Vector similarity search using sentence embeddings
2. LLM-based reasoning for detailed fit analysis

Academic References:
- Reimers & Gurevych (2019). "Sentence-BERT: Sentence Embeddings using Siamese
  BERT-Networks". EMNLP-IJCNLP 2019. DOI: 10.18653/v1/D19-1410
- Robertson & Zaragoza (2009). "The Probabilistic Relevance Framework: BM25
  and Beyond". Foundations and Trends in Information Retrieval.
- Wei et al. (2022). "Chain-of-Thought Prompting Elicits Reasoning in Large
  Language Models". NeurIPS 2022. arXiv:2201.11903
- Khattab et al. (2022). "Demonstrate-Search-Predict: Composing retrieval and
  language models for knowledge-intensive NLP". arXiv:2212.14024
"""

# Standard library imports
import asyncio
import json
import time
from typing import Dict, List

# Third-party imports
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

# Local application imports
from backend.access_control import Viewer, require_viewable
from backend.logging_config import get_logger, log_llm_call
from src.config import Config
from src.database.vector_store import VectorStore
from src.utils.prompts import MATCHING_PROMPT

logger = get_logger(__name__)


class MatchingEngine:
    """Matches candidates to job requirements and calculates fit scores."""

    def __init__(self, vector_store: VectorStore):
        """
        Initialize the matching engine.

        Args:
            vector_store: VectorStore instance
        """
        self.vector_store = vector_store
        self.llm = ChatOpenAI(model=Config.OPENAI_MODEL, temperature=0)
        logger.info("MatchingEngine initialized", model=Config.OPENAI_MODEL)

    def match_candidates(
        self,
        job_id: str,
        viewer: Viewer,
        top_k: int = 10,
        lang: str = "en",
        owner_only: bool = False,
    ) -> List[Dict]:
        """
        Find and rank candidates for a job.

        Args:
            job_id: Job identifier
            top_k: Number of top candidates to return

        Returns:
            List of candidates with fit scores and analysis
        """
        # Get job data
        job = self.vector_store.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        require_viewable(viewer, job["metadata"])

        job_text = job["text"]
        job_data = job["metadata"]

        # Search for similar CVs using vector similarity
        search_results = self.vector_store.search_similar_cvs(
            job_text,
            viewer=viewer,
            n_results=top_k,
            owner_only=owner_only,
        )

        # Calculate detailed fit scores using LLM
        candidates = []
        if not search_results.get("ids") or not search_results["ids"][0]:
            logger.warning("No CVs found for matching", job_id=job_id)
            return candidates

        for i, cv_id in enumerate(search_results["ids"][0]):
            cv = self.vector_store.get_cv(cv_id)
            if not cv:
                continue
            if owner_only and cv["metadata"].get("owner_user_id") != viewer.user_id:
                continue

            # Defense-in-depth: verify CV is viewable before LLM scoring
            try:
                require_viewable(viewer, cv["metadata"])
            except PermissionError:
                logger.warning(
                    "CV visibility check failed during matching",
                    cv_id=cv_id,
                    viewer=viewer.user_id,
                )
                continue

            distance = search_results["distances"][0][i]
            similarity = 1 - distance

            match_data = self._calculate_fit_score(
                job_data, cv["metadata"], job_id=job_id, cv_id=cv_id, lang=lang
            )

            candidates.append(
                {
                    "cv_id": cv_id,
                    "name": cv["metadata"].get("name", "Unknown"),
                    "fit_score": match_data.get("fit_score", 0),
                    "strengths": match_data.get("strengths", []),
                    "gaps": match_data.get("gaps", []),
                    "reasoning": match_data.get("reasoning", ""),
                    "similarity_score": similarity,
                    "metadata": cv["metadata"],
                }
            )

        # Sort by fit score
        candidates.sort(key=lambda x: x["fit_score"], reverse=True)

        # Deduplicate by email (or name+phone fallback), keep highest score
        seen = set()
        unique_candidates = []
        for c in candidates:
            email = c["metadata"].get("email", "").strip().lower()
            name = c["metadata"].get("name", "").strip().lower()
            phone = c["metadata"].get("phone", "").strip()
            key = email if email else f"{name}|{phone}"
            if not key or key not in seen:
                if key:
                    seen.add(key)
                unique_candidates.append(c)
        candidates = unique_candidates

        return candidates

    def _calculate_fit_score(
        self,
        job_data: Dict,
        candidate_data: Dict,
        job_id: str = None,
        cv_id: str = None,
        lang: str = "en",
    ) -> Dict:
        """
        Use LLM to calculate detailed fit score.

        Args:
            job_data: Structured job requirements
            candidate_data: Structured candidate profile
            job_id: Job identifier (optional, for logging)
            cv_id: CV identifier (optional, for logging)
            lang: Output language ("vi" or "en")

        Returns:
            Dictionary with fit_score, strengths, gaps, reasoning
        """
        lang_instruction = (
            "\n\nIMPORTANT: You MUST write ALL strengths, gaps, and reasoning in Vietnamese (tiếng Việt), regardless of the language of the job description or CV."
            if lang == "vi"
            else ""
        )
        prompt = (
            MATCHING_PROMPT.format(
                job_requirements=json.dumps(job_data, indent=2),
                candidate_profile=json.dumps(candidate_data, indent=2),
            )
            + lang_instruction
        )

        start_time = time.time()
        response = self.llm.invoke([HumanMessage(content=prompt)])
        duration = time.time() - start_time

        # Count actual tokens for operational logging.
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
            match_data = json.loads(content)

            # Ensure required fields exist
            match_data.setdefault("fit_score", 50)
            match_data.setdefault("strengths", [])
            match_data.setdefault("gaps", [])
            match_data.setdefault("reasoning", "Analysis completed")

            # Ensure fit_score is an integer between 0-100
            if isinstance(match_data["fit_score"], str):
                # Try to extract number from string like "85%" or "85"
                # Standard library imports
                import re

                numbers = re.findall(r"\d+", match_data["fit_score"])
                if numbers:
                    match_data["fit_score"] = int(numbers[0])
                else:
                    match_data["fit_score"] = 50

            match_data["fit_score"] = max(0, min(100, int(match_data["fit_score"])))

            # Log successful LLM call with token counts
            log_llm_call(
                logger=logger,
                operation="match_candidate",
                model=Config.OPENAI_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=duration,
                job_id=job_id,
                cv_id=cv_id,
                fit_score=match_data["fit_score"],
                strengths_count=len(match_data["strengths"]),
                gaps_count=len(match_data["gaps"]),
            )

            logger.debug(
                "Fit score calculated",
                fit_score=match_data["fit_score"],
                num_strengths=len(match_data["strengths"]),
                num_gaps=len(match_data["gaps"]),
            )

        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            # Log the error for debugging
            logger.error(
                "Error parsing matching response",
                error=str(e),
                response_length=len(response.content),
            )

            # Fallback
            match_data = {
                "fit_score": 50,
                "strengths": [],
                "gaps": [],
                "reasoning": "Unable to analyze match details",
            }

        return match_data

    async def _calculate_fit_score_async(
        self,
        job_data: Dict,
        candidate_data: Dict,
        job_id: str = None,
        cv_id: str = None,
        lang: str = "en",
    ) -> Dict:
        """Async version of _calculate_fit_score using ainvoke."""
        lang_instruction = (
            "\n\nIMPORTANT: You MUST write ALL strengths, gaps, and reasoning in Vietnamese (tiếng Việt), regardless of the language of the job description or CV."
            if lang == "vi"
            else ""
        )
        prompt = (
            MATCHING_PROMPT.format(
                job_requirements=json.dumps(job_data, indent=2),
                candidate_profile=json.dumps(candidate_data, indent=2),
            )
            + lang_instruction
        )

        start_time = time.time()
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        duration = time.time() - start_time

        # Local application imports
        from backend.token_utils import count_tokens

        prompt_tokens = count_tokens(prompt, Config.OPENAI_MODEL)
        completion_tokens = count_tokens(str(response.content), Config.OPENAI_MODEL)

        try:
            content = str(response.content).strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            match_data = json.loads(content)
            match_data.setdefault("fit_score", 50)
            match_data.setdefault("strengths", [])
            match_data.setdefault("gaps", [])
            match_data.setdefault("reasoning", "Analysis completed")

            if isinstance(match_data["fit_score"], str):
                # Standard library imports
                import re

                numbers = re.findall(r"\d+", match_data["fit_score"])
                match_data["fit_score"] = int(numbers[0]) if numbers else 50

            match_data["fit_score"] = max(0, min(100, int(match_data["fit_score"])))

            log_llm_call(
                logger=logger,
                operation="match_candidate",
                model=Config.OPENAI_MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=duration,
                job_id=job_id,
                cv_id=cv_id,
                fit_score=match_data["fit_score"],
                strengths_count=len(match_data["strengths"]),
                gaps_count=len(match_data["gaps"]),
            )
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.error(
                "Error parsing matching response",
                error=str(e),
                response_length=len(response.content),
            )
            match_data = {
                "fit_score": 50,
                "strengths": [],
                "gaps": [],
                "reasoning": "Unable to analyze match details",
            }

        return match_data

    async def match_candidates_async(
        self,
        job_id: str,
        viewer: Viewer,
        top_k: int = 10,
        lang: str = "en",
        owner_only: bool = False,
    ) -> List[Dict]:
        """Async version of match_candidates — runs LLM calls in parallel."""
        job = self.vector_store.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        require_viewable(viewer, job["metadata"])

        job_text = job["text"]
        job_data = job["metadata"]
        # Guest and explicit demo sandboxes must not include foreign public CVs.
        guest_owner = (viewer.user_id or "").startswith("guest_")

        search_results = self.vector_store.search_similar_cvs(
            job_text,
            viewer=viewer,
            n_results=top_k,
            owner_only=owner_only,
        )

        if not search_results.get("ids") or not search_results["ids"][0]:
            logger.warning("No CVs found for matching", job_id=job_id)
            return []

        # Collect CV data
        cv_entries = []
        for i, cv_id in enumerate(search_results["ids"][0]):
            cv = self.vector_store.get_cv(cv_id)
            if not cv:
                continue
            if (guest_owner or owner_only) and cv["metadata"].get(
                "owner_user_id"
            ) != viewer.user_id:
                continue

            # Defense-in-depth: verify CV is viewable before LLM scoring
            try:
                require_viewable(viewer, cv["metadata"])
            except PermissionError:
                logger.warning(
                    "CV visibility check failed during async matching",
                    cv_id=cv_id,
                    viewer=viewer.user_id,
                )
                continue

            distance = search_results["distances"][0][i]
            similarity = 1 - distance
            cv_entries.append((cv_id, cv, similarity))

        # Run LLM calls in parallel (max 10 concurrent to avoid rate limits)
        semaphore = asyncio.Semaphore(10)

        async def process_cv(cv_id, cv, similarity):
            async with semaphore:
                match_data = await self._calculate_fit_score_async(
                    job_data, cv["metadata"], job_id=job_id, cv_id=cv_id, lang=lang
                )
            return {
                "cv_id": cv_id,
                "name": cv["metadata"].get("name", "Unknown"),
                "fit_score": match_data.get("fit_score", 0),
                "strengths": match_data.get("strengths", []),
                "gaps": match_data.get("gaps", []),
                "reasoning": match_data.get("reasoning", ""),
                "similarity_score": similarity,
                "metadata": cv["metadata"],
            }

        tasks = [process_cv(cv_id, cv, sim) for cv_id, cv, sim in cv_entries]
        candidates = await asyncio.gather(*tasks)
        candidates = list(candidates)

        # Sort by fit score
        candidates.sort(key=lambda x: x["fit_score"], reverse=True)

        # Deduplicate
        seen = set()
        unique_candidates = []
        for c in candidates:
            email = c["metadata"].get("email", "").strip().lower()
            name = c["metadata"].get("name", "").strip().lower()
            phone = c["metadata"].get("phone", "").strip()
            key = email if email else f"{name}|{phone}"
            if not key or key not in seen:
                if key:
                    seen.add(key)
                unique_candidates.append(c)

        return unique_candidates
