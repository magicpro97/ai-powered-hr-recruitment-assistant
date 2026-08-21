"""
Token Counting Utilities for LLM Logging
Uses tiktoken library for accurate token counting
"""

# Third-party imports
import tiktoken

# Cache for encoding objects
_ENCODING_CACHE = {}


def get_encoding_for_model(model_name: str) -> tiktoken.Encoding:
    """
    Get tiktoken encoding for a specific model

    Args:
        model_name: OpenAI model name (e.g., "gpt-4", "gpt-3.5-turbo")

    Returns:
        tiktoken.Encoding object
    """
    if model_name not in _ENCODING_CACHE:
        try:
            # Try to get encoding for specific model
            _ENCODING_CACHE[model_name] = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base (used by GPT-4 and GPT-3.5-turbo)
            _ENCODING_CACHE[model_name] = tiktoken.get_encoding("cl100k_base")

    return _ENCODING_CACHE[model_name]


def count_tokens(text: str, model_name: str = "gpt-4") -> int:
    """
    Count tokens in text for a specific model

    Args:
        text: Text to count tokens for
        model_name: OpenAI model name

    Returns:
        Number of tokens
    """
    if not text:
        return 0

    encoding = get_encoding_for_model(model_name)
    return len(encoding.encode(text))


def count_tokens_for_messages(messages: list, model_name: str = "gpt-4") -> int:
    """
    Count tokens for a list of messages (ChatGPT format)

    Args:
        messages: List of message dicts with 'role' and 'content'
        model_name: OpenAI model name

    Returns:
        Total number of tokens

    Note:
        This accounts for message formatting overhead
    """
    encoding = get_encoding_for_model(model_name)

    # Token counting logic based on OpenAI's cookbook
    # https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb

    tokens_per_message = (
        3  # Every message follows <im_start>{role/name}\n{content}<im_end>\n
    )
    tokens_per_name = 1  # If there's a name, the role is omitted

    num_tokens = 0

    for message in messages:
        num_tokens += tokens_per_message

        for key, value in message.items():
            if value:
                num_tokens += len(encoding.encode(str(value)))
                if key == "name":
                    num_tokens += tokens_per_name

    num_tokens += 2  # Every reply is primed with <im_start>assistant

    return num_tokens


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_name: str = "gpt-4",
) -> float:
    """
    Estimate API cost for a completion

    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        model_name: OpenAI model name

    Returns:
        Estimated cost in USD

    Note:
        Prices as of January 2026 (update periodically)
    """
    # Pricing per 1K tokens (as of Jan 2026)
    PRICING = {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-4o": {"prompt": 0.005, "completion": 0.015},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    }

    # Default to gpt-4 pricing if model not found
    pricing = PRICING.get(model_name, PRICING["gpt-4"])

    prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1000) * pricing["completion"]

    return prompt_cost + completion_cost


def truncate_to_token_limit(
    text: str,
    max_tokens: int,
    model_name: str = "gpt-4",
    suffix: str = "...",
) -> str:
    """
    Truncate text to fit within token limit

    Args:
        text: Text to truncate
        max_tokens: Maximum number of tokens
        model_name: OpenAI model name
        suffix: String to append to truncated text

    Returns:
        Truncated text
    """
    if not text:
        return ""

    encoding = get_encoding_for_model(model_name)
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return text

    # Account for suffix tokens
    suffix_tokens = len(encoding.encode(suffix))
    truncate_at = max_tokens - suffix_tokens

    if truncate_at < 0:
        truncate_at = 0

    truncated_tokens = tokens[:truncate_at]
    truncated_text = encoding.decode(truncated_tokens)

    return truncated_text + suffix


# Convenience functions for common models


def count_tokens_gpt4(text: str) -> int:
    """Count tokens for GPT-4"""
    return count_tokens(text, "gpt-4")


def count_tokens_gpt4o_mini(text: str) -> int:
    """Count tokens for GPT-4o-mini"""
    return count_tokens(text, "gpt-4o-mini")


def count_tokens_gpt35(text: str) -> int:
    """Count tokens for GPT-3.5-turbo"""
    return count_tokens(text, "gpt-3.5-turbo")
