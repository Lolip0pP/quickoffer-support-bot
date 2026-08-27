"""Hybrid retriever - combines BM25 with semantic search and reranking."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.metrics.pairwise import cosine_similarity

from src.benchmarking.faiss_cache import FAISSEmbeddingCache

logger = logging.getLogger(__name__)


@dataclass
class HybridRAGMatch:
    """Result of hybrid RAG retrieval with reranking."""

    question: str
    answer: str
    source_id: str
    bm25_score: float
    semantic_score: float
    rerank_score: float
    combined_score: float
    original_qa_pair: dict[str, str]


class EmbeddingService:
    """Service for getting embeddings via API."""

    def __init__(
        self,
        base_url: str = "https://litellm.ai.nestle.ru/v1",
        api_key: str = "",
        model: str = "Nestle/qwen-embed-06",
    ):
        """Initialize embedding service.

        Args:
            base_url: Base URL for the embedding API.
            api_key: API key for authentication.
            model: Model name for embeddings.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.embedding_cache: dict[str, np.ndarray] = {}

    def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding for text, using cache when available.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector or None if API call fails.
        """
        # Check cache first
        if text in self.embedding_cache:
            return self.embedding_cache[text]

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {"model": self.model, "input": text}

            with httpx.Client(verify=False) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )

            if response.status_code != 200:
                logger.warning(
                    f"Embedding API returned status {response.status_code}: "
                    f"{response.text}"
                )
                return None

            data = response.json()
            embedding = np.array(data["data"][0]["embedding"])

            # Cache the embedding
            self.embedding_cache[text] = embedding
            return embedding

        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None

    def batch_embeddings(
        self, texts: list[str]
    ) -> dict[str, Optional[np.ndarray]]:
        """Get embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            Dictionary mapping text to embedding or None.
        """
        embeddings = {}
        for text in texts:
            embeddings[text] = self.get_embedding(text)
        return embeddings


class RerankerService:
    """Service for reranking results via API."""

    def __init__(
        self,
        base_url: str = "https://litellm.ai.nestle.ru/v1",
        api_key: str = "",
        model: str = "Nestle/qwen-rerank-06",
    ):
        """Initialize reranker service.

        Args:
            base_url: Base URL for the reranker API.
            api_key: API key for authentication.
            model: Model name for reranking.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def rerank(
        self, query: str, documents: list[str]
    ) -> Optional[list[tuple[int, float]]]:
        """Rerank documents based on query relevance.

        Args:
            query: Query text.
            documents: List of document texts to rerank.

        Returns:
            List of (index, score) tuples sorted by score, or None if API fails.
        """
        if not documents:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "query": query,
                "documents": documents,
            }

            with httpx.Client(verify=False) as client:
                response = client.post(
                    f"{self.base_url}/rerank",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )

            if response.status_code != 200:
                logger.warning(
                    f"Reranker API returned status {response.status_code}: "
                    f"{response.text}"
                )
                return None

            data = response.json()
            results = []

            # API returns list of results with index and score
            for result in data["results"]:
                results.append((result["index"], float(result["relevance_score"])))

            # Sort by score descending
            results.sort(key=lambda x: x[1], reverse=True)
            return results

        except Exception as e:
            logger.error(f"Error reranking documents: {e}")
            return None


