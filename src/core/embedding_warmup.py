"""
embedding_warmup.py

Pattern for warming the SentenceTransformer/Chroma embedding model in the
background at AuraCore startup in a dedicated OS thread, so the ~17-20s cold-start cost
never blocks a user's first request and never deadlocks with the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class EmbeddingModelWarmup:
    """
    Attach one instance of this to AuraCore. Call start_background_warmup()
    once during AuraCore startup. Any code path that needs the embedding
    model (AmbientContextBuilder, memory recall, etc.) calls
    `await warmup.ensure_ready()` or `warmup.ensure_ready_sync()` instead
    of loading the model itself.
    """

    def __init__(self, load_fn: Optional[Callable[[], Any]] = None) -> None:
        if load_fn is None:
            def _default_load():
                try:
                    from memory.vector_memory import VectorMemoryEngine
                    return VectorMemoryEngine.get_instance().get_model()
                except Exception as e:
                    logger.warning(f"[EmbeddingWarmup] Default load_fn fallback: {e}")
                    return None
            self._load_fn = _default_load
        else:
            self._load_fn = load_fn

        self._thread: Optional[threading.Thread] = None
        self._model: Any = None
        self._ready_event = threading.Event()
        self._lock = threading.Lock()

    def start_background_warmup(self) -> None:
        """Call this once early in AuraCore init — fire and forget."""
        with self._lock:
            if self._ready_event.is_set() or self._thread is not None:
                return  # already in flight or ready

            self._thread = threading.Thread(target=self._warm_worker, daemon=True, name="EmbeddingModelWarmupThread")
            self._thread.start()

    def _warm_worker(self) -> None:
        start = time.time()
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            kernel32.GetCurrentThread.restype = wintypes.HANDLE
            kernel32.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
            kernel32.SetThreadPriority.restype = wintypes.BOOL
            # THREAD_PRIORITY_BELOW_NORMAL = -1
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), -1)
        except Exception:
            pass

        logger.info("[EmbeddingWarmup] Background OS thread embedding model warmup started...")
        try:
            self._model = self._load_fn()
        except Exception as e:
            logger.warning(f"[EmbeddingWarmup] Error during warmup: {e}")
        finally:
            self._ready_event.set()
            elapsed = time.time() - start
            logger.info(f"[EmbeddingWarmup] Embedding model warmup finished in {elapsed:.2f}s")

    async def ensure_ready(self) -> Any:
        """
        Awaitable: if warmup already finished, returns instantly.
        If in flight, awaits the single shared in-flight load in a background worker.
        """
        if self._ready_event.is_set():
            return self._model

        self.start_background_warmup()
        await asyncio.to_thread(self._ready_event.wait)
        return self._model

    def ensure_ready_sync(self, timeout: Optional[float] = None) -> Any:
        """Synchronous variant of ensure_ready."""
        if self._ready_event.is_set():
            return self._model

        self.start_background_warmup()
        self._ready_event.wait(timeout=timeout)
        return self._model

    @property
    def is_ready(self) -> bool:
        return self._ready_event.is_set()
