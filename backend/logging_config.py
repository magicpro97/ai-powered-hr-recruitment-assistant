"""
Structured Logging Configuration
Uses structlog for production-grade logging with context
"""

# Standard library imports
import logging
import sys
from typing import Any, Optional

# Third-party imports
import structlog


def setup_logging(level: str = "INFO") -> None:
    """
    Configure structured logging for the application

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            (
                structlog.dev.ConsoleRenderer()
                if sys.stdout.isatty()
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """
    Get a structured logger instance

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding structured logging context"""

    def __init__(self, **kwargs: Any):
        self.context = kwargs

    def __enter__(self) -> None:
        structlog.contextvars.bind_contextvars(**self.context)

    def __exit__(self, *args: Any) -> None:
        structlog.contextvars.unbind_contextvars(*self.context.keys())


def log_llm_call(
    logger: Any,
    operation: str,
    model: str,
    prompt_length: Optional[int] = None,
    response_length: Optional[int] = None,
    duration: Optional[float] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    **kwargs: Any,
) -> None:
    """
    Log LLM API call with accurate token counting

    Args:
        logger: Structured logger instance
        operation: Operation name (e.g., 'extract_job', 'match_candidate')
        model: Model name (e.g., 'gpt-4o-mini')
        prompt_length: Character length of prompt (deprecated, use prompt_tokens)
        response_length: Character length of response (deprecated, use completion_tokens)
        duration: API call duration in seconds
        prompt_tokens: Actual token count for prompt (preferred)
        completion_tokens: Actual token count for completion (preferred)
        **kwargs: Additional context (job_id, cv_id, etc.)
    """
    # Local application imports
    from backend.token_utils import estimate_cost

    # Calculate total tokens if both provided
    total_tokens = None
    estimated_cost = None

    if prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = estimate_cost(prompt_tokens, completion_tokens, model)

    log_data = {
        "event_type": "llm_call",
        "operation": operation,
        "model": model,
        "duration_seconds": duration,
    }

    # Add token counts (prefer actual tokens over character lengths)
    if prompt_tokens is not None:
        log_data["prompt_tokens"] = prompt_tokens
    elif prompt_length is not None:
        log_data["prompt_length_chars"] = prompt_length

    if completion_tokens is not None:
        log_data["completion_tokens"] = completion_tokens
    elif response_length is not None:
        log_data["response_length_chars"] = response_length

    if total_tokens is not None:
        log_data["total_tokens"] = total_tokens

    if estimated_cost is not None:
        log_data["estimated_cost_usd"] = round(estimated_cost, 6)

    # Add any additional context
    log_data.update(kwargs)

    logger.info("llm_call", **log_data)


def log_action_execution(
    logger: structlog.BoundLogger,
    action: str,
    session_id: str,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """
    Log action execution with metrics

    Args:
        logger: Structured logger instance
        action: Action type being executed
        session_id: User session ID
        duration_ms: Execution duration in milliseconds
        success: Whether action succeeded
        error: Error message if failed
    """
    logger.info(
        "action_execution",
        action=action,
        session_id=session_id,
        duration_ms=duration_ms,
        success=success,
        error=error,
        event_type="action_execution",
    )
