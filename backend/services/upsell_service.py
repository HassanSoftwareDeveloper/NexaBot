import logging
from typing import List, Union, Optional

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from backend.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service to generate embeddings using SentenceTransformer"""

    def __init__(self, model_name: Optional[str] = None, normalize: bool = True):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name or settings.embedding_model
        self.normalize = normalize
        self._model = None
        self._embedding_dim = None

    def _load_model(self):
        """Lazy-load the model on first use."""
        if self._model is None:
            logger.info(f"Loading embedding model '{self.model_name}' on {self.device}...")
            try:
                self._model = SentenceTransformer(self.model_name, device=self.device)
                self._embedding_dim = self._model.get_sentence_embedding_dimension()
                logger.info(f"Embedding model loaded. Dimension: {self._embedding_dim}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise RuntimeError(f"Failed to load embedding model: {e}")

    @property
    def model(self):
        self._load_model()
        return self._model

    @property
    def embedding_dim(self):
        self._load_model()
        return self._embedding_dim




    def encode_texts(
        self, texts: Union[str, List[str]], batch_size: int = 32
    ) -> np.ndarray:
        """
        Encode a single string or list of strings into embeddings.

        Args:
            texts: Single string or list of strings.
            batch_size: Batch size for model encoding.

        Returns:
            np.ndarray of shape (n_texts, embedding_dim)
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            logger.warning("No texts provided for embedding.")
            return np.zeros((0, self.embedding_dim), dtype=np.float32)

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 100,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize,
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            raise




    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode a single query string.

        Args:
            query: Text string to encode.

        Returns:
            np.ndarray embedding vector.
        """
        if not query:
            logger.warning("Empty query string provided.")
            return np.zeros((self.embedding_dim,), dtype=np.float32)
        return self.encode_texts(query)[0]




    def compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: np.ndarray
            embedding2: np.ndarray

        Returns:
            float similarity score (-1 to 1)
        """
        if embedding1.ndim == 1:
            embedding1 = embedding1 / np.linalg.norm(embedding1)
        if embedding2.ndim == 1:
            embedding2 = embedding2 / np.linalg.norm(embedding2)
        return float(np.dot(embedding1, embedding2))




    def compute_similarities(
        self, embeddings: np.ndarray, query_embedding: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarities for multiple embeddings against a query.

        Args:
            embeddings: np.ndarray of shape (n, dim)
            query_embedding: np.ndarray of shape (dim,)

        Returns:
            np.ndarray of similarity scores
        """
        if query_embedding.ndim == 1:
            query_embedding = query_embedding / np.linalg.norm(query_embedding)
        embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        return np.dot(embeddings_norm, query_embedding)

    def get_embedding_dimension(self) -> int:
        """Return the dimension of embeddings."""
        return self.embedding_dim


# Global instance
embedding_service = EmbeddingService()
