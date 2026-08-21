"""
Custom Exception Hierarchy for HR Recruitment Assistant
Provides type-safe error handling with structured error responses
"""

# Standard library imports
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Standard error codes for API responses"""

    # Validation Errors (400)
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_SESSION_ID = "INVALID_SESSION_ID"

    # Business Logic Errors (422)
    NO_JOB_DESCRIPTION = "NO_JOB_DESCRIPTION"
    NO_CVS_FOUND = "NO_CVS_FOUND"
    NO_MATCHES_FOUND = "NO_MATCHES_FOUND"
    CANDIDATE_NOT_FOUND = "CANDIDATE_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    CV_NOT_FOUND = "CV_NOT_FOUND"

    # Processing Errors (500)
    LLM_PROCESSING_ERROR = "LLM_PROCESSING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    FILE_PROCESSING_ERROR = "FILE_PROCESSING_ERROR"
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"

    # Security Errors (403)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INVALID_TOKEN = "INVALID_TOKEN"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class HRAssistantException(Exception):
    """Base exception for all HR Assistant errors"""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to API response format"""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(HRAssistantException):
    """Raised when input validation fails"""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INVALID_INPUT,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code=400, details=details)


class BusinessLogicError(HRAssistantException):
    """Raised when business rules are violated"""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code=422, details=details)


class ProcessingError(HRAssistantException):
    """Raised when processing operations fail"""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code=500, details=details)


class SecurityError(HRAssistantException):
    """Raised when security constraints are violated"""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.PERMISSION_DENIED,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code=403, details=details)


class ResourceNotFoundError(HRAssistantException):
    """Raised when a requested resource is not found"""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code=404, details=details)
