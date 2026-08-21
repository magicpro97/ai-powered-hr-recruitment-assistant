"""
Input Sanitization Utilities
Uses bleach library for safe text processing
"""

# Standard library imports
import re

# Third-party imports
import bleach


def sanitize_user_input(
    text: str, max_length: int = 5000, preserve_whitespace: bool = True
) -> str:
    """
    Sanitize user input to prevent injection attacks

    Args:
        text: Raw user input
        max_length: Maximum allowed length (default 5000)
        preserve_whitespace: If True, preserve newlines and formatting (default True)

    Returns:
        Sanitized text safe for processing
    """
    if not text:
        return ""

    # Truncate to max length
    text = text[:max_length]

    # Remove null bytes
    text = text.replace("\x00", "")

    # Clean HTML/script tags (defense in depth)
    text = bleach.clean(text, tags=[], strip=True)

    # Normalize whitespace based on preserve_whitespace flag
    if preserve_whitespace:
        # Only normalize excessive whitespace, keep newlines
        text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces/tabs → single space
        text = re.sub(r"\n{3,}", "\n\n", text)  # Multiple newlines → max 2
    else:
        # Aggressive normalization (old behavior)
        text = " ".join(text.split())

    return text


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal

    Args:
        filename: Raw filename

    Returns:
        Safe filename
    """
    # Standard library imports
    import os

    # Get basename only (removes directory path)
    filename = os.path.basename(filename)

    # Remove any remaining path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Only allow alphanumeric, dash, underscore, dot
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    # Prevent hidden files
    if filename.startswith("."):
        filename = "_" + filename[1:]

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext

    return filename


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format

    Args:
        session_id: Session ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not session_id or len(session_id) < 8 or len(session_id) > 64:
        return False

    # Only allow alphanumeric, hyphens, underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
        return False

    # Prevent path traversal patterns
    if ".." in session_id or "/" in session_id or "\\" in session_id:
        return False

    return True


def validate_uuid(uuid_str: str) -> bool:
    """
    Validate UUID format (UUIDv4)

    Args:
        uuid_str: UUID string to validate

    Returns:
        True if valid UUID, False otherwise
    """
    # Standard library imports
    import uuid

    if not uuid_str:
        return False

    try:
        # Try to parse as UUID
        uuid_obj = uuid.UUID(uuid_str)
        # Verify it's the same string (catches malformed UUIDs)
        return str(uuid_obj) == uuid_str
    except (ValueError, AttributeError):
        return False


def validate_email(email: str) -> bool:
    """
    Validate email format

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    if not email or len(email) > 254:
        return False

    # RFC 5322 compliant email regex (simplified)
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(email_pattern, email))


def sanitize_llm_prompt(prompt: str, max_length: int = 50000) -> str:
    """
    Sanitize LLM prompt to prevent prompt injection

    Args:
        prompt: Raw prompt text
        max_length: Maximum prompt length

    Returns:
        Sanitized prompt
    """
    if not prompt:
        return ""

    # Truncate to reasonable length
    prompt = prompt[:max_length]

    # Remove control characters except newlines/tabs
    prompt = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", prompt)

    # Limit consecutive newlines
    prompt = re.sub(r"\n{4,}", "\n\n\n", prompt)

    # Basic defense against prompt injection attempts
    # Remove common injection patterns
    dangerous_patterns = [
        r"ignore (all )?previous instructions",
        r"disregard (all )?previous (instructions|prompts)",
        r"instead,? (now )?do",
        r"forget (all )?previous",
    ]

    for pattern in dangerous_patterns:
        prompt = re.sub(pattern, "", prompt, flags=re.IGNORECASE)

    return prompt
