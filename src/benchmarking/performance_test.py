"""Performance test comparing sync vs async versions."""

import asyncio
import time
import logging
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.benchmarking.hybrid_retriever import HybridRetriever
from src.benchmarking.llm_improver import LLMImprover

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def test_retriever_performance() -> None:
    """Test HybridRetriever async performance."""
    print("\n" + "=" * 80)
    print("PERFORMANCE TEST: HybridRetriever (Async)")
    print("=" * 80)

    # Initialize retriever
    retriever = HybridRetriever(
        dataset_path="docs/rag_dataset.jsonl",
        base_url="https://litellm.ai.nestle.ru/v1",
        api_key="",  # Will use env variable
        use_reranker=True,
    )

    # Test queries
    test_queries = [
        "Как вернуть свои деньги?",
        "Помощь с резюме и карьерой",
        "Как получить промокод?",
    ]

    try:
        print("\nTesting async retriever with multiple queries...")
        print("-" * 80)

        # Concurrent queries
        start_time = time.time()
        tasks = [
            retriever.retrieve(query, top_k=3) for query in test_queries
        ]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        for query, matches in zip(test_queries, results):
            print(f"\nQuery: {query}")
            print(f"  Found {len(matches)} matches")
            if matches:
                print(f"  Top match score: {matches[0].rerank_score:.4f}")

        print(f"\n✓ Processed {len(test_queries)} queries in {elapsed:.2f} seconds")
        print(f"  Average time per query: {elapsed / len(test_queries):.2f} seconds")

    finally:
        await retriever.close()


async def test_concurrent_operations() -> None:
    """Test concurrent operations."""
    print("\n" + "=" * 80)
    print("PERFORMANCE TEST: Concurrent Operations")
    print("=" * 80)

    retriever = HybridRetriever(
        dataset_path="docs/rag_dataset.jsonl",
        base_url="https://litellm.ai.nestle.ru/v1",
        api_key="",
        use_reranker=True,
    )

    queries = [
        "Возврат платежа",
        "Архивирование вакансии",
        "Помощь с поиском работы",
        "Промокод за отзыв",
        "Криптовалюта платеж",
    ] * 2  # Repeat for more data

    try:
        print(f"\nTesting {len(queries)} concurrent retrievals...")
        print("-" * 80)

        # Serial execution (for baseline)
        print("\nSerial execution:")
        start_time = time.time()
        for query in queries[:3]:
            await retriever.retrieve(query, top_k=1)
        serial_elapsed = time.time() - start_time
        print(f"  3 queries: {serial_elapsed:.2f} seconds")

        # Concurrent execution
        print("\nConcurrent execution:")
        start_time = time.time()
        tasks = [retriever.retrieve(query, top_k=1) for query in queries[:3]]
        await asyncio.gather(*tasks)
        concurrent_elapsed = time.time() - start_time
        print(f"  3 queries: {concurrent_elapsed:.2f} seconds")

        speedup = serial_elapsed / concurrent_elapsed if concurrent_elapsed > 0 else 1
        print(f"\n✓ Speedup: {speedup:.1f}x")

    finally:
        await retriever.close()


async def main() -> None:
    """Run all performance tests."""
    print("\n" + "=" * 80)
    print("QUICKOFFER BOT - ASYNC PERFORMANCE TESTS")
    print("=" * 80)

    try:
        await test_retriever_performance()
        await test_concurrent_operations()

        print("\n" + "=" * 80)
        print("✓ All performance tests completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        logger.exception("Performance test error")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
