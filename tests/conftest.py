"""Minimal async test runner to keep the test suite dependency-light."""

import asyncio
import inspect

import pytest

from src.core.config import settings


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: run a coroutine test with asyncio.run")
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires real API credentials)",
    )


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Run coroutine tests without requiring pytest-asyncio at runtime."""
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None
    arguments = {
        name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames
    }
    asyncio.run(pyfuncitem.obj(**arguments))
    return True


@pytest.fixture
def settings_fixture():
    """Provide access to application settings."""
    return settings


@pytest.fixture
def litellm_base_url():
    """LiteLLM API base URL from settings."""
    return settings.llm_base_url


@pytest.fixture
def litellm_api_key():
    """LiteLLM API key from settings."""
    return settings.llm_provider_key


@pytest.fixture
def litellm_model():
    """LiteLLM model name from settings."""
    return settings.llm_model


@pytest.fixture
def litellm_embedding_model():
    """LiteLLM embedding model from settings."""
    return settings.embedding_model


@pytest.fixture
def openrouter_api_key():
    """OpenRouter API key from settings."""
    return settings.openrouter_api_key


@pytest.fixture
def openrouter_base_url():
    """OpenRouter base URL from settings."""
    return settings.openrouter_base_url


@pytest.fixture
def openrouter_model():
    """OpenRouter model name from settings."""
    return settings.openrouter_model


@pytest.fixture
def zero_entropy_api_key():
    """ZeroEntropy API key from settings."""
    return settings.zero_entropy_api_key


@pytest.fixture
def zero_entropy_base_url():
    """ZeroEntropy base URL from settings."""
    return settings.zero_entropy_base_url


@pytest.fixture
def provider_mode():
    """Current provider mode from settings."""
    return settings.provider_mode
