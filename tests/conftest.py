"""
Pytest configuration and fixtures for HR Assistant tests.
"""

# Standard library imports
import os
import shutil
import sys
import tempfile
import types

# Third-party imports
import pytest

_TEST_ROOT = tempfile.mkdtemp(prefix="hr-assistant-tests-")
os.environ.update(
    {
        "CHROMA_PERSIST_DIR": os.path.join(_TEST_ROOT, "chroma"),
        "UPLOAD_DIR": os.path.join(_TEST_ROOT, "uploads"),
        "JWT_SECRET": "test-jwt-secret-must-be-at-least-32-characters",
        "OPENAI_API_KEY": "test-openai-api-key",
    }
)
os.makedirs(os.environ["CHROMA_PERSIST_DIR"])
os.makedirs(os.environ["UPLOAD_DIR"])


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


@pytest.fixture
def stub_psycopg(monkeypatch):
    """Stub absent DB drivers without leaking fake modules to other tests."""
    if "psycopg" not in sys.modules:
        psycopg = types.ModuleType("psycopg")
        psycopg_rows = types.ModuleType("psycopg.rows")
        psycopg_rows.dict_row = object()
        psycopg.rows = psycopg_rows
        monkeypatch.setitem(sys.modules, "psycopg", psycopg)
        monkeypatch.setitem(sys.modules, "psycopg.rows", psycopg_rows)
    if "psycopg_pool" not in sys.modules:
        psycopg_pool = types.ModuleType("psycopg_pool")
        psycopg_pool.ConnectionPool = object
        monkeypatch.setitem(sys.modules, "psycopg_pool", psycopg_pool)
    yield


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: marks unit tests")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "slow: marks slow tests")
    config.addinivalue_line(
        "markers", "e2e: marks end-to-end tests (require running backend)"
    )
    config.addinivalue_line("markers", "requires_db: marks tests requiring PostgreSQL")
    config.addinivalue_line("markers", "security: marks security tests")


def pytest_collection_modifyitems(config, items):
    """
    Auto-skip e2e tests unless explicitly requested with -m e2e.
    This allows running unit tests by default without needing a running backend.
    """
    # Check if e2e marker was explicitly requested
    markexpr = config.getoption("-m", default="")
    if "e2e" in markexpr:
        # E2E tests are explicitly requested, don't skip them
        return

    skip_e2e = pytest.mark.skip(
        reason="E2E tests require -m e2e flag and running backend"
    )
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)
