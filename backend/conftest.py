import pytest
from app.config import settings

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring network access and real API keys"
    )

def pytest_runtest_setup(item):
    for marker in item.iter_markers(name="integration"):
        # Check if GROQ_API_KEY is not set or is a placeholder
        if not settings.GROQ_API_KEY or "xxxx" in settings.GROQ_API_KEY:
            pytest.skip("Integration tests skipped: GROQ_API_KEY not set or is a placeholder")
