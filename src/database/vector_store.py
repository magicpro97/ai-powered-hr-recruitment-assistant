"""
Vector database wrapper using ChromaDB with user ownership support.

This module implements semantic search capabilities using dense vector embeddings
stored in ChromaDB for efficient similarity retrieval.

Academic References:
- Johnson et al. (2019). "Billion-scale similarity search with GPUs".
  IEEE Transactions on Big Data. (FAISS foundations)
- Chroma Team (2023). "ChromaDB: The AI-native open-source embedding database".
  https://docs.trychroma.com/
- Karpukhin et al. (2020). "Dense Passage Retrieval for Open-Domain Question
  Answering". EMNLP 2020. arXiv:2004.04906
- Neelakantan et al. (2022). "Text and Code Embeddings by Contrastive Pre-Training".
  arXiv:2201.10005 (OpenAI text-embedding models)
"""

# Standard library imports
import json
import logging
from typing import Dict, List, Optional

# Third-party imports
import chromadb
from chromadb.config import Settings

# Local application imports
from backend.access_control import (
    SYSTEM_USER_ID,
    Viewer,
    can_view_resource,
    visibility_where,
)

logger = logging.getLogger(__name__)


class VectorStore:
    """Wrapper for ChromaDB vector database operations with user ownership."""

    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize the vector store.

        Args:
            persist_directory: Directory to persist the database
        """
        # Use PersistentClient to ensure data is saved to disk
        self.client = chromadb.PersistentClient(
            path=persist_directory, settings=Settings(anonymized_telemetry=False)
        )

        # Create collections for jobs and CVs
        self.jobs_collection = self.client.get_or_create_collection(
            name="job_descriptions",
            metadata={"description": "Job descriptions and requirements"},
        )

        self.cvs_collection = self.client.get_or_create_collection(
            name="candidate_cvs", metadata={"description": "Candidate CVs and profiles"}
        )

    def _prepare_metadata(self, data: Dict) -> Dict:
        """
        Prepare metadata for ChromaDB by converting lists to JSON strings.
        ChromaDB only accepts str, int, float, bool as metadata values.

        Args:
            data: Dictionary with potentially nested data

        Returns:
            Flattened dictionary with only primitive types
        """
        metadata = {}
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                # Convert lists and dicts to JSON strings
                metadata[key] = json.dumps(value)
            elif isinstance(value, (str, int, float, bool)):
                # Keep primitive types as-is
                metadata[key] = value
            elif value is None:
                # Convert None to empty string
                metadata[key] = ""
            else:
                # Convert other types to string
                metadata[key] = str(value)
        return metadata

    def _restore_metadata(self, metadata: Dict) -> Dict:
        """
        Restore metadata by parsing JSON strings back to lists/dicts.

        Args:
            metadata: Dictionary from ChromaDB

        Returns:
            Dictionary with restored data structures
        """
        restored = {}
        for key, value in metadata.items():
            if isinstance(value, str) and (
                value.startswith("[") or value.startswith("{")
            ):
                try:
                    # Try to parse JSON strings back to lists/dicts
                    restored[key] = json.loads(value)
                except json.JSONDecodeError:
                    # If parsing fails, keep as string
                    restored[key] = value
            else:
                restored[key] = value
        return restored

    def add_job(
        self,
        job_id: str,
        job_text: str,
        job_data: Dict,
        user_id: str = SYSTEM_USER_ID,
        is_public: bool = False,
    ):
        """
        Add a job description to the vector store.

        Args:
            job_id: Unique identifier for the job
            job_text: Full text of the job description
            job_data: Structured data extracted from the job
            user_id: Owner user ID (default: system for public data)
            is_public: Whether this job is visible to all users
        """
        # Add ownership metadata
        job_data["owner_user_id"] = user_id
        job_data["is_public"] = is_public

        # Convert lists to JSON strings for ChromaDB compatibility
        metadata = self._prepare_metadata(job_data)

        self.jobs_collection.add(
            documents=[job_text], metadatas=[metadata], ids=[job_id]
        )

    def add_cv(
        self,
        cv_id: str,
        cv_text: str,
        cv_data: Dict,
        user_id: str = SYSTEM_USER_ID,
        is_public: bool = False,
    ):
        """
        Add a CV to the vector store.

        Args:
            cv_id: Unique identifier for the CV
            cv_text: Full text of the CV
            cv_data: Structured data extracted from the CV
            user_id: Owner user ID (default: system for public data)
            is_public: Whether this CV is visible to all users
        """
        # Add ownership metadata
        cv_data["owner_user_id"] = user_id
        cv_data["is_public"] = is_public

        # Convert lists to JSON strings for ChromaDB compatibility
        metadata = self._prepare_metadata(cv_data)

        self.cvs_collection.add(documents=[cv_text], metadatas=[metadata], ids=[cv_id])

    def search_similar_cvs(
        self,
        job_text: str,
        viewer: Viewer,
        n_results: int = 10,
        owner_only: bool = False,
    ) -> Dict:
        """Search CVs visible to viewer before similarity retrieval."""
        if owner_only:
            if not viewer.user_id:
                raise PermissionError("Owner-only search requires an owner")
            where = {"owner_user_id": viewer.user_id}
        else:
            where = visibility_where(viewer)
        query = {"query_texts": [job_text], "n_results": n_results}
        if where is not None:
            query["where"] = where
        return self.cvs_collection.query(**query)

    def get_job(self, job_id: str) -> Optional[Dict]:
        """
        Retrieve a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job data or None if not found
        """
        try:
            result = self.jobs_collection.get(ids=[job_id])
            if result["ids"]:
                metadata = self._restore_metadata(result["metadatas"][0])
                return {
                    "id": result["ids"][0],
                    "text": result["documents"][0],
                    "metadata": metadata,
                }
        except Exception as e:
            logger.warning("Failed to get job", job_id=job_id, error=str(e))
        return None

    def get_cv(self, cv_id: str) -> Optional[Dict]:
        """
        Retrieve a CV by ID.

        Args:
            cv_id: CV identifier

        Returns:
            CV data or None if not found
        """
        try:
            result = self.cvs_collection.get(ids=[cv_id])
            if result["ids"]:
                metadata = self._restore_metadata(result["metadatas"][0])
                return {
                    "id": result["ids"][0],
                    "text": result["documents"][0],
                    "metadata": metadata,
                }
        except Exception as e:
            logger.warning("Failed to get CV", cv_id=cv_id, error=str(e))
        return None

    def list_all_jobs(
        self,
        user_id: Optional[str] = None,
        include_public: bool = True,
        is_admin: bool = False,
    ) -> List[Dict]:
        """
        Get all jobs from the database, optionally filtered by user.

        Args:
            user_id: If provided, filter to this user's jobs and public jobs
            include_public: Whether to include public jobs (default True)
            is_admin: If True, return all jobs without filtering

        Returns:
            List of jobs accessible to the user
        """
        # Use ChromaDB where filter for user-scoped queries when possible
        if user_id and not is_admin:
            or_filters: list = [
                {"owner_user_id": user_id},
                {"owner_user_id": SYSTEM_USER_ID},
            ]
            if include_public:
                or_filters.append({"is_public": True})
            result = self.jobs_collection.get(where={"$or": or_filters})
        else:
            result = self.jobs_collection.get()

        jobs = []
        for i in range(len(result["ids"])):
            metadata = self._restore_metadata(result["metadatas"][i])

            if not is_admin and not can_view_resource(
                Viewer(user_id=user_id), metadata
            ):
                continue
            if (
                not include_public
                and metadata.get("owner_user_id") != user_id
                and not is_admin
            ):
                continue

            jobs.append(
                {
                    "id": result["ids"][i],
                    "text": result["documents"][i],
                    "metadata": metadata,
                }
            )
        return jobs

    def list_all_cvs(
        self,
        user_id: Optional[str] = None,
        include_public: bool = True,
        is_admin: bool = False,
    ) -> List[Dict]:
        """
        Get all CVs from the database, optionally filtered by user.

        Args:
            user_id: If provided, filter to this user's CVs and public CVs
            include_public: Whether to include public CVs (default True)
            is_admin: If True, return all CVs without filtering

        Returns:
            List of CVs accessible to the user
        """
        # Use ChromaDB where filter for user-scoped queries when possible
        if not is_admin and user_id:
            or_filters: list = [
                {"owner_user_id": user_id},
                {"owner_user_id": SYSTEM_USER_ID},
            ]
            if include_public:
                or_filters.append({"is_public": True})
            result = self.cvs_collection.get(where={"$or": or_filters})
        elif not is_admin:
            # No user_id: only public CVs
            result = self.cvs_collection.get(where={"is_public": True})
        else:
            result = self.cvs_collection.get()

        cvs = []
        for i in range(len(result["ids"])):
            metadata = self._restore_metadata(result["metadatas"][i])
            if not is_admin and not can_view_resource(
                Viewer(user_id=user_id), metadata
            ):
                continue
            if (
                not include_public
                and metadata.get("owner_user_id") != user_id
                and not is_admin
            ):
                continue
            cvs.append(
                {
                    "id": result["ids"][i],
                    "text": result["documents"][i],
                    "metadata": metadata,
                }
            )
        return cvs

    def update_job_visibility(
        self, job_id: str, is_public: bool, user_id: Optional[str] = None
    ) -> bool:
        """
        Update the public visibility of a job.

        Args:
            job_id: Job identifier
            is_public: New visibility setting
            user_id: User making the request (None = admin, skips ownership check)
        """
        job = self.get_job(job_id)
        if not job:
            return False

        if user_id:
            owner = job["metadata"].get("owner_user_id", SYSTEM_USER_ID)
            if owner != user_id:
                return False

        # Update metadata
        job["metadata"]["is_public"] = is_public
        metadata = self._prepare_metadata(job["metadata"])

        self.jobs_collection.update(ids=[job_id], metadatas=[metadata])
        return True

    def update_cv_visibility(
        self, cv_id: str, is_public: bool, user_id: Optional[str] = None
    ) -> bool:
        """
        Update the public visibility of a CV.

        Args:
            cv_id: CV identifier
            is_public: New visibility setting
            user_id: User making the request (None = admin, skips ownership check)
        """
        cv = self.get_cv(cv_id)
        if not cv:
            return False

        if user_id:
            owner = cv["metadata"].get("owner_user_id", SYSTEM_USER_ID)
            if owner != user_id:
                return False

        # Update metadata
        cv["metadata"]["is_public"] = is_public
        metadata = self._prepare_metadata(cv["metadata"])

        self.cvs_collection.update(ids=[cv_id], metadatas=[metadata])
        return True

    def update_job_metadata(self, job_id: str, new_metadata: Dict) -> bool:
        """Update all metadata fields for a job."""
        metadata = self._prepare_metadata(new_metadata)
        try:
            self.jobs_collection.update(ids=[job_id], metadatas=[metadata])
            return True
        except Exception:
            return False

    def update_cv_metadata(self, cv_id: str, new_metadata: Dict) -> bool:
        """Update all metadata fields for a CV."""
        metadata = self._prepare_metadata(new_metadata)
        try:
            self.cvs_collection.update(ids=[cv_id], metadatas=[metadata])
            return True
        except Exception:
            return False

    def migrate_existing_to_system(self) -> Dict[str, int]:
        """
        Migrate existing data without ownership to system user.

        Returns:
            Count of migrated jobs and CVs
        """
        migrated = {"jobs": 0, "cvs": 0}

        # Migrate jobs
        result = self.jobs_collection.get()
        for i in range(len(result["ids"])):
            metadata = result["metadatas"][i]
            if "owner_user_id" not in metadata:
                metadata["owner_user_id"] = SYSTEM_USER_ID
                metadata["is_public"] = True  # Existing data becomes public
                self.jobs_collection.update(
                    ids=[result["ids"][i]], metadatas=[metadata]
                )
                migrated["jobs"] += 1

        # Migrate CVs
        result = self.cvs_collection.get()
        for i in range(len(result["ids"])):
            metadata = result["metadatas"][i]
            if "owner_user_id" not in metadata:
                metadata["owner_user_id"] = SYSTEM_USER_ID
                metadata["is_public"] = True  # Existing data becomes public
                self.cvs_collection.update(ids=[result["ids"][i]], metadatas=[metadata])
                migrated["cvs"] += 1

        return migrated

    def delete_job(self, job_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a job by ID.

        Args:
            job_id: Job identifier
            user_id: If provided, only delete if user is owner

        Returns:
            True if deleted successfully
        """
        try:
            if user_id:
                job = self.get_job(job_id)
                if not job:
                    return False
                owner = job["metadata"].get("owner_user_id", SYSTEM_USER_ID)
                if owner != user_id:
                    return False  # Not authorized

            self.jobs_collection.delete(ids=[job_id])
            return True
        except Exception:
            return False

    def delete_cv(self, cv_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a CV by ID.

        Args:
            cv_id: CV identifier
            user_id: If provided, only delete if user is owner

        Returns:
            True if deleted successfully
        """
        try:
            if user_id:
                cv = self.get_cv(cv_id)
                if not cv:
                    return False
                owner = cv["metadata"].get("owner_user_id", SYSTEM_USER_ID)
                if owner != user_id:
                    return False  # Not authorized

            self.cvs_collection.delete(ids=[cv_id])
            return True
        except Exception:
            return False

    def delete_test_data(self, test_email_pattern: str = "e2e@") -> Dict[str, int]:
        """
        Delete all test data matching the email pattern.
        Used for E2E test cleanup.

        Args:
            test_email_pattern: Email pattern to identify test data owner

        Returns:
            Count of deleted jobs and CVs
        """
        deleted = {"jobs": 0, "cvs": 0}

        # Delete test jobs
        result = self.jobs_collection.get()
        jobs_to_delete = []
        for i in range(len(result["ids"])):
            metadata = result["metadatas"][i]
            owner = metadata.get("owner_user_id", "")
            if owner.startswith(test_email_pattern) or owner.endswith(
                test_email_pattern
            ):
                jobs_to_delete.append(result["ids"][i])

        if jobs_to_delete:
            self.jobs_collection.delete(ids=jobs_to_delete)
            deleted["jobs"] = len(jobs_to_delete)

        # Delete test CVs
        result = self.cvs_collection.get()
        cvs_to_delete = []
        for i in range(len(result["ids"])):
            metadata = result["metadatas"][i]
            owner = metadata.get("owner_user_id", "")
            if owner.startswith(test_email_pattern) or owner.endswith(
                test_email_pattern
            ):
                cvs_to_delete.append(result["ids"][i])

        if cvs_to_delete:
            self.cvs_collection.delete(ids=cvs_to_delete)
            deleted["cvs"] = len(cvs_to_delete)

        return deleted
