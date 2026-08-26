"""
RAG Service - Retrieval Augmented Generation & Document Knowledge Engine for AuraAI.

Integrates file discovery, document parsing (PDF, DOCX, TXT, MD, JSON),
vector indexing, semantic/keyword retrieval, and file launching into a unified service.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.file_service import FileService
from .chunker import Chunker
from .citation_engine import CitationEngine
from .embedding_manager import EmbeddingManager
from .graph_store import GraphStore
from .models import DocumentChunk, DocumentMetadata, RetrievalMode, RetrievalResult, SourceType
from .parsers import get_parser_registry
from .retrieval_engine import RetrievalEngine
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RAGService:
    """
    Unified RAG Service for document intelligence and file retrieval.
    
    Capabilities:
    1. Search & Open Files (e.g., 'open Sreekanta_resume', 'open my resume')
    2. Extract & Index Document Knowledge (PDF, DOCX, TXT, MD, CSV, PPTX, JSON)
    3. Query Knowledge Base with citations (e.g., 'what skills are in my resume?')
    4. Inject relevant document context into ConversationEngine prompts
    """

    _instance: RAGService | None = None

    def __init__(
        self,
        store_path: str | Path | None = None,
        file_service: FileService | None = None,
    ):
        """Initialize RAG Service components."""
        self.store_path = Path(store_path or (_PROJECT_ROOT / "data" / "rag_store"))
        self.store_path.mkdir(parents=True, exist_ok=True)

        self.file_service = file_service or FileService.get_instance()
        self.parser_registry = get_parser_registry()
        self.chunker = Chunker(chunk_size=500, chunk_overlap=50)
        self.embedding_manager = EmbeddingManager()
        self.vector_store = VectorStore(
            store_path=str(self.store_path / "vectors"),
            embedding_manager=self.embedding_manager,
        )
        self.graph_store = GraphStore(vector_store=self.vector_store)
        self.citation_engine = CitationEngine()
        self.retrieval_engine = RetrievalEngine(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            chunker=self.chunker,
        )

        self._indexed_files: set[str] = set()

    @classmethod
    def get_instance(cls) -> RAGService:
        """Singleton accessor for RAGService."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def index_file(self, file_path: Path | str) -> bool:
        """
        Parse and index a single document file into the vector and graph stores.
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            logger.warning(f"[RAGService] File not found for indexing: {path}")
            return False

        path_key = str(path.resolve()).lower()
        if path_key in self._indexed_files:
            return True

        chunks = []
        try:
            try:
                chunks = self.parser_registry.parse(path)
            except Exception as pe:
                logger.debug(f"[RAGService] Parser registry parse notice for {path.name}: {pe}")

            if not chunks:
                # Fallback: read plain text if supported
                try:
                    text_content = path.read_text(encoding="utf-8", errors="ignore")
                    if text_content.strip():
                        chunks = self.chunker.chunk_document(
                            content=text_content,
                            document_id=path.stem,
                            metadata=DocumentMetadata(
                                document_id=path.stem,
                                title=path.name,
                                file_path=str(path),
                                file_type=path.suffix.lstrip("."),
                                file_size=path.stat().st_size,
                                created_at=datetime.fromtimestamp(path.stat().st_ctime),
                                modified_at=datetime.fromtimestamp(path.stat().st_mtime),
                            ),
                        )
                except Exception:
                    pass

            if chunks:
                self.vector_store.add_chunks(chunks)
                self._indexed_files.add(path_key)
                logger.info(f"[RAGService] Successfully indexed {len(chunks)} chunks from {path.name}")
                return True
        except Exception as e:
            logger.error(f"[RAGService] Error indexing file {path}: {e}")

        return False

    def index_user_documents(self, max_files: int = 20) -> int:
        """
        Scan user search roots for relevant documents (resumes, notes, PDFs, docs) and index them.
        """
        indexed_count = 0
        candidate_files = []
        for root in self.file_service.get_search_roots():
            if not root.exists():
                continue
            for ext in (".pdf", ".docx", ".txt", ".md"):
                try:
                    for f in root.glob(f"*{ext}"):
                        if f.is_file() and not f.name.startswith((".", "~$")):
                            candidate_files.append(f)
                            if len(candidate_files) >= max_files:
                                break
                except Exception:
                    pass
            if len(candidate_files) >= max_files:
                break

        for f in candidate_files:
            if self.index_file(f):
                indexed_count += 1

        return indexed_count

    def find_and_open_document(self, query: str) -> tuple[bool, str]:
        """
        Search for a document matching the query and open it with the default viewer.
        
        Example queries: 'open Sreekanta_resume', 'open my resume', 'open notes.md'
        """
        ok, msg, matched_path = self.file_service.find_and_open(query)
        if ok and matched_path:
            # Also asynchronously index the opened document into RAG for future queries
            try:
                self.index_file(matched_path)
            except Exception:
                pass
            return True, msg

        return False, msg

    def query(self, query_text: str, top_k: int = 5) -> dict[str, Any]:
        """
        Query the RAG system for knowledge passages matching the query.
        
        Returns structured results with answer context, snippets, and citations.
        """
        # Ensure any on-demand files referenced in the query are indexed if found
        file_match = self.file_service.find_best_file(query_text)
        if file_match and str(file_match.resolve()).lower() not in self._indexed_files:
            self.index_file(file_match)

        retrieval_results = self.retrieval_engine.retrieve(
            query=query_text,
            top_k=top_k,
            mode=RetrievalMode.HYBRID,
            include_citations=True,
        )

        # Check for self-reference (e.g. "my resume", "i worked")
        is_self_query = bool(re.search(r"\b(my|i|me|mine|myself|worked|company|experience)\b", query_text, re.IGNORECASE))
        user_aliases = self.file_service.get_known_user_aliases()

        snippets: list[dict[str, Any]] = []
        for res in retrieval_results:
            source = (
                (res.chunk.metadata.get("file_path") if isinstance(res.chunk.metadata, dict) else None)
                or getattr(res.chunk, "source_file", None)
                or getattr(res.chunk, "title", None)
                or "Knowledge Base"
            )
            doc_id = (
                (res.chunk.metadata.get("document_id") if isinstance(res.chunk.metadata, dict) else None)
                or getattr(res.chunk, "id", "doc")
            )
            
            score = res.score
            source_lower = str(source).lower()
            doc_id_lower = str(doc_id).lower()

            if is_self_query:
                if any(alias in source_lower or alias in doc_id_lower for alias in user_aliases):
                    score += 0.50
                elif any(other in source_lower for other in ("mohammed", "khan", "john", "alex")):
                    score -= 0.50

            snippets.append({
                "content": res.chunk.content,
                "document_id": doc_id,
                "score": score,
                "source": source,
                "citations": [c.format() if hasattr(c, "format") else str(c) for c in (res.citations or [])],
            })

        snippets.sort(key=lambda s: s["score"], reverse=True)

        return {
            "query": query_text,
            "results_count": len(snippets),
            "results": snippets,
            "has_context": len(snippets) > 0,
        }

    def get_relevant_context(self, query_text: str, max_chars: int = 1500) -> str | None:
        """
        Retrieve formatted document context for prompt augmentation.
        """
        data = self.query(query_text, top_k=3)
        if not data.get("has_context"):
            # Check if there is a matching file we can read directly
            best_file = self.file_service.find_best_file(query_text)
            if best_file and best_file.suffix.lower() in (".txt", ".md", ".json", ".csv"):
                try:
                    text = best_file.read_text(encoding="utf-8", errors="ignore")[:max_chars]
                    return f"Document Content ({best_file.name}):\n{text}"
                except Exception:
                    pass
            return None

        is_self_query = bool(re.search(r"\b(my|i|me|mine|myself|worked|company|experience)\b", query_text, re.IGNORECASE))
        user_aliases = self.file_service.get_known_user_aliases()
        results = data["results"]
        if is_self_query:
            user_specific = [
                r for r in results
                if any(alias in str(r.get("source", "")).lower() or alias in str(r.get("document_id", "")).lower() for alias in user_aliases)
            ]
            if user_specific:
                results = user_specific

        parts = []
        for r in results:
            src = r["source"]
            content = r["content"].strip()
            parts.append(f"[{src}]:\n{content}")

        combined = "\n\n---\n\n".join(parts)
        return combined[:max_chars] if combined else None
