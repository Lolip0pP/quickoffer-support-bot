"""RAG retriever - retrieves relevant Q&A from rag_dataset using BM25."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

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
    """Retrieves relevant Q&A pairs from RAG dataset using BM25."""

    def __init__(self, dataset_path: str = "docs/rag_dataset.jsonl"):
        """Initialize RAG retriever.

        Args:
            dataset_path: Path to RAG dataset JSONL file.
        """
        self.dataset_path = Path(dataset_path)
        self.documents: list[dict[str, str]] = []
        self.corpus: list[list[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self._load_dataset()

    def _load_dataset(self) -> None:
        """Load RAG dataset from JSONL file."""
        if not self.dataset_path.exists():
            logger.error(f"Dataset not found at {self.dataset_path}")
            return

        logger.info(f"Loading RAG dataset from {self.dataset_path}")
        loaded_count = 0

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        record = json.loads(line)
                        qa_pairs = record.get("qa_pairs", [])

                        for qa_idx, qa in enumerate(qa_pairs):
                            if "question" in qa and "answer" in qa:
                                doc = {
                                    "id": f"{record['id']}_{qa_idx}",
                                    "question": qa["question"],
                                    "answer": qa["answer"],
                                    "original_record": record["id"],
                                }
                                self.documents.append(doc)

                                # Tokenize for BM25
                                tokens = qa["question"].lower().split()
                                self.corpus.append(tokens)
                                loaded_count += 1

                                if loaded_count % 100 == 0:
                                    logger.debug(
                                        f"Loaded {loaded_count} Q&A pairs..."
                                    )

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse JSON at line {line_num}: {e}"
                        )
                        continue

            # Initialize BM25
            if self.corpus:
                self.bm25 = BM25Okapi(self.corpus)
                logger.info(
                    f"RAG dataset loaded: {loaded_count} Q&A pairs indexed"
                )
            else:
                logger.warning("No Q&A pairs found in dataset")

        except Exception as e:
            logger.error(f"Error loading RAG dataset: {e}")

    def retrieve(self, query: str, top_k: int = 3) -> list[RAGMatch]:
        """Retrieve relevant Q&A pairs for a query.

        Args:
            query: User question/query.
            top_k: Number of top results to return.

        Returns:
            List of RAGMatch results ranked by relevance.
        """
        if not self.bm25 or not self.documents:
            logger.warning("RAG retriever not initialized or empty dataset")
            return []

        # Tokenize query
        query_tokens = query.lower().split()

        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)

        # Get top-k indices
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]

        matches: list[RAGMatch] = []

        for idx in top_indices:
            if idx < len(self.documents) and scores[idx] > 0:
                doc = self.documents[idx]
                match = RAGMatch(
                    question=doc["question"],
                    answer=doc["answer"],
                    source_id=doc["id"],
                    relevance_score=round(float(scores[idx]), 4),
                    original_qa_pair={
                        "question": doc["question"],
                        "answer": doc["answer"],
                    },
                )
                matches.append(match)

        if matches:
            logger.info(
                f"RAG retrieval: found {len(matches)} relevant Q&A pairs "
                f"(top score: {matches[0].relevance_score})"
            )
        else:
            logger.info(f"RAG retrieval: no relevant Q&A pairs found for query")

        return matches
