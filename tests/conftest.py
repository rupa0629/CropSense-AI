"""Test environment isolation.

Keep the test client independent from production-oriented values in the local
.env file. Settings are loaded while test modules are imported, so these
overrides must be applied from conftest before collection begins.
"""

import os
from pathlib import Path

import pytest


os.environ["ENVIRONMENT"] = "testing"
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"
os.environ["FORCE_HTTPS"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///tests/test_cropsense.db"
os.environ["REDIS_USE_RATE_LIMITING"] = "false"

TEST_DB = Path(__file__).parent / "test_cropsense.db"


@pytest.fixture(autouse=True)
def isolate_application_state():
    TEST_DB.unlink(missing_ok=True)
    yield
    try:
        from api_server import app

        app.dependency_overrides.clear()
    except ImportError:
        pass
    TEST_DB.unlink(missing_ok=True)


def pytest_sessionfinish(session, exitstatus):
    TEST_DB.unlink(missing_ok=True)
