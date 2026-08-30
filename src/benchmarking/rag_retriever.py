"""RAG retriever - retrieves relevant Q&A from rag_dataset using hybrid search."""

import logging
import os
from dataclasses import dataclass

from src.services.processing.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)


@dataclass
class RAGMatch:
    """Result of RAG retrieval."""

    question: str
    answer: str
    source_id: str
    relevance_score: float
    original_qa_pair: dict[str, str]


class RAGRetriever:
    """Retrieves relevant Q&A pairs from RAG dataset using hybrid search (BM25 + semantic + reranking)."""

    def __init__(self, dataset_path: str = "docs/rag_dataset.jsonl"):
        """Initialize RAG retriever using hybrid search.

        Args:
            dataset_path: Path to RAG dataset JSONL file.
        """
        # Initialize hybrid retriever with environment variables
        llm_base_url = os.getenv("LLM_BASE_URL", "https://litellm.ai.nestle.ru/v1")
        llm_api_key = os.getenv("LLM_PROVIDER_KEY", "")

        self.hybrid_retriever = HybridRetriever(
            dataset_path=dataset_path,
            base_url=llm_base_url,
            api_key=llm_api_key,
            use_reranker=True,
        )

    def retrieve(self, query: str, top_k: int = 3) -> list[RAGMatch]:
        """Retrieve relevant Q&A pairs for a query using hybrid search.

        Args:
            query: User question/query.
            top_k: Number of top results to return.

        Returns:
            List of RAGMatch results ranked by relevance (using rerank score).
        """
        # Get results from hybrid retriever
        hybrid_matches = self.hybrid_retriever.retrieve(query, top_k=top_k)

        # Convert HybridRAGMatch to RAGMatch for backward compatibility
        matches: list[RAGMatch] = []
        for match in hybrid_matches:
            rag_match = RAGMatch(
                question=match.question,
                answer=match.answer,
                source_id=match.source_id,
                relevance_score=match.rerank_score,  # Use rerank score as relevance
                original_qa_pair=match.original_qa_pair,
            )
            matches.append(rag_match)

        return matches
