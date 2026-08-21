"""
Unit Tests for File Validation Module
Tests MIME type validation, path traversal prevention, and file security
"""

# Standard library imports
import io

# Third-party imports
import pytest
from fastapi import HTTPException, UploadFile

# Local application imports
from backend.file_validation import (
    ALLOWED_CV_MIME_TYPES,
    MAX_CV_SIZE,
    _sanitize_upload_filename,
    validate_cv_file,
    validate_file_upload,
    validate_pdf_file,
)


class TestSanitizeFilename:
    """Test filename sanitization and path traversal prevention."""

    def test_removes_path_traversal(self):
        """Verify path traversal attempts are blocked."""
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config",
            "/etc/passwd",
            "C:\\Windows\\System32\\config",
        ]

        for name in malicious_names:
            result = _sanitize_upload_filename(name)
            # Result should be safe: no path separators, only basename
            assert not result.startswith("/")
            assert not result.startswith("\\")
            assert "/../" not in result
            assert "\\..\\" not in result
            # Should only contain safe characters (alphanumeric, dots, underscores, dashes)
            # Standard library imports
            import re

            assert re.match(r"^[a-zA-Z0-9._-]+$", result), f"Unsafe filename: {result}"

    def test_preserves_safe_filename(self):
        """Verify safe filenames are preserved."""
        safe_name = "resume_john_doe.pdf"
        result = _sanitize_upload_filename(safe_name)
        assert result == safe_name

    def test_removes_dangerous_characters(self):
        """Verify dangerous characters are removed."""
        dangerous = 'file<>:"|?*.pdf'
        result = _sanitize_upload_filename(dangerous)
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_handles_unicode_filenames(self):
        """Verify Unicode characters are handled correctly."""
        unicode_name = "résumé_年度报告.pdf"
        result = _sanitize_upload_filename(unicode_name)
        # Should preserve or safely encode Unicode
        assert result is not None
        assert len(result) > 0


class TestValidateFileUpload:
    """Test generic file upload validation with MIME detection."""

    def test_validates_pdf_mime_type(self):
        """Verify PDF files pass MIME validation."""
        # Create a minimal PDF file
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        file = UploadFile(filename="test.pdf", file=io.BytesIO(pdf_content))

        content, safe_name = validate_file_upload(
            file, allowed_mime_types=ALLOWED_CV_MIME_TYPES
        )

        assert content == pdf_content
        assert safe_name.endswith(".pdf")

    def test_rejects_wrong_mime_type(self):
        """Verify files with wrong MIME type are rejected."""
        # Text file masquerading as PDF
        fake_pdf_content = b"This is not a PDF file"
        file = UploadFile(filename="malware.pdf", file=io.BytesIO(fake_pdf_content))

        with pytest.raises(HTTPException):
            validate_file_upload(file, allowed_mime_types=ALLOWED_CV_MIME_TYPES)

    def test_enforces_file_size_limit(self):
        """Verify file size limits are enforced."""
        # Create file larger than limit
        large_content = b"X" * (MAX_CV_SIZE + 1000)
        file = UploadFile(filename="huge.pdf", file=io.BytesIO(large_content))

        with pytest.raises(HTTPException):
            validate_file_upload(file, max_size=MAX_CV_SIZE)

    def test_handles_empty_file(self):
        """Verify empty files are rejected."""
        empty_file = UploadFile(filename="empty.pdf", file=io.BytesIO(b""))

        with pytest.raises(HTTPException):
            validate_file_upload(empty_file)

    def test_sanitizes_filename(self):
        """Verify filenames are sanitized during validation."""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        file = UploadFile(
            filename="../../../etc/passwd.pdf", file=io.BytesIO(pdf_content)
        )

        content, safe_name = validate_file_upload(
            file, allowed_mime_types=ALLOWED_CV_MIME_TYPES
        )

        assert ".." not in safe_name
        assert "/" not in safe_name


