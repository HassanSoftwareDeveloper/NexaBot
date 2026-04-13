import logging
import os
import requests
import numpy as np
from typing import List, Union, Optional
from backend.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    API-based embedding service using HuggingFace Inference API.
    No local model loaded — zero RAM overhead from torch/transformers.
    """

    def __init__(self):
        self.api_key = os.getenv("HUGGINGFACE_API_KEY", "")
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        # Updated to new HuggingFace router endpoint (old api-inference.huggingface.co is deprecated)
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}/pipeline/feature-extraction"
        self._embedding_dim = 384  # all-MiniLM-L6-v2 output dim

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def _call_api(self, texts: List[str]) -> np.ndarray:
        """Call HuggingFace Inference API for embeddings."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": texts,
            "options": {"wait_for_model": True}
        }

        response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            # HF returns list of lists
            return np.array(result, dtype=np.float32)
        else:
            raise RuntimeError(f"HuggingFace API error {response.status_code}: {response.text}")

    def encode_texts(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """Encode texts into embeddings via API."""
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.zeros((0, self._embedding_dim), dtype=np.float32)

        all_embeddings = []

        # Process in batches to avoid API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                embeddings = self._call_api(batch)
                all_embeddings.append(embeddings)
            except Exception as e:
                logger.error(f"Embedding API error for batch {i}: {e}")
                # Return zero vectors as fallback
                all_embeddings.append(np.zeros((len(batch), self._embedding_dim), dtype=np.float32))

        result = np.vstack(all_embeddings)

        # Normalize
        norms = np.linalg.norm(result, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return result / norms

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query string."""
        if not query:
            return np.zeros((self._embedding_dim,), dtype=np.float32)
        return self.encode_texts(query)[0]

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        return float(np.dot(embedding1, embedding2))

    def compute_similarities(self, embeddings: np.ndarray, query_embedding: np.ndarray) -> np.ndarray:
        return np.dot(embeddings, query_embedding)

    def get_embedding_dimension(self) -> int:
        return self._embedding_dim


# Global instance — no model loaded at startup
embedding_service = EmbeddingService()
