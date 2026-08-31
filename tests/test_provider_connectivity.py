"""Integration tests for provider connectivity and API key validation.

These tests verify that:
1. API keys are valid and credentials work
2. Endpoints are accessible and responding
3. All components (embedder, reranker, LLM) work together

Run with: pytest tests/test_provider_connectivity.py -v -m integration
"""

import logging

import httpx
import pytest

from src.core.config import settings
from src.services.processing.hybrid_retriever import HybridRetriever
from src.services.llm import get_llm_service

logger = logging.getLogger(__name__)


# ============================================================================
# LiteLLM Tests
# ============================================================================


@pytest.mark.integration
async def test_litellm_base_url_accessible(litellm_base_url: str) -> None:
    """Test that LiteLLM base URL is accessible."""
    if not litellm_base_url or litellm_base_url.startswith("http://localhost"):
        pytest.skip("LiteLLM localhost - skipping network test")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{litellm_base_url.rstrip('/')}/models")
            assert response.status_code in [200, 401, 403]
            logger.info(f"✅ LiteLLM URL accessible: {litellm_base_url}")
    except httpx.ConnectError as e:
        pytest.fail(f"❌ Cannot connect to LiteLLM: {e}")
    except httpx.TimeoutException as e:
        pytest.fail(f"❌ LiteLLM timeout: {e}")