class TestValidatePdfFile:
    """Test PDF-specific file validation."""

    async def test_accepts_valid_pdf(self):
        """Verify valid PDF files are accepted."""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        file = UploadFile(filename="document.pdf", file=io.BytesIO(pdf_content))

        content, safe_name = await validate_pdf_file(file)

        assert content == pdf_content
        assert safe_name.endswith(".pdf")

    async def test_rejects_non_pdf_extension(self):
        """Verify files with PDF MIME are accepted and extension corrected."""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        file = UploadFile(
            filename="document.txt", file=io.BytesIO(pdf_content)  # Wrong extension
        )

        # Should succeed and correct extension to .pdf
        content, safe_name = await validate_pdf_file(file)
        assert content == pdf_content
        assert safe_name.endswith(".pdf")

    async def test_rejects_executable_as_pdf(self):
        """Verify executable files cannot be uploaded as PDFs."""
        # Windows PE header (executable)
        exe_content = b"MZ\x90\x00" + b"X" * 100
        file = UploadFile(filename="malware.pdf", file=io.BytesIO(exe_content))

        with pytest.raises(HTTPException):
            await validate_pdf_file(file)


class TestValidateCvFile:
    """Test CV file validation (PDF, DOCX, DOC)."""

    def test_accepts_pdf_cv(self):
        """Verify PDF CVs are accepted."""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        file = UploadFile(filename="resume.pdf", file=io.BytesIO(pdf_content))

        content, safe_name = validate_cv_file(file)
        assert content == pdf_content

    def test_rejects_image_as_cv(self):
        """Verify image files cannot be uploaded as CVs."""
        # PNG header
        png_content = b"\x89PNG\r\n\x1a\n" + b"X" * 100
        file = UploadFile(
            filename="resume.pdf", file=io.BytesIO(png_content)  # Lying about extension
        )

        with pytest.raises(HTTPException):
            validate_cv_file(file)

    def test_respects_cv_size_limit(self):
        """Verify CV size limits are enforced."""
        large_cv = b"%PDF-1.4\n" + b"X" * (MAX_CV_SIZE + 1000)
        file = UploadFile(filename="huge_resume.pdf", file=io.BytesIO(large_cv))

        with pytest.raises(HTTPException):
            validate_cv_file(file)


class TestMimeTypeConstants:
    """Test MIME type configuration constants."""

    def test_allowed_cv_mime_types_configured(self):
        """Verify CV MIME types are properly configured."""
        assert "application/pdf" in ALLOWED_CV_MIME_TYPES
        assert len(ALLOWED_CV_MIME_TYPES) >= 1

    def test_mime_types_map_to_extensions(self):
        """Verify MIME types map to correct file extensions."""
        assert ALLOWED_CV_MIME_TYPES["application/pdf"] == ".pdf"

    def test_max_cv_size_reasonable(self):
        """Verify CV size limit is reasonable."""
        # Should be at least 1MB, at most 50MB
        assert 1 * 1024 * 1024 <= MAX_CV_SIZE <= 50 * 1024 * 1024


class TestSecurityVulnerabilities:
    """Test protection against known security vulnerabilities."""

    async def test_prevents_mime_spoofing(self):
        """Verify MIME type detection prevents spoofing."""
        # Text file with .pdf extension
        text_content = b"This is plain text, not a PDF"
        file = UploadFile(filename="fake.pdf", file=io.BytesIO(text_content))

        with pytest.raises(HTTPException):
            await validate_pdf_file(file)

    def test_prevents_null_byte_injection(self):
        """Verify null bytes in filenames are handled."""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
        file = UploadFile(
            filename="resume.pdf\x00.exe",  # Null byte injection attempt
            file=io.BytesIO(pdf_content),
        )

        content, safe_name = validate_file_upload(
            file, allowed_mime_types=ALLOWED_CV_MIME_TYPES
        )

        # Sanitized filename should not contain null bytes
        assert "\x00" not in safe_name


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
