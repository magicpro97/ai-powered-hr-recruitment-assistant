"""
ClamAV Scanner Module - Virus scanning for uploaded files.
Integrates with Reefspect (ClamAV REST API) running in Docker.
Supports ARM64/Mac M1/M2.
"""

# Standard library imports
import os
from typing import Optional, Tuple

# Third-party imports
import httpx

# Local application imports
from backend.logging_config import get_logger

logger = get_logger(__name__)

# ========== CONFIGURATION ==========

# Reefspect REST API URL (internal Docker network)
CLAMAV_URL = os.environ.get("CLAMAV_URL", "http://clamav:8000")
CLAMAV_TIMEOUT = 60  # seconds - scanning can take time
MAX_SCAN_SIZE = 50 * 1024 * 1024  # 50MB max file size

# Skip scanning in development if ClamAV is not available
SKIP_SCAN_IN_DEV = os.environ.get("SKIP_CLAMAV_IN_DEV", "false").lower() == "true"
IS_DEVELOPMENT = os.environ.get("DEBUG", "false").lower() == "true"


class ClamAVClient:
    """
    Client for communicating with Reefspect (ClamAV REST API).
    Uses /upload endpoint for file scanning.
    """

    def __init__(self, base_url: str = CLAMAV_URL):
        self.base_url = base_url.rstrip("/")

    def ping(self) -> bool:
        """Check if ClamAV REST API is available."""
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning("ClamAV ping failed", error=str(e))
            return False

    def scan_stream(
        self, data: bytes, filename: str = "upload"
    ) -> Tuple[bool, Optional[str]]:
        """
        Scan data using Reefspect REST API.

        Args:
            data: File content as bytes
            filename: Original filename (for logging)

        Returns:
            (is_clean, virus_name) - True if clean, virus name if infected
        """
        if len(data) > MAX_SCAN_SIZE:
            logger.warning("File too large for scanning", size=len(data))
            return False, "FILE_TOO_LARGE"

        try:
            # POST file to /upload endpoint (multipart/form-data)
            files = {"file": (filename, data)}
            response = httpx.post(
                f"{self.base_url}/upload", files=files, timeout=CLAMAV_TIMEOUT
            )

            if response.status_code != 200:
                logger.error("ClamAV scan failed", status=response.status_code)
                return False, f"SCAN_ERROR_HTTP_{response.status_code}"

            try:
                result = response.json()
            except (ValueError, TypeError) as e:
                logger.error("ClamAV returned non-JSON response", error=str(e))
                return False, "SCAN_ERROR_INVALID_RESPONSE"

            # Reefspect response format:
            # {
            #   "results": [
            #     {
            #       "name": "file.pdf",
            #       "result": "CLEAN" | "VIRUS" | "WHITELISTED",
            #       "signature": "VirusName" or null
            #     }
            #   ]
            # }
            results = result.get("results", [])
            for file_result in results:
                scan_result = file_result.get("result", "UNKNOWN")
                if scan_result == "VIRUS":
                    virus_name = file_result.get("signature", "UNKNOWN_VIRUS")
                    logger.warning(
                        "Virus detected", virus=virus_name, filename=filename
                    )
                    return False, virus_name
                elif scan_result in ("CLEAN", "WHITELISTED"):
                    logger.info("File scan clean", filename=filename)
                    return True, None

            return False, "SCAN_ERROR_INVALID_RESPONSE"

        except httpx.TimeoutException:
            logger.error("ClamAV scan timed out")
            return False, "SCAN_TIMEOUT"
        except httpx.RequestError as e:
            logger.error("ClamAV connection error", error=str(e))
            return False, "CONNECTION_ERROR"
        except Exception as e:
            logger.error("ClamAV unexpected error", error=str(e))
            return False, "SCAN_ERROR"

    def scan_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Scan a file by reading and streaming it.

        Args:
            file_path: Path to file to scan

        Returns:
            (is_clean, virus_name)
        """
        try:
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                data = f.read()
            return self.scan_stream(data, filename)
        except IOError as e:
            logger.error("Failed to read file for scanning", error=str(e))
            return False, f"FILE_READ_ERROR: {e}"


# ========== SINGLETON CLIENT ==========

_client: Optional[ClamAVClient] = None


def get_clamav_client() -> ClamAVClient:
    """Get or create the ClamAV client."""
    global _client
    if _client is None:
        _client = ClamAVClient()
    return _client


# ========== CONVENIENCE FUNCTIONS ==========


def scan_uploaded_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Scan an uploaded file for viruses.

    In development mode with SKIP_CLAMAV_IN_DEV=true, scanning is skipped.

    Args:
        file_path: Path to the uploaded file

    Returns:
        (is_safe, threat_name) - True if safe, threat name if detected
    """
    # Skip in development if configured
    if IS_DEVELOPMENT and SKIP_SCAN_IN_DEV:
        logger.debug("Skipping virus scan in development mode")
        return True, None

    client = get_clamav_client()

    # Check if ClamAV is available
    if not client.ping():
        logger.warning("ClamAV not available, skipping scan")
        # In production, you might want to reject the file instead
        if not IS_DEVELOPMENT:
            return False, "SCANNER_UNAVAILABLE"
        return True, None

    return client.scan_file(file_path)


def scan_file_bytes(
    data: bytes, filename: str = "upload"
) -> Tuple[bool, Optional[str]]:
    """
    Scan file bytes for viruses.

    Args:
        data: File content as bytes
        filename: Original filename

    Returns:
        (is_safe, threat_name)
    """
    if IS_DEVELOPMENT and SKIP_SCAN_IN_DEV:
        logger.debug("Skipping virus scan in development mode")
        return True, None

    client = get_clamav_client()

    if not client.ping():
        logger.warning("ClamAV not available")
        if not IS_DEVELOPMENT:
            return False, "SCANNER_UNAVAILABLE"
        return True, None

    return client.scan_stream(data, filename)


def is_clamav_available() -> bool:
    """Check if ClamAV service is available."""
    if IS_DEVELOPMENT and SKIP_SCAN_IN_DEV:
        return False  # Not needed in dev
    return get_clamav_client().ping()
