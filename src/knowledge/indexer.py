"""
Knowledge Indexer

Background indexing pipeline for continuous document indexing.
"""

import logging
import os
import threading
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from queue import Queue, Empty
from dataclasses import dataclass

from .models import IndexingTask, IndexingStatus, SourceType
from .embedding_manager import EmbeddingManager
from .vector_store import VectorStore
from .graph_store import GraphStore
from .citation_engine import CitationEngine
from .parsers import get_parser_registry

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    """Result of an indexing operation."""
    task_id: str
    status: IndexingStatus
    chunks_added: int
    chunks_processed: int
    errors: List[str]
    duration_seconds: float
    timestamp: datetime


class Indexer:
    """
    Background indexer for continuous document indexing.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        graph_store: GraphStore,
        embedding_manager: EmbeddingManager,
        citation_engine: CitationEngine
    ):
        """
        Initialize indexer.

        Args:
            vector_store: Vector store instance
            graph_store: Graph store instance
            embedding_manager: Embedding manager instance
            citation_engine: Citation engine instance
        """
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.embedding_manager = embedding_manager
        self.citation_engine = citation_engine

        # Parser registry for document parsing
        self.parser_registry = get_parser_registry()

        # Indexing queue
        self.queue: Queue[IndexingTask] = Queue()

        # Statistics
        self.total_processed = 0
        self.total_errors = 0
        self.lock = threading.Lock()

        # Worker thread
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running = False

        logger.info("Indexer initialized")

    def start(self):
        """Start the indexer worker thread."""
        if self.is_running:
            logger.warning("Indexer is already running")
            return

        self.is_running = True
        self.worker_thread = threading.Thread(
            target=self._worker,
            daemon=True
        )
        self.worker_thread.start()
        logger.info("Indexer worker thread started")

    def stop(self):
        """Stop the indexer worker thread."""
        if not self.is_running:
            return

        self.is_running = False

        if self.worker_thread:
            self.worker_thread.join(timeout=5)

        logger.info("Indexer stopped")

    def queue_indexing(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Queue a file for indexing.

        Args:
            file_path: Path to file
            metadata: Optional file metadata

        Returns:
            Task ID
        """
        task = IndexingTask(
            task_id=self._generate_task_id(),
            file_path=file_path,
            status=IndexingStatus.PENDING,
            metadata=metadata,
            created_at=datetime.now(),
            priority=0
        )

        self.queue.put(task)
        logger.info(f"Queued indexing task: {task.task_id} for {file_path}")

        return task.task_id

    def queue_directory(
        self,
        directory: str,
        recursive: bool = True
    ) -> int:
        """
        Queue all files in a directory for indexing.

        Args:
            directory: Directory path
            recursive: Whether to recurse into subdirectories

        Returns:
            Number of tasks queued
        """
        directory_path = Path(directory)

        if not directory_path.exists():
            logger.error(f"Directory does not exist: {directory}")
            return 0

        if not directory_path.is_dir():
            logger.error(f"Path is not a directory: {directory}")
            return 0

        # Find files to index using supported extensions from parser registry
        files = []
        supported_extensions = self.parser_registry.list_supported_extensions()

        for ext in supported_extensions:
            if recursive:
                files.extend(directory_path.rglob(f'*{ext}'))
            else:
                files.extend(directory_path.glob(f'*{ext}'))

        # Queue files
        tasks_queued = 0
        for file_path in files:
            if file_path.is_file():
                self.queue_indexing(str(file_path))
                tasks_queued += 1

        logger.info(f"Queued {tasks_queued} files for indexing from {directory}")
        return tasks_queued

    def process_file(
        self,
        file_path: str
    ) -> IndexingResult:
        """
        Process a single file through the indexing pipeline.

        Args:
            file_path: Path to file

        Returns:
            Indexing result
        """
        logger.info(f"Processing file: {file_path}")

        task = IndexingTask(
            task_id=self._generate_task_id(),
            file_path=file_path,
            status=IndexingStatus.IN_PROGRESS,
            created_at=datetime.now(),
            priority=0
        )

        start_time = time.time()
        errors = []
        chunks_added = 0
        chunks_processed = 0

        try:
            # Parse document using parser registry
            chunks = self.parser_registry.parse(file_path)

            if not chunks:
                logger.warning(f"No chunks generated for {file_path}")
                task.status = IndexingStatus.SUCCESS
                task.chunks_added = 0
                return IndexingResult(
                    task_id=task.task_id,
                    status=IndexingStatus.SUCCESS,
                    chunks_added=0,
                    chunks_processed=0,
                    errors=[],
                    duration_seconds=time.time() - start_time,
                    timestamp=datetime.now()
                )

            chunks_processed = len(chunks)

            if not chunks:
                logger.warning(f"No chunks generated for {file_path}")
                task.status = IndexingStatus.SUCCESS
                task.chunks_added = 0

            else:
                # Create DocumentChunk objects from parsed chunks
                document_chunks = []
                for i, chunk in enumerate(chunks):
                    # Generate unique ID
                    chunk_id = self._generate_chunk_id()

                    # Get metadata from chunk
                    metadata = chunk.metadata
                    metadata_dict = metadata.__dict__ if hasattr(metadata, '__dict__') else {}

                    # Create DocumentChunk
                    doc_chunk = DocumentChunk(
                        id=chunk_id,
                        content=chunk.content,
                        title=metadata_dict.get('chunk_id', file_path),
                        summary=metadata_dict.get('docstring', None),
                        chunk_type=metadata_dict.get('chunk_type', 'file'),
                        source_file=file_path,
                        source_type=metadata.file_type if hasattr(metadata, 'file_type') else 'unknown',
                        chunk_number=i + 1,
                        language=metadata_dict.get('language', None),
                        project=metadata_dict.get('project', None),
                        tags=metadata_dict.get('tags', []),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    document_chunks.append(doc_chunk)

                # Add to vector store
                stats = self.vector_store.add_chunks(document_chunks)
                chunks_added = stats.get('new_chunks_added', 0)

                # Add to graph store
                self.graph_store.add_nodes_from_chunks(document_chunks)
                self.graph_store.add_edges_from_chunks(document_chunks, self.vector_store)

                task.status = IndexingStatus.SUCCESS

            task.chunks_added = chunks_added
            task.chunks_processed = chunks_processed

            logger.info(
                f"Successfully processed {file_path}: "
                f"{chunks_processed} chunks, {chunks_added} added"
            )

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            errors.append(str(e))
            task.status = IndexingStatus.FAILED

            # Re-raise for caller to handle
            raise

        finally:
            duration = time.time() - start_time
            task.duration_seconds = duration
            task.finished_at = datetime.now()

            with self.lock:
                self.total_processed += 1
                self.total_errors += len(errors)

        return IndexingResult(
            task_id=task.task_id,
            status=task.status,
            chunks_added=chunks_added,
            chunks_processed=chunks_processed,
            errors=errors,
            duration_seconds=duration,
            timestamp=datetime.now()
        )

    def _worker(self):
        """Worker thread function."""
        logger.info("Indexer worker thread running")

        while self.is_running:
            try:
                # Wait for task with timeout
                task = self.queue.get(timeout=1)

                if task.status != IndexingStatus.PENDING:
                    continue

                # Process task
                try:
                    self.process_file(task.file_path)
                except Exception as e:
                    logger.error(f"Failed to process {task.file_path}: {e}")

            except Empty:
                # No tasks, continue waiting
                continue
            except KeyboardInterrupt:
                break

        logger.info("Indexer worker thread stopped")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get indexer statistics.

        Returns:
            Statistics dictionary
        """
        with self.lock:
            return {
                'total_processed': self.total_processed,
                'total_errors': self.total_errors,
                'queue_size': self.queue.qsize(),
                'is_running': self.is_running
            }

    def clear_queue(self):
        """Clear the indexing queue."""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Empty:
                break
        logger.info("Indexing queue cleared")

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        return f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.queue.queue) + 1}"

    def _generate_chunk_id(self) -> str:
        """Generate a unique chunk ID."""
        return f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(os.urandom(8)) % 1000000}"


