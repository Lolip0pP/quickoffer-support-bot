"""FAISS embedding cache - manages vector index for fast similarity search."""

import json
import logging
import pickle
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

logger = logging.getLogger(__name__)


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize a 2D array of row vectors.

    Normalizing before indexing lets us treat the FAISS L2 distance as a
    monotonic function of cosine similarity: for unit vectors,
    ``L2^2 = 2 - 2 * cos``, so ``similarity = 1 - L2^2 / 2 = cos``.

    Args:
        vectors: Array of shape (n, dim).

    Returns:
        L2-normalized array of the same shape (float32).
    """
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class FAISSEmbeddingCache:
    """Manages FAISS index for fast nearest neighbor search of embeddings."""

    def __init__(self, cache_dir: str = "docs/faiss_indexes"):
        """Initialize FAISS cache manager.

        Args:
            cache_dir: Directory to store FAISS indexes.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index: Optional[faiss.IndexFlatL2] = None
        self.metadata: dict = {}

    def _get_index_path(self, dataset_name: str) -> Path:
        """Get path for FAISS index file.

        Args:
            dataset_name: Name of the dataset (e.g., "rag_dataset_train").

        Returns:
            Path to index file.
        """
        return self.cache_dir / f"{dataset_name}.index"

    def _get_metadata_path(self, dataset_name: str) -> Path:
        """Get path for metadata file.

        Args:
            dataset_name: Name of the dataset.

        Returns:
            Path to metadata file.
        """
        return self.cache_dir / f"{dataset_name}.pkl"

    def build_index(
        self, embeddings: list[Optional[np.ndarray]], dataset_name: str
    ) -> None:
        """Build FAISS index from embeddings.

        Args:
            embeddings: List of embedding vectors (numpy arrays).
            dataset_name: Name of the dataset for caching.
        """
        # Filter out None embeddings and keep track of valid indices
        valid_embeddings = []
        valid_indices = []

        for idx, emb in enumerate(embeddings):
            if emb is not None:
                valid_embeddings.append(emb)
                valid_indices.append(idx)

        if not valid_embeddings:
            logger.warning("No valid embeddings to index")
            return

        # Convert to numpy array and L2-normalize so that L2 distance maps
        # directly onto cosine similarity (see ``_l2_normalize`` docstring).
        embeddings_array = _l2_normalize(np.array(valid_embeddings, dtype=np.float32))

        # Create FAISS index (L2 distance - Euclidean, on unit vectors)
        embedding_dim = embeddings_array.shape[1]
        self.index = faiss.IndexFlatL2(embedding_dim)
        self.index.add(embeddings_array)

        # Store metadata. ``normalized`` marks indexes built with the cosine
        # convention; older caches without it are rejected on load so they get
        # rebuilt automatically.
        self.metadata = {
            "total_embeddings": len(embeddings),
            "valid_embeddings": len(valid_embeddings),
            "valid_indices": valid_indices,
            "embedding_dim": embedding_dim,
            "normalized": True,
        }

        logger.info(
            f"Built FAISS index with {len(valid_embeddings)} "
            f"embeddings (dimension: {embedding_dim})"
        )

    def save_index(self, dataset_name: str) -> bool:
        """Save FAISS index to disk.

        Args:
            dataset_name: Name of the dataset.

        Returns:
            True if successful, False otherwise.
        """
        if self.index is None:
            logger.warning("No index to save")
            return False

        try:
            index_path = self._get_index_path(dataset_name)
            faiss.write_index(self.index, str(index_path))

            metadata_path = self._get_metadata_path(dataset_name)
            with open(metadata_path, "wb") as f:
                pickle.dump(self.metadata, f)

            logger.info(f"Saved FAISS index to {index_path}")
            logger.info(f"Saved metadata to {metadata_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving FAISS index: {e}")
            return False

    def load_index(self, dataset_name: str) -> bool:
        """Load FAISS index from disk.

        Args:
            dataset_name: Name of the dataset.

        Returns:
            True if successful, False otherwise.
        """
        try:
            index_path = self._get_index_path(dataset_name)
            metadata_path = self._get_metadata_path(dataset_name)

            if not index_path.exists() or not metadata_path.exists():
                logger.debug(f"Index files not found for {dataset_name}")
                return False

            with open(metadata_path, "rb") as f:
                metadata = pickle.load(f)

            # Reject legacy caches built before cosine normalization was
            # introduced; returning False triggers a rebuild with the correct
            # (normalized) convention.
            if not metadata.get("normalized"):
                logger.warning(
                    f"FAISS cache '{dataset_name}' is un-normalized (legacy); "
                    f"ignoring so it will be rebuilt with cosine normalization"
                )
                return False

            self.index = faiss.read_index(str(index_path))
            self.metadata = metadata

            logger.info(f"Loaded FAISS index from {index_path}")

            logger.info(
                f"Index contains {self.metadata.get('valid_embeddings', 0)} "
                f"valid embeddings"
            )
            return True

        except Exception as e:
            logger.error(f"Error loading FAISS index: {e}")
            return False

    def search(
        self, query_embedding: np.ndarray, top_k: int = 10
    ) -> list[tuple[int, float]]:
        """Search for nearest neighbors in FAISS index.

        Args:
            query_embedding: Query embedding vector.
            top_k: Number of nearest neighbors to return.

        Returns:
            List of (original_index, distance) tuples sorted by distance.
        """
        if self.index is None:
            logger.warning("No index loaded for search")
            return []

        try:
            # Ensure query is float32 and L2-normalized to match the indexed
            # unit vectors, so the returned squared-L2 distance equals
            # ``2 - 2 * cos`` and can be converted back to cosine similarity.
            query = _l2_normalize(np.array([query_embedding], dtype=np.float32))

            # Search in FAISS
            distances, indices = self.index.search(query, top_k)

            # FAISS returns distances and indices for the first (and only) query
            distances = distances[0]
            indices = indices[0]

            # Map back to original document indices
            valid_indices = self.metadata.get("valid_indices", [])
            results = []

            for idx, dist in zip(indices, distances):
                if idx < len(valid_indices):
                    original_idx = valid_indices[idx]
                    results.append((original_idx, float(dist)))

            return results

        except Exception as e:
            logger.error(f"Error searching FAISS index: {e}")
            return []

    def get_index_stats(self) -> dict:
        """Get statistics about the loaded index.

        Returns:
            Dictionary with index statistics.
        """
        if self.index is None:
            return {"status": "no_index_loaded"}

        return {
            "status": "loaded",
            "total_vectors": self.index.ntotal,
            "valid_embeddings": self.metadata.get("valid_embeddings", 0),
            "embedding_dimension": self.metadata.get("embedding_dim", 0),
            "index_type": type(self.index).__name__,
        }
