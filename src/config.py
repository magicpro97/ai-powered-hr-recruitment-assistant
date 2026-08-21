"""Configuration management for HR Assistant application."""

# Standard library imports
import os
from ipaddress import ip_network

# Third-party imports
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # OpenAI Settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Database Settings
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    BACKUP_DIR = os.getenv("BACKUP_DIR", "./backups")

    # File Upload Settings
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE_MB = 10
    ALLOWED_EXTENSIONS = [".pdf", ".txt"]

    # Application Settings
    APP_TITLE = "HR Recruitment Assistant"
    APP_ICON = "🤖"

    # Authentication Settings
    # JWT_SECRET MUST be set in .env - no default for security
    JWT_SECRET = os.getenv("JWT_SECRET") or ""
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
    TRUSTED_PROXY_CIDRS = tuple(
        cidr.strip()
        for cidr in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",")
        if cidr.strip()
    )

    # Development Settings
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    API_URL = os.getenv("API_URL", "http://localhost:8000")

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required. Please set it in .env file.")

        # Set the API key as environment variable for LangChain
        os.environ["OPENAI_API_KEY"] = cls.OPENAI_API_KEY
        return True

    @classmethod
    def validate_auth(cls):
        """Validate authentication configuration."""
        if not cls.JWT_SECRET:
            raise ValueError(
                "JWT_SECRET is required. Generate with: openssl rand -hex 32"
            )
        if len(cls.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        cls.validate_trusted_proxies(cls.TRUSTED_PROXY_CIDRS)
        return True

    @classmethod
    def is_auth_configured(cls) -> bool:
        """Check if JWT_SECRET is properly configured (runtime guard)."""
        return bool(cls.JWT_SECRET) and len(cls.JWT_SECRET) >= 32

    @staticmethod
    def validate_trusted_proxies(cidrs: tuple[str, ...]) -> tuple[str, ...]:
        """Validate every configured trusted-proxy CIDR. Raise loudly on a typo
        rather than silently discarding proxies (fail-dangerous). Returns cidrs.
        """
        for cidr in cidrs:
            try:
                ip_network(cidr)
            except ValueError as e:
                raise ValueError(f"Invalid TRUSTED_PROXY_CIDRS entry {cidr!r}: {e}")
        return cidrs