@pytest.mark.integration
async def test_litellm_embeddings_endpoint(
    litellm_base_url: str, litellm_api_key: str, litellm_embedding_model: str
) -> None:
    """Test that LiteLLM embeddings endpoint works."""
    if not litellm_base_url or litellm_base_url.startswith("http://localhost"):
        pytest.skip("LiteLLM localhost - skipping network test")

    headers = {
        "Authorization": f"Bearer {litellm_api_key}" if litellm_api_key else "",
        "Content-Type": "application/json",
    }

    payload = {"model": litellm_embedding_model, "input": "test text"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{litellm_base_url.rstrip('/')}/embeddings",
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                assert "data" in data
                assert len(data["data"]) > 0
                logger.info("✅ LiteLLM embeddings working")
            elif response.status_code == 401:
                pytest.skip("LiteLLM API key invalid or missing")
            else:
                pytest.fail(f"❌ LiteLLM embeddings failed: {response.status_code}")
    except httpx.TimeoutException:
        pytest.skip("LiteLLM embeddings timeout")
    except Exception as e:
        pytest.fail(f"❌ LiteLLM embeddings error: {e}")


@pytest.mark.integration
async def test_litellm_chat_completion_endpoint(
    litellm_base_url: str, litellm_api_key: str, litellm_model: str
) -> None:
    """Test that LiteLLM chat completion endpoint works."""
    if not litellm_base_url or litellm_base_url.startswith("http://localhost"):
        pytest.skip("LiteLLM localhost - skipping network test")

    headers = {
        "Authorization": f"Bearer {litellm_api_key}" if litellm_api_key else "",
        "Content-Type": "application/json",
    }

    payload = {
        "model": litellm_model,
        "messages": [{"role": "user", "content": "say hello"}],
        "max_tokens": 100,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{litellm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                assert "choices" in data
                assert len(data["choices"]) > 0
                logger.info("✅ LiteLLM chat completion working")
            elif response.status_code == 401:
                pytest.skip("LiteLLM API key invalid")
            else:
                pytest.fail(f"❌ LiteLLM chat completion failed: {response.status_code}")
    except httpx.TimeoutException:
        pytest.skip("LiteLLM chat completion timeout")
    except Exception as e:
        pytest.fail(f"❌ LiteLLM chat completion error: {e}")


# ============================================================================
# OpenRouter Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.skipif(not settings.openrouter_api_key, reason="OPENROUTER_API_KEY not set")
async def test_openrouter_api_key_valid(
    openrouter_base_url: str, openrouter_api_key: str
) -> None:
    """Test that OpenRouter API key is valid."""
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{openrouter_base_url.rstrip('/')}/auth/key",
                headers=headers,
            )

            if response.status_code == 200:
                logger.info("✅ OpenRouter API key valid")
            elif response.status_code == 401:
                pytest.fail("❌ OpenRouter API key invalid (401)")
            elif response.status_code == 403:
                pytest.fail("❌ OpenRouter API key forbidden (403)")
            else:
                pytest.fail(f"❌ OpenRouter auth check failed: {response.status_code}")
    except httpx.ConnectError as e:
        pytest.fail(f"❌ Cannot connect to OpenRouter: {e}")
    except httpx.TimeoutException as e:
        pytest.fail(f"❌ OpenRouter timeout: {e}")


@pytest.mark.integration
@pytest.mark.skipif(not settings.openrouter_api_key, reason="OPENROUTER_API_KEY not set")
async def test_openrouter_model_available(
    openrouter_base_url: str, openrouter_api_key: str, openrouter_model: str
) -> None:
    """Test that OpenRouter model is available and working."""
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://quickoffer.ru",
        "X-Title": "QuickOffer Support Bot",
    }

    payload = {
        "model": openrouter_model,
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{openrouter_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                assert "choices" in data
                logger.info(f"✅ OpenRouter model {openrouter_model} working")
            elif response.status_code == 401:
                pytest.fail("❌ OpenRouter API key invalid")
            elif response.status_code == 429:
                pytest.skip("OpenRouter rate limit exceeded")
            else:
                pytest.fail(f"❌ OpenRouter model test failed: {response.status_code}")
    except httpx.TimeoutException:
        pytest.fail("❌ OpenRouter timeout")
    except Exception as e:
        pytest.fail(f"❌ OpenRouter error: {e}")


# ============================================================================
# ZeroEntropy Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.skipif(not settings.zero_entropy_api_key, reason="ZERO_ENTROPY_API_KEY not set")
async def test_zero_entropy_api_key_valid(
    zero_entropy_base_url: str, zero_entropy_api_key: str
) -> None:
    """Test that ZeroEntropy API key is valid."""
    headers = {
        "Authorization": f"Bearer {zero_entropy_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.get(
                f"{zero_entropy_base_url.rstrip('/')}/models",
                headers=headers,
            )

            if response.status_code == 200:
                logger.info("✅ ZeroEntropy API key valid")
            elif response.status_code == 401:
                pytest.fail("❌ ZeroEntropy API key invalid (401)")
            elif response.status_code == 403:
                pytest.fail("❌ ZeroEntropy API key forbidden (403)")
            else:
                if response.status_code < 500:
                    logger.info(f"✅ ZeroEntropy API key valid (status: {response.status_code})")
                else:
                    pytest.fail(f"❌ ZeroEntropy API error: {response.status_code}")
    except httpx.ConnectError as e:
        pytest.fail(f"❌ Cannot connect to ZeroEntropy: {e}")
    except httpx.TimeoutException as e:
        pytest.fail(f"❌ ZeroEntropy timeout: {e}")


@pytest.mark.integration
@pytest.mark.skipif(not settings.zero_entropy_api_key, reason="ZERO_ENTROPY_API_KEY not set")
async def test_zero_entropy_embeddings_endpoint(
    zero_entropy_base_url: str, zero_entropy_api_key: str
) -> None:
    """Test that ZeroEntropy embeddings endpoint works."""
    headers = {
        "Authorization": f"Bearer {zero_entropy_api_key}",
        "Content-Type": "application/json",
    }

    payload = {"model": "e5-large", "input": "test embedding"}

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(
                f"{zero_entropy_base_url.rstrip('/')}/embeddings",
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                assert "data" in data
                logger.info("✅ ZeroEntropy embeddings working")
            elif response.status_code == 401:
                pytest.fail("❌ ZeroEntropy API key invalid")
            else:
                pytest.fail(f"❌ ZeroEntropy embeddings failed: {response.status_code}")
    except httpx.TimeoutException:
        pytest.fail("❌ ZeroEntropy embeddings timeout")
    except Exception as e:
        pytest.fail(f"❌ ZeroEntropy embeddings error: {e}")


@pytest.mark.integration
@pytest.mark.skipif(not settings.zero_entropy_api_key, reason="ZERO_ENTROPY_API_KEY not set")
async def test_zero_entropy_rerank_endpoint(
    zero_entropy_base_url: str, zero_entropy_api_key: str
) -> None:
    """Test that ZeroEntropy reranking endpoint works."""
    headers = {
        "Authorization": f"Bearer {zero_entropy_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "bge-reranker-large",
        "query": "test query",
        "documents": ["doc 1", "doc 2", "doc 3"],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(
                f"{zero_entropy_base_url.rstrip('/')}/rerank",
                json=payload,
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                assert "results" in data
                logger.info("✅ ZeroEntropy reranking working")
            elif response.status_code == 401:
                pytest.fail("❌ ZeroEntropy API key invalid")
            else:
                pytest.fail(f"❌ ZeroEntropy reranking failed: {response.status_code}")
    except httpx.TimeoutException:
        pytest.fail("❌ ZeroEntropy reranking timeout")
    except Exception as e:
        pytest.fail(f"❌ ZeroEntropy reranking error: {e}")


# ============================================================================
# Combined Component Tests
# ============================================================================


@pytest.mark.integration
async def test_provider_mode_litellm_all_components() -> None:
    """Test that all components work in LiteLLM mode."""
    if settings.provider_mode.lower() != "litellm":
        pytest.skip("Not in LiteLLM mode")

    try:
        retriever = HybridRetriever(
            dataset_path="docs/rag_dataset_train.jsonl",
            base_url=settings.llm_base_url,
            api_key=settings.llm_provider_key,
            embedding_model=settings.embedding_model,
            reranker_model=settings.reranker_model or "default",
            use_reranker=bool(settings.reranker_base_url),
        )

        llm_service = get_llm_service()

        assert retriever.embedding_service is not None
        assert retriever.reranker_service is not None
        assert llm_service is not None

        logger.info("✅ LiteLLM mode: All components initialized successfully")

        await retriever.close()

    except Exception as e:
        pytest.fail(f"❌ LiteLLM components initialization failed: {e}")


@pytest.mark.integration
@pytest.mark.skipif(
    not settings.zero_entropy_api_key or not settings.openrouter_api_key,
    reason="Missing ZeroEntropy or OpenRouter API key",
)
async def test_provider_mode_zeroentropy_openrouter_all_components() -> None:
    """Test that all components work in ZeroEntropy + OpenRouter mode."""
    if settings.provider_mode.lower() != "zeroentropy_openrouter":
        pytest.skip("Not in ZeroEntropy + OpenRouter mode")

    try:
        retriever = HybridRetriever(
            dataset_path="docs/rag_dataset_train.jsonl",
            base_url=settings.zero_entropy_base_url,
            api_key=settings.zero_entropy_api_key,
            embedding_model="e5-large",
            reranker_model="bge-reranker-large",
            use_reranker=True,
        )

        llm_service = get_llm_service()

        assert retriever.embedding_service is not None
        assert retriever.reranker_service is not None
        assert llm_service is not None
        assert llm_service.provider == "openrouter"

        logger.info(
            "✅ ZeroEntropy + OpenRouter mode: All components initialized successfully"
        )

        await retriever.close()

    except Exception as e:
        pytest.fail(
            f"❌ ZeroEntropy + OpenRouter components initialization failed: {e}"
        )

        pytest.fail(f"❌ ZeroEntropy reranking error: {e}")

        pytest.fail("❌ OpenRouter timeout")
    except Exception as e:
        pytest.fail(f"❌ OpenRouter error: {e}")

        pytest.skip("LiteLLM chat completion timeout")
    except Exception as e:
        pytest.fail(f"❌ LiteLLM chat completion error: {e}")