class HybridRetriever:
    """Retrieves relevant Q&A pairs using hybrid search (BM25 + semantic) with reranking."""

    def __init__(
        self,
        dataset_path: str = "docs/rag_dataset_train.jsonl",
        base_url: str = "https://litellm.ai.nestle.ru/v1",
        api_key: str = "",
        embedding_model: str = "Nestle/qwen-embed-06",
        reranker_model: str = "Nestle/qwen-rerank-06",
        use_reranker: bool = True,
        use_faiss: bool = True,
    ):
        """Initialize hybrid retriever.

        Args:
            dataset_path: Path to RAG dataset JSONL file.
            base_url: Base URL for embedding/reranker APIs.
            api_key: API key for authentication.
            embedding_model: Model for embeddings.
            reranker_model: Model for reranking.
            use_reranker: Whether to use reranker (requires API access).
            use_faiss: Whether to use FAISS for fast similarity search.
        """
        self.dataset_path = Path(dataset_path)
        self.documents: list[dict[str, str]] = []
        self.corpus: list[list[str]] = []
        self.document_texts: list[str] = []
        self.document_embeddings: list[Optional[np.ndarray]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.query_embedding_cache: dict[str, np.ndarray] = {}

        # Initialize services
        self.embedding_service = EmbeddingService(
            base_url=base_url, api_key=api_key, model=embedding_model
        )
        self.reranker_service = RerankerService(
            base_url=base_url, api_key=api_key, model=reranker_model
        )
        self.use_reranker = use_reranker
        self.use_faiss = use_faiss

        # Initialize FAISS cache
        self.faiss_cache = FAISSEmbeddingCache()

        self._load_dataset()

    def _load_dataset(self) -> None:
        """Load RAG dataset and compute embeddings for all documents."""
        if not self.dataset_path.exists():
            logger.error(f"Dataset not found at {self.dataset_path}")
            return

        logger.info(f"Loading RAG dataset from {self.dataset_path}")
        loaded_count = 0

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        qa = json.loads(line)

                        # Each line is a direct QA pair from split_dataset.py
                        if "question" in qa and "answer" in qa:
                            doc = {
                                "id": f"qa_{loaded_count}",
                                "question": qa["question"],
                                "answer": qa["answer"],
                            }
                            self.documents.append(doc)
                            self.document_texts.append(qa["question"])

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

                # Pre-compute embeddings for all documents
                logger.info("Computing embeddings for all documents...")
                self._precompute_embeddings()
            else:
                logger.warning("No Q&A pairs found in dataset")

        except Exception as e:
            logger.error(f"Error loading RAG dataset: {e}")

    def _precompute_embeddings(self) -> None:
        """Pre-compute and cache embeddings for all documents."""
        # Extract dataset name from path for FAISS caching
        dataset_name = self.dataset_path.stem

        if self.use_faiss:
            # Try to load from FAISS cache first
            if self.faiss_cache.load_index(dataset_name):
                logger.info("Loaded embeddings from FAISS cache")
                stats = self.faiss_cache.get_index_stats()
                logger.info(f"FAISS index stats: {stats}")
                return

        # If not using FAISS or cache doesn't exist, compute embeddings
        for text in self.document_texts:
            embedding = self.embedding_service.get_embedding(text)
            self.document_embeddings.append(embedding)

        # Count successful embeddings
        successful = sum(1 for e in self.document_embeddings if e is not None)
        logger.info(f"Successfully computed {successful}/{len(self.document_texts)} embeddings")

        # Save to FAISS cache if enabled
        if self.use_faiss and successful > 0:
            self.faiss_cache.build_index(self.document_embeddings, dataset_name)
            if self.faiss_cache.save_index(dataset_name):
                logger.info("Saved embeddings to FAISS cache for future use")

    def _get_query_embedding(self, query: str) -> Optional[np.ndarray]:
        """Get embedding for query with caching.

        Args:
            query: Query text.

        Returns:
            Embedding vector or None.
        """
        if query in self.query_embedding_cache:
            return self.query_embedding_cache[query]

        embedding = self.embedding_service.get_embedding(query)
        if embedding is not None:
            self.query_embedding_cache[query] = embedding
        return embedding

    def _compute_semantic_scores(
        self, query_embedding: np.ndarray, top_k: int = 10
    ) -> dict[int, float]:
        """Compute semantic similarity scores using cosine similarity.

        Args:
            query_embedding: Query embedding vector.
            top_k: Number of top results to consider.

        Returns:
            Dictionary mapping document index to semantic score.
        """
        scores = {}

        for idx, doc_embedding in enumerate(self.document_embeddings):
            if doc_embedding is None:
                scores[idx] = 0.0
                continue

            # Compute cosine similarity
            similarity = cosine_similarity(
                query_embedding.reshape(1, -1), doc_embedding.reshape(1, -1)
            )[0][0]

            # Normalize to 0-1 range (cosine similarity is already in -1 to 1)
            normalized_similarity = (similarity + 1) / 2
            scores[idx] = float(normalized_similarity)

        return scores

    def _compute_semantic_scores_faiss(
        self, query_embedding: np.ndarray, top_k: int = 10
    ) -> dict[int, float]:
        """Compute semantic similarity scores using FAISS for fast search.

        Args:
            query_embedding: Query embedding vector.
            top_k: Number of top results to consider.

        Returns:
            Dictionary mapping document index to semantic score (0-1 normalized).
        """
        scores = {}

        # Try FAISS search if available
        if self.use_faiss and self.faiss_cache.index is not None:
            try:
                faiss_results = self.faiss_cache.search(query_embedding, top_k)
                for doc_idx, distance in faiss_results:
                    # Convert L2 distance to similarity score (0-1)
                    # L2 distance range: 0-2 for normalized vectors, normalize to 0-1
                    similarity_score = max(0.0, 1.0 - (distance / 2.0))
                    scores[doc_idx] = float(similarity_score)
                return scores
            except Exception as e:
                logger.warning(f"FAISS search failed: {e}, falling back to full scan")

        # Fallback: manual cosine similarity on all documents
        for idx, doc_embedding in enumerate(self.document_embeddings):
            if doc_embedding is None:
                scores[idx] = 0.0
                continue

            similarity = cosine_similarity(
                query_embedding.reshape(1, -1), doc_embedding.reshape(1, -1)
            )[0][0]
            normalized_similarity = (similarity + 1) / 2
            scores[idx] = float(normalized_similarity)

        return scores

    def retrieve(self, query: str, top_k: int = 3) -> list[HybridRAGMatch]:
        """Retrieve relevant Q&A pairs using hybrid search.

        Args:
            query: User question/query.
            top_k: Number of top results to return.

        Returns:
            List of HybridRAGMatch results ranked by combined score.
        """
        if not self.bm25 or not self.documents:
            logger.warning("RAG retriever not initialized or empty dataset")
            return []

        # STEP 1: BM25 retrieval
        query_tokens = query.lower().split()
        bm25_scores = self.bm25.get_scores(query_tokens)

        # Get top-k from BM25 (fast filtering)
        top_indices = sorted(
            range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
        )[:top_k * 3]  # Get more results for semantic re-scoring

        # STEP 2: Semantic scoring
        query_embedding = self._get_query_embedding(query)
        semantic_scores: dict[int, float] = {}

        if query_embedding is not None:
            # Use FAISS-backed semantic scoring. When embeddings are loaded
            # from the FAISS cache, ``self.document_embeddings`` is empty, so
            # the plain full-scan path would silently return zeros. The FAISS
            # path queries the persisted index directly.
            semantic_scores = self._compute_semantic_scores_faiss(
                query_embedding, top_k=len(top_indices)
            )
        else:
            logger.warning("Failed to get query embedding, using BM25 only")
            semantic_scores = {i: 0.0 for i in top_indices}


        # STEP 3: Combine scores (BM25 30% + Semantic 70%)
        combined_scores: dict[int, float] = {}
        for idx in top_indices:
            bm25_norm = min(bm25_scores[idx] / 10.0, 1.0)  # Normalize BM25
            semantic_norm = semantic_scores.get(idx, 0.0)
            combined = 0.3 * bm25_norm + 0.7 * semantic_norm
            combined_scores[idx] = combined

        # Sort by combined score
        sorted_indices = sorted(
            combined_scores.keys(),
            key=lambda i: combined_scores[i],
            reverse=True,
        )[:top_k]

        # STEP 4: Rerank if available
        rerank_scores: dict[int, float] = {}
        if self.use_reranker:
            candidate_docs = [
                self.documents[idx]["question"] for idx in sorted_indices
            ]
            rerank_result = self.reranker_service.rerank(query, candidate_docs)

            if rerank_result:
                # Map rerank indices back to document indices
                for rank_idx, score in rerank_result:
                    if rank_idx < len(sorted_indices):
                        doc_idx = sorted_indices[rank_idx]
                        rerank_scores[doc_idx] = score
                logger.debug(f"Reranking successful for top {len(rerank_scores)} docs")
            else:
                logger.warning("Reranker returned no results, using combined scores")
                for idx in sorted_indices:
                    rerank_scores[idx] = combined_scores[idx]
        else:
            # Use combined score as rerank score if reranker disabled
            for idx in sorted_indices:
                rerank_scores[idx] = combined_scores[idx]

        # STEP 5: Build results
        matches: list[HybridRAGMatch] = []
        final_sorted = sorted(
            sorted_indices, key=lambda i: rerank_scores[i], reverse=True
        )

        for idx in final_sorted:
            if idx < len(self.documents):
                doc = self.documents[idx]
                match = HybridRAGMatch(
                    question=doc["question"],
                    answer=doc["answer"],
                    source_id=doc["id"],
                    bm25_score=round(float(bm25_scores[idx]), 4),
                    semantic_score=round(float(semantic_scores.get(idx, 0.0)), 4),
                    rerank_score=round(float(rerank_scores[idx]), 4),
                    combined_score=round(float(combined_scores[idx]), 4),
                    original_qa_pair={
                        "question": doc["question"],
                        "answer": doc["answer"],
                    },
                )
                matches.append(match)

        if matches:
            logger.info(
                f"Hybrid RAG retrieval: found {len(matches)} relevant Q&A pairs "
                f"(top rerank score: {matches[0].rerank_score})"
            )
        else:
            logger.info("Hybrid RAG retrieval: no relevant Q&A pairs found for query")

        return matches
