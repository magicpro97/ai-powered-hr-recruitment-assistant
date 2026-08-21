"""File handling utilities for CV processing."""

# Standard library imports
import os
import tempfile

# Third-party imports
from pypdf import PdfReader

# Denial-of-service guard: maximum PDF pages to extract
MAX_PDF_PAGES = 100


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text as a string

    Raises:
        ValueError: If extraction fails or page count exceeds MAX_PDF_PAGES.
    """
    try:
        reader = PdfReader(file_path)
        # Get page count from document catalog - avoids flattening the full
        # page tree via reader.pages (which would trigger get_num_pages()
        # -> _flatten() on the entire tree).
        try:
            pages_obj = reader.root_object["/Pages"].get_object()
            page_count = int(pages_obj["/Count"])
        except (AttributeError, KeyError, TypeError, ValueError):
            raise ValueError("Malformed PDF: unable to determine page count")

        if page_count > MAX_PDF_PAGES:
            raise ValueError(
                f"PDF has {page_count} pages, max allowed is {MAX_PDF_PAGES}"
            )

        text = ""
        for i, page in enumerate(reader.pages):
            if i >= MAX_PDF_PAGES:
                raise ValueError(
                    f"PDF has more than {MAX_PDF_PAGES} pages, extraction rejected"
                )
            text += page.extract_text() + "\n"
        return text.strip()
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Error extracting text from PDF: {str(e)}")


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate if file has an allowed extension.

    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.txt'])

    Returns:
        True if valid, False otherwise
    """
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed_extensions


def _extract_filename(uploaded_file) -> str:
    """Determine the filename from different upload backends."""
    for attr in ("name", "filename"):
        value = getattr(uploaded_file, attr, None)
        if value:
            return value
    raise ValueError("Uploaded file does not contain a filename")


def _read_file_bytes(uploaded_file) -> bytes:
    """Read file bytes supporting both Streamlit and FastAPI upload objects."""
    if hasattr(uploaded_file, "getbuffer"):
        # Streamlit UploadedFile provides getbuffer()
        return uploaded_file.getbuffer()
    if hasattr(uploaded_file, "file"):
        uploaded_file.file.seek(0)
        return uploaded_file.file.read()
    if hasattr(uploaded_file, "read"):
        uploaded_file.seek(0)
        return uploaded_file.read()
    raise ValueError("Unsupported uploaded file type; cannot read content")


def save_uploaded_file(uploaded_file, upload_dir: str, storage_key: str = None) -> str:
    """
    Save an uploaded file to the specified directory.

    When *storage_key* is provided the file is written as ``{storage_key}.pdf``
    regardless of the original client filename.  The key is validated to
    prevent path traversal (must be a plain basename) and the original upload
    filename must end with ``.pdf`` (defense-in-depth).

    Args:
        uploaded_file: Streamlit UploadedFile or FastAPI UploadFile object
        upload_dir: Directory to save the file
        storage_key: Server-controlled identifier (e.g. a cv_id uuid). When
            set, the file is saved as ``{storage_key}.pdf``.

    Returns:
        Path to the saved file
    """
    os.makedirs(upload_dir, exist_ok=True)

    if storage_key is not None:
        # Validate storage_key: reject path separators and null bytes only
        # Standard library imports
        import re

        if "/" in storage_key or "\\" in storage_key or "\0" in storage_key:
            raise ValueError("Invalid storage key")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", storage_key):
            raise ValueError("Invalid storage key")
        # Defense-in-depth: original upload filename must be .pdf
        original_name = _extract_filename(uploaded_file)
        if not original_name.lower().endswith(".pdf"):
            raise ValueError("original filename must end with .pdf")
        file_path = os.path.join(upload_dir, f"{storage_key}.pdf")
    else:
        filename = _extract_filename(uploaded_file)
        file_path = os.path.join(upload_dir, filename)

    data = _read_file_bytes(uploaded_file)
    # Atomic write: write to temp file then rename to prevent partial reads
    fd, tmp_path = tempfile.mkstemp(dir=upload_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, file_path)  # Atomic on POSIX
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return file_path
