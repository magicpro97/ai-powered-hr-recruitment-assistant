"""
File Upload Validation Utilities
Provides secure file upload handling with MIME type verification
"""

# Standard library imports
import logging
import uuid
from pathlib import Path
from typing import Optional, Tuple

# Third-party imports
import magic
from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# Allowed MIME types for CV uploads
ALLOWED_CV_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}

# Maximum file sizes (in bytes)
MAX_CV_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


class FileValidationError(Exception):
    """Raised when file validation fails"""

    pass


def validate_file_upload(
    file: UploadFile,
    allowed_mime_types: dict = None,
    max_size: int = MAX_CV_SIZE,
    require_extension: Optional[str] = None,
) -> Tuple[bytes, str]:
    """
    Validate uploaded file with MIME type verification

    Args:
        file: FastAPI UploadFile object
        allowed_mime_types: Dict of allowed MIME types to extensions
        max_size: Maximum file size in bytes
        require_extension: Required file extension (e.g., ".pdf")

    Returns:
        Tuple of (file_content, safe_filename)

    Raises:
        HTTPException: If validation fails
    """
    if allowed_mime_types is None:
        allowed_mime_types = ALLOWED_CV_MIME_TYPES

    # Read file content
    try:
        file_content = file.file.read()
    except Exception as e:
        logger.error("Failed to read file: %s", str(e))
        raise HTTPException(status_code=400, detail="Failed to read file")
    finally:
        try:
            file.file.seek(0)  # Reset file pointer
        except Exception:
            pass  # File descriptor may be closed after read error

    # Check file size
    file_size = len(file_content)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=400, detail=f"File too large (max {max_mb:.1f} MB)"
        )

    # Detect MIME type using python-magic
    try:
        mime_type = magic.from_buffer(file_content, mime=True)
    except Exception as e:
        logger.error("MIME type detection failed: %s", str(e))
        raise HTTPException(status_code=500, detail="File validation failed")

    # Validate MIME type
    if mime_type not in allowed_mime_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type: uploaded file is not an accepted format",
        )

    # Get original filename
    original_filename = file.filename or "unnamed_file"

    # Sanitize filename
    safe_filename = _sanitize_upload_filename(original_filename)

    # Verify extension matches MIME type
    expected_extension = allowed_mime_types[mime_type]
    if not safe_filename.lower().endswith(expected_extension):
        # Force correct extension based on MIME type
        name_without_ext = Path(safe_filename).stem
        safe_filename = f"{name_without_ext}{expected_extension}"

    # If specific extension required, verify it
    if require_extension and not safe_filename.lower().endswith(
        require_extension.lower()
    ):
        raise HTTPException(
            status_code=400,
            detail=f"File must have {require_extension} extension",
        )

    # Generate unique filename to prevent collisions
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"

    return file_content, unique_filename


def _sanitize_upload_filename(filename: str) -> str:
    """
    Sanitize uploaded filename to prevent security issues

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Get basename only (strips directory paths like ../../../etc/passwd)
    filename = Path(filename).name

    # Remove null bytes and other dangerous characters
    filename = filename.replace("\x00", "")

    # Remove path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Only allow safe characters: alphanumeric, dash, underscore, dot
    # Standard library imports
    import re

    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    # Prevent hidden files (starting with .)
    if filename.startswith("."):
        filename = "_" + filename[1:]

    # Prevent files with only extension or empty name
    if filename == "":
        filename = "file"

    # Limit filename length (preserve extension)
    if len(filename) > 255:
        name_part = Path(filename).stem[:240]
        ext_part = Path(filename).suffix[:15]
        filename = name_part + ext_part

    return filename


def validate_cv_file(file: UploadFile) -> Tuple[bytes, str]:
    """
    Validate CV file upload (PDF, DOCX, DOC)

    Args:
        file: FastAPI UploadFile object

    Returns:
        Tuple of (file_content, safe_filename)

    Raises:
        HTTPException: If validation fails
    """
    return validate_file_upload(
        file=file,
        allowed_mime_types=ALLOWED_CV_MIME_TYPES,
        max_size=MAX_CV_SIZE,
    )


async def validate_pdf_file(file: UploadFile) -> Tuple[bytes, str]:
    """
    Validate PDF file upload (strict PDF-only) - async.
    Uses await UploadFile.read() and await seek() to avoid blocking the event loop.
    """
    try:
        file_content = await file.read()
    except Exception as e:
        logger.error("Failed to read file: %s", str(e))
        raise HTTPException(status_code=400, detail="Failed to read file")
    finally:
        try:
            await file.seek(0)
        except Exception:
            pass

    # Check file size
    file_size = len(file_content)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if file_size > MAX_CV_SIZE:
        max_mb = MAX_CV_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=400, detail=f"File too large (max {max_mb:.1f} MB)"
        )

    # Detect MIME type using python-magic
    try:
        mime_type = magic.from_buffer(file_content, mime=True)
    except Exception as e:
        logger.error("MIME type detection failed: %s", str(e))
        raise HTTPException(status_code=500, detail="File validation failed")

    if mime_type not in {"application/pdf": ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type: uploaded file is not an accepted format",
        )

    original_filename = file.filename or "unnamed_file"
    safe_filename = _sanitize_upload_filename(original_filename)

    # Verify extension matches MIME type
    if not safe_filename.lower().endswith(".pdf"):
        name_without_ext = Path(safe_filename).stem
        safe_filename = f"{name_without_ext}.pdf"

    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    return file_content, unique_filename
