"""
Vector Memory Engine — Real Dense Neural Embeddings
===================================================
Provides thread-safe, high-performance, matrix-vectorized dense vector embedding search for
Aura's persistent memory using all-MiniLM-L6-v2 (384-dim CPU vectors via BLAS).
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class VectorMemoryEngine:
    """
    Manages dense vector embeddings for facts, preferences, and knowledge.
    Thread-safe under concurrent access from voice pipelines, background daemons, and orchestrators.
    """

    _instance: VectorMemoryEngine | None = None
    _lock = threading.Lock()

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else Path("Memory.db")
        self._model = None
        self._model_lock = threading.Lock()
        self._cache_lock = threading.RLock()  # Thread-safe guard for cache and matrix mutations
        
        self._embedding_cache: dict[str, np.ndarray] = {}
        
        # Matrix-vectorized acceleration buffers
        self._matrix: np.ndarray | None = None
        self._matrix_keys: list[str] = []
        self._matrix_dirty: bool = True
        
        self._init_vector_table()

    @contextmanager
    def _connect(self):
        """Per-call thread-safe SQLite connection with explicit close in finally."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def get_instance(cls, db_path: Path | str | None = None) -> VectorMemoryEngine:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path=db_path)
            elif db_path is not None and Path(db_path) != cls._instance.db_path:
                cls._instance.db_path = Path(db_path)
                with cls._instance._cache_lock:
                    cls._instance._embedding_cache.clear()
                    cls._instance._matrix = None
                    cls._instance._matrix_keys = []
                    cls._instance._matrix_dirty = True
                cls._instance._init_vector_table()
            return cls._instance

    def get_model(self):
        """Public accessor to get the shared SentenceTransformer singleton instance."""
        return self._get_model()

    def _get_model(self):
        """Lazy-load the SentenceTransformer model on CPU once as a process singleton."""
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        logger.info("[VectorMemory] Loading all-MiniLM-L6-v2 on CPU...")
                        self._model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
                        logger.info("[VectorMemory] Dense neural embedding model ready.")
                    except Exception as e:
                        logger.warning(f"[VectorMemory] Could not load SentenceTransformer: {e}")
                        self._model = False
        return self._model if self._model is not False else None

    def _init_vector_table(self):
        """Initialize vector embeddings storage table in SQLite."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fact_embeddings (
                        category TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        embedding BLOB NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (category, key)
                    );
                    """
                )
                self._load_cached_embeddings(conn)
        except Exception as e:
            logger.debug(f"[VectorMemory] Table init note: {e}")

    def _load_cached_embeddings(self, conn: sqlite3.Connection):
        """Pre-warm in-memory vector cache from SQLite."""
        try:
            rows = conn.execute("SELECT category, key, embedding FROM fact_embeddings").fetchall()
            with self._cache_lock:
                for cat, k, blob in rows:
                    vec = np.frombuffer(blob, dtype=np.float32)
                    cache_key = f"{cat}:{k}"
                    self._embedding_cache[cache_key] = vec
                self._matrix_dirty = True
            logger.debug(f"[VectorMemory] Pre-warmed {len(self._embedding_cache)} vector embeddings.")
        except Exception as e:
            logger.debug(f"[VectorMemory] Cache load note: {e}")

    def _sync_matrix(self):
        """Build or refresh contiguous (N, 384) float32 matrix under cache lock."""
        with self._cache_lock:
            if not self._matrix_dirty and self._matrix is not None:
                return

            if not self._embedding_cache:
                self._matrix = None
                self._matrix_keys = []
                self._matrix_dirty = False
                return

            keys = list(self._embedding_cache.keys())
            vectors = [self._embedding_cache[k] for k in keys]
            self._matrix = np.ascontiguousarray(np.vstack(vectors), dtype=np.float32)
            self._matrix_keys = keys
            self._matrix_dirty = False

    def encode(self, text: str) -> np.ndarray | None:
        """Generate normalized 384-dim dense embedding for a single string."""
        model = self._get_model()
        if model is None:
            return None
        try:
            emb = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(emb, dtype=np.float32)
        except Exception as e:
            logger.error(f"[VectorMemory] Embedding generation error: {e}")
            return None

    def encode_batch(self, texts: list[str]) -> list[np.ndarray] | None:
        """Generate normalized dense embeddings in a single vectorized batch pass."""
        if not texts:
            return []
        model = self._get_model()
        if model is None:
            return None
        try:
            embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
            return [np.asarray(e, dtype=np.float32) for e in embs]
        except Exception as e:
            logger.error(f"[VectorMemory] Batch embedding generation error: {e}")
            return None

    def index_fact(self, category: str, key: str, value: str):
        """Encode, cache, and persist dense vector embedding for a fact."""
        text_repr = f"{category} {key}: {value}"
        vec = self.encode(text_repr)
        if vec is None:
            return

        cache_key = f"{category}:{key}"
        with self._cache_lock:
            self._embedding_cache[cache_key] = vec
            self._matrix_dirty = True

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fact_embeddings (category, key, value, embedding)
                    VALUES (?, ?, ?, ?)
                    """,
                    (category, key, value, vec.tobytes()),
                )
        except Exception as e:
            logger.debug(f"[VectorMemory] Fact indexing note: {e}")

    def delete_fact_embedding(self, category: str, key: str) -> bool:
        """Purge vector embedding from in-memory cache, matrix buffer, and SQLite storage."""
        cache_key = f"{category}:{key}"
        deleted = False
        with self._cache_lock:
            if cache_key in self._embedding_cache:
                del self._embedding_cache[cache_key]
                self._matrix_dirty = True
                deleted = True

        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM fact_embeddings WHERE category = ? AND key = ?",
                    (category, key),
                )
                if cursor.rowcount > 0:
                    deleted = True
        except Exception as e:
            logger.debug(f"[VectorMemory] Fact deletion note: {e}")

        return deleted

    def delete_category_embeddings(self, category: str) -> int:
        """Purge all vector embeddings for an entire category."""
        with self._cache_lock:
            keys_to_delete = [k for k in self._embedding_cache if k.startswith(f"{category}:")]
            for k in keys_to_delete:
                del self._embedding_cache[k]
            if keys_to_delete:
                self._matrix_dirty = True

        deleted_count = 0
        try:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM fact_embeddings WHERE category = ?", (category,))
                deleted_count = cursor.rowcount
        except Exception as e:
            logger.debug(f"[VectorMemory] Category deletion note: {e}")

        return deleted_count

    def search(
        self, query: str, facts: list[Any], top_k: int = 5, min_similarity: float = 0.30
    ) -> list[tuple[float, Any]]:
        """
        Perform thread-safe, high-speed matrix-vectorized cosine similarity search:
        sims = Matrix(N, 384) @ query_vec(384,) via single BLAS call.
        """
        query_vec = self.encode(query)
        if query_vec is None or not facts:
            return []

        # ── Thread-Safe Reconciliation: Identify missing facts ──
        missing_items: list[tuple[str, str, Any]] = []
        with self._cache_lock:
            for fact in facts:
                cache_key = f"{fact.category}:{fact.key}"
                if cache_key not in self._embedding_cache:
                    text_repr = f"{fact.category} {fact.key}: {fact.value}"
                    missing_items.append((cache_key, text_repr, fact))

        # ── If missing facts exist, batch encode them outside the lock to prevent blocking ──
        if missing_items:
            texts = [item[1] for item in missing_items]
            embs = self.encode_batch(texts)
            if embs:
                with self._cache_lock:
                    for (cache_key, _, _), vec in zip(missing_items, embs):
                        self._embedding_cache[cache_key] = vec
                    self._matrix_dirty = True

        # ── Synchronize matrix under lock ──
        with self._cache_lock:
            self._sync_matrix()
            if self._matrix is None or len(self._matrix_keys) == 0:
                return []
            matrix_snapshot = self._matrix
            keys_snapshot = list(self._matrix_keys)

        # ── True Matrix-Vector Multiplication: single CPU BLAS call ──
        sim_scores = matrix_snapshot @ query_vec  # Shape: (N,)

        # Build lookup from cache_key -> fact for valid active facts
        active_facts_map = {f"{f.category}:{f.key}": f for f in facts}

        scored_results: list[tuple[float, Any]] = []
        for i, cache_key in enumerate(keys_snapshot):
            if cache_key in active_facts_map:
                score = float(sim_scores[i])
                if score >= min_similarity:
                    scored_results.append((score, active_facts_map[cache_key]))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return scored_results[:top_k]
