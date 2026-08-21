# Standard library imports
from functools import lru_cache

# Third-party imports
from fastapi import Depends

# Local application imports
from src.agents.memory import ContextManager, ConversationMemory
from src.agents.recruitment_agent import RecruitmentAgent
from src.config import Config
from src.database.vector_store import VectorStore
from src.processors.cv_processor import CVProcessor

# Lazy imports to avoid circular dependencies if any (though structured well)
from src.processors.job_processor import JobProcessor
from src.processors.matching_engine import MatchingEngine
from src.processors.question_generator import QuestionGenerator


@lru_cache()
def get_vector_store_singleton() -> VectorStore:
    """
    Create a singleton instance of VectorStore.
    LRU Cache ensures we only initialize it once per application lifetime.
    """
    return VectorStore(Config.CHROMA_PERSIST_DIR)


def get_vector_store() -> VectorStore:
    """
    Dependency provider for VectorStore.
    """
    return get_vector_store_singleton()


@lru_cache()
def get_recruitment_agent_singleton(vector_store: VectorStore) -> RecruitmentAgent:
    """Singleton for the heavy RecruitmentAgent"""
    return RecruitmentAgent(vector_store)


def get_recruitment_agent(
    vector_store: VectorStore = Depends(get_vector_store),
) -> RecruitmentAgent:
    return get_recruitment_agent_singleton(vector_store)


# --- Processors (Singleton-ish, though lightweight) ---


def get_job_processor(
    vector_store: VectorStore = Depends(get_vector_store),
) -> JobProcessor:
    return JobProcessor(vector_store)


def get_cv_processor(
    vector_store: VectorStore = Depends(get_vector_store),
) -> CVProcessor:
    return CVProcessor(vector_store)


def get_matching_engine(
    vector_store: VectorStore = Depends(get_vector_store),
) -> MatchingEngine:
    return MatchingEngine(vector_store)


def get_question_generator(
    vector_store: VectorStore = Depends(get_vector_store),
) -> QuestionGenerator:
    return QuestionGenerator(vector_store)


# --- Memory Dependencies ---
# These might need to be singletons to share state across requests if using in-memory dicts
@lru_cache()
def get_memory_singleton() -> ConversationMemory:
    return ConversationMemory()


def get_memory_dep() -> ConversationMemory:
    return get_memory_singleton()


@lru_cache()
def get_context_manager_singleton() -> ContextManager:
    # ContextManager likely depends on Memory
    return ContextManager(get_memory_singleton())


def get_context_manager_dep() -> ContextManager:
    return get_context_manager_singleton()


# Aliases for compatibility
get_conversation_memory = get_memory_dep
get_context_manager = get_context_manager_dep

# Third-party imports
# Third-party imports (after Config usage)
from langchain_openai import ChatOpenAI  # noqa: E402


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=Config.OPENAI_MODEL, temperature=0)
