"""
Knowledge Embedding Manager

Manages embeddings with swappable providers.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from .models import DocumentChunk, EmbeddingProvider

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """
    Base class for embedding providers.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize embedding provider.

        Args:
            api_key: API key for provider
            model: Model name to use
        """
        self.api_key = api_key
        self.model = model or self.get_default_model()
        self.logger = logger

    @abstractmethod
    def get_default_model(self) -> str:
        """Get default model name."""
        pass

    @abstractmethod
    def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        pass

    @abstractmethod
    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        pass


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI embedding provider.
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI API key
            model: Model name (default: text-embedding-3-small)
        """
        super().__init__(api_key, model)
        try:
            import openai

            self.client = openai.OpenAI(api_key=self.api_key)
            self.logger.info(
                f"OpenAI embedding provider initialized with model: {self.model}"
            )
        except ImportError:
            raise ImportError(
                "openai package not installed. Install with: pip install openai"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI: {e}")

    def get_default_model(self) -> str:
        """Get default model."""
        return "text-embedding-3-small"

    def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            return []

        if not getattr(self, "client", None):
            import hashlib, math
            dim = 384
            vec = [0.0] * dim
            for i, w in enumerate(text.lower().split()):
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
                vec[h % dim] += (((h >> 8) % 1000) / 1000.0 - 0.5) * (1.0 / (1.0 + math.log(i + 1)))
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            return [x / norm for x in vec]

        try:
            response = self.client.embeddings.create(input=text, model=self.model)
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"OpenAI embedding error: {e}")
            import hashlib, math
            dim = 384
            vec = [0.0] * dim
            for i, w in enumerate(text.lower().split()):
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
                vec[h % dim] += (((h >> 8) % 1000) / 1000.0 - 0.5) * (1.0 / (1.0 + math.log(i + 1)))
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            return [x / norm for x in vec]

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        if not texts:
            return [[] for _ in texts]

        # Filter empty texts
        valid_texts = [text for text in texts if text and text.strip()]

        if not valid_texts:
            return [[] for _ in texts]

        if not getattr(self, "client", None):
            return [self.get_embedding(t) for t in texts]

        try:
            response = self.client.embeddings.create(
                input=valid_texts, model=self.model
            )
            embeddings = [item.embedding for item in response.data]
            return embeddings
        except Exception as e:
            self.logger.error(f"OpenAI batch embedding error: {e}")
            return [self.get_embedding(text) for text in texts]


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """
    Local embedding provider using sentence-transformers.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str | None = None):
        """
        Initialize local embedding provider.

        Args:
            model_name: Sentence transformer model name
            device: Device to run on (cpu/cuda, or auto-detect if None)
        """
        self.model_name = model_name
        self._model = None
        if device is None or device == "cpu":
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                self.device = "cpu"
        else:
            self.device = device

    @property
    def model(self):
        """Lazy-load SentenceTransformer model only when embedding calculation is performed."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                logger.info(
                    f"Local embedding provider initialized with model: {self.model_name} on {self.device.upper()}"
                )
            except ImportError:
                raise ImportError(
                    "sentence-transformers package not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    def get_default_model(self) -> str:
        """Get default model."""
        return "all-MiniLM-L6-v2"

    def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            return []

        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            self.logger.error(f"Local embedding error: {e}")
            return []

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        if not texts:
            return [[] for _ in texts]

        # Filter empty texts
        valid_texts = [text for text in texts if text and text.strip()]

        if not valid_texts:
            return [[] for _ in texts]

        try:
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            self.logger.error(f"Local batch embedding error: {e}")
            return [self.get_embedding(text) for text in texts]


class FallbackEmbeddingProvider(BaseEmbeddingProvider):
    """
    Lightweight deterministic fallback embedding provider using normalized char/word hashes.
    Guarantees embedding generation with zero external dependencies.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.logger = logger

    def get_default_model(self) -> str:
        return "deterministic-hash-384"

    def get_embedding(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self.dim
        import hashlib
        import math
        vec = [0.0] * self.dim
        words = text.lower().split()
        for i, word in enumerate(words):
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            val = ((h >> 8) % 1000) / 1000.0 - 0.5
            vec[idx] += val * (1.0 / (1.0 + math.log(i + 1)))

        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self.get_embedding(t) for t in texts]


class EmbeddingManager:
    """
    Manages embeddings across multiple providers.
    """

    def __init__(
        self,
        provider: str = EmbeddingProvider.OPENAI,
        api_key: str | None = None,
        model: str | None = None,
        default_chunk_size: int = 500,
    ):
        """
        Initialize embedding manager.

        Args:
            provider: Embedding provider (openai, local, etc.)
            api_key: API key for provider
            model: Model name
            default_chunk_size: Default chunk size for text splitting
        """
        self.provider = provider
        self.default_chunk_size = default_chunk_size
        self._embedding_provider: BaseEmbeddingProvider | None = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the embedding provider with graceful fallback."""
        try:
            if self.provider == EmbeddingProvider.OPENAI:
                self._embedding_provider = OpenAIEmbeddingProvider(
                    api_key=(
                        self._embedding_provider.api_key
                        if self._embedding_provider
                        else None
                    ),
                    model=(
                        self._embedding_provider.model if self._embedding_provider else None
                    ),
                )
            elif self.provider == EmbeddingProvider.LOCAL:
                self._embedding_provider = LocalEmbeddingProvider()
            else:
                self._embedding_provider = FallbackEmbeddingProvider()
        except Exception as e:
            logger.warning(f"Embedding provider initialization fallback to hash provider: {e}")
            self._embedding_provider = FallbackEmbeddingProvider()

    def get_provider(self) -> BaseEmbeddingProvider:
        """
        Get the current embedding provider.

        Returns:
            Embedding provider instance
        """
        return self._embedding_provider

    def set_provider(self, provider: str, **kwargs):
        """
        Change embedding provider.

        Args:
            provider: New provider name
            **kwargs: Provider-specific arguments
        """
        self.provider = provider

        # Preserve model if available
        if self._embedding_provider and hasattr(self._embedding_provider, "model"):
            kwargs["model"] = self._embedding_provider.model

        self._embedding_provider = None
        self._initialize_provider()

    def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        return self._embedding_provider.get_embedding(text)

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        return self._embedding_provider.get_embeddings(texts)

    def get_embedding_for_chunk(self, chunk: DocumentChunk) -> list[float]:
        """
        Get embedding for a document chunk.

        Args:
            chunk: Document chunk

        Returns:
            Embedding vector
        """
        return self.get_embedding(chunk.content)

    def get_embeddings_for_chunks(
        self, chunks: list[DocumentChunk]
    ) -> list[list[float]]:
        """
        Get embeddings for multiple chunks.

        Args:
            chunks: List of document chunks

        Returns:
            List of embedding vectors
        """
        return self.get_embeddings([chunk.content for chunk in chunks])

    def split_text(self, text: str, max_length: int | None = None) -> list[str]:
        """
        Split text into chunks.

        Args:
            text: Input text
            max_length: Maximum length per chunk (defaults to default_chunk_size)

        Returns:
            List of text chunks
        """
        max_length = max_length or self.default_chunk_size
        chunks = []

        # Simple approach: split by max_length
        for i in range(0, len(text), max_length):
            chunks.append(text[i : i + max_length])

        return chunks

    def get_provider_stats(self) -> dict[str, Any]:
        """
        Get provider statistics.

        Returns:
            Dictionary of statistics
        """
        if not self._embedding_provider:
            return {"provider": "none"}

        return {
            "provider": self.provider,
            "model": self._embedding_provider.model,
            "default_chunk_size": self.default_chunk_size,
        }
