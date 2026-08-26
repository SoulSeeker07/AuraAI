"""
Central Cognitive Memory Engine
Location: src/memory/cognitive_memory.py

Main orchestrator for Milestone 17 Cognitive Memory System.
Coordinates SQLite persistence, all 8 memory types, memory provenance,
ranked recall, consolidation, decay, and project isolation.
"""

import datetime as dt
import json
import logging
import sqlite3
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from .consolidation_engine import ConsolidationEngine
from .decay_engine import DecayEngine
from .episodic_memory import EpisodicMemoryRecorder
from .models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource
from .procedural_memory import ProceduralMemoryStore
from .project_isolation import ProjectMemoryFilter
from .recall_engine import RecallEngine
from .semantic_memory import SemanticMemoryStore
from .working_memory import WorkingMemoryManager

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "Memory.db"


class CognitiveMemoryEngine:
    """
    Central Cognitive Memory Engine backing the AuraAI memory subsystem.
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize sub-managers
        self.working_memory = WorkingMemoryManager()
        self.episodic_memory = EpisodicMemoryRecorder()
        self.semantic_memory = SemanticMemoryStore()
        self.procedural_memory = ProceduralMemoryStore()
        self.recall_engine = RecallEngine()
        self.consolidation_engine = ConsolidationEngine()
        self.decay_engine = DecayEngine()
        self.project_filter = ProjectMemoryFilter()

        self._init_db()
        logger.info(f"[CognitiveMemoryEngine] Initialized with DB at: {self.db_path}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize SQLite database tables for cognitive memories."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_memories (
                    memory_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    importance REAL NOT NULL,
                    confidence REAL NOT NULL,
                    project_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    access_count INTEGER NOT NULL,
                    last_accessed TEXT NOT NULL,
                    expires_at TEXT,
                    metadata TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_mem_type ON cognitive_memories(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_mem_project ON cognitive_memories(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_mem_importance ON cognitive_memories(importance)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_mem_topic ON cognitive_memories(topic)")

            # Legacy facts & topics table support
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(category, key, value)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def store_memory(self, memory: MemoryItem) -> MemoryItem:
        """Store or update a MemoryItem in SQLite database."""
        now = dt.datetime.now().isoformat(timespec="seconds")
        memory.updated_at = now

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cognitive_memories (
                    memory_id, type, content, provenance, created_at, updated_at,
                    importance, confidence, project_id, topic, access_count,
                    last_accessed, expires_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    content = excluded.content,
                    updated_at = excluded.updated_at,
                    importance = excluded.importance,
                    confidence = excluded.confidence,
                    access_count = cognitive_memories.access_count + 1,
                    last_accessed = excluded.last_accessed,
                    metadata = excluded.metadata
                """,
                (
                    memory.memory_id,
                    memory.type.value if isinstance(memory.type, Enum) else str(memory.type),
                    memory.content,
                    json.dumps(memory.provenance.to_dict()),
                    memory.created_at,
                    memory.updated_at,
                    memory.importance,
                    memory.confidence,
                    memory.project_id,
                    memory.topic,
                    memory.access_count,
                    memory.last_accessed,
                    memory.expires_at,
                    json.dumps(memory.metadata),
                ),
            )
        logger.debug(f"[CognitiveMemoryEngine] Stored memory '{memory.memory_id}' [{memory.type}]")
        return memory

    def get_memory(self, memory_id: str) -> MemoryItem | None:
        """Retrieve a MemoryItem by ID."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT memory_id, type, content, provenance, created_at, updated_at,
                       importance, confidence, project_id, topic, access_count,
                       last_accessed, expires_at, metadata
                FROM cognitive_memories WHERE memory_id = ?
                """,
                (memory_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_memory_item(row)

    def search_memories(
        self,
        query: str = "",
        memory_type: MemoryType | str | None = None,
        project_id: str = "global",
        limit: int = 20,
        include_expired: bool = False,
    ) -> list[MemoryItem]:
        """
        Search memories matching query, optionally filtering by type and project.
        """
        with self._connect() as conn:
            sql = "SELECT memory_id, type, content, provenance, created_at, updated_at, importance, confidence, project_id, topic, access_count, last_accessed, expires_at, metadata FROM cognitive_memories WHERE 1=1"
            params: list[Any] = []

            if query.strip():
                words = [w.lower() for w in query.strip().split() if len(w) > 2]
                if words:
                    word_clauses = []
                    for w in words:
                        pat = f"%{w}%"
                        word_clauses.append("(lower(content) LIKE ? OR lower(topic) LIKE ? OR lower(metadata) LIKE ?)")
                        params.extend([pat, pat, pat])
                    sql += " AND (" + " OR ".join(word_clauses) + ")"
                else:
                    pattern = f"%{query.strip().lower()}%"
                    sql += " AND (lower(content) LIKE ? OR lower(topic) LIKE ? OR lower(metadata) LIKE ?)"
                    params.extend([pattern, pattern, pattern])

            if memory_type:
                t_val = memory_type.value if isinstance(memory_type, Enum) else str(memory_type)
                sql += " AND type = ?"
                params.append(t_val)

            sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
            params.append(limit * 2)

            rows = conn.execute(sql, params).fetchall()
            items = [self._row_to_memory_item(r) for r in rows]

        # Apply project isolation filter
        items = self.project_filter.filter_for_project(items, active_project=project_id)

        # Apply decay filter to discard expired items unless explicitly requested
        if include_expired:
            return items[:limit]
        valid_items = [m for m in items if not self.decay_engine.is_expired(m)]
        return valid_items[:limit]

    def recall_ranked(
        self,
        query: str,
        active_project: str = "global",
        limit: int = 10,
    ) -> list[MemoryItem]:
        """
        Recall top-ranked, relevant memories for active context injection using RecallEngine.
        """
        candidates = self.search_memories(query=query, project_id=active_project, limit=50)
        scored = self.recall_engine.score_and_rank(query, candidates, active_project=active_project, limit=limit)
        return [mem for score, mem in scored]

    def count_memories(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM cognitive_memories").fetchone()
            return row[0] if row else 0

    def _row_to_memory_item(self, row: tuple) -> MemoryItem:
        prov_dict = json.loads(row[3]) if row[3] else {}
        meta_dict = json.loads(row[13]) if row[13] else {}
        prov = MemoryProvenance.from_dict(prov_dict)

        mt = row[1]
        try:
            type_enum = MemoryType(mt)
        except ValueError:
            type_enum = MemoryType.LONG_TERM

        return MemoryItem(
            memory_id=row[0],
            type=type_enum,
            content=row[2],
            provenance=prov,
            created_at=row[4],
            updated_at=row[5],
            importance=row[6],
            confidence=row[7],
            project_id=row[8],
            topic=row[9],
            access_count=row[10],
            last_accessed=row[11],
            expires_at=row[12],
            metadata=meta_dict,
        )

    def import_from_external(
        self,
        export_path: str,
        source: str = "claude",
        dry_run: bool = False,
    ) -> Any:
        """
        Import memories from an external assistant export (Claude / ChatGPT).
        """
        source_lower = source.lower().strip()
        if source_lower == "claude":
            from .importers.claude_importer import ClaudeImporter
            importer = ClaudeImporter()
        elif source_lower in ("chatgpt", "openai"):
            from .importers.chatgpt_importer import ChatGPTImporter
            importer = ChatGPTImporter()
        else:
            raise ValueError(f"Unsupported memory import source: {source}. Expected 'claude' or 'chatgpt'.")

        return importer.import_to_memory(export_path, self, dry_run=dry_run)

    def rollback_import(self, batch_id: str) -> int:
        """
        Delete all memories created under a specific import batch_id.
        """
        deleted_count = 0
        with self._connect() as conn:
            cursor = conn.execute("SELECT memory_id, content, metadata FROM cognitive_memories")
            to_delete = []
            for row in cursor.fetchall():
                mem_id, content, meta_json = row[0], row[1], row[2]
                if meta_json:
                    try:
                        meta = json.loads(meta_json)
                        if meta.get("import_batch_id") == batch_id:
                            to_delete.append((mem_id, content))
                    except Exception:
                        pass

            for mem_id, content in to_delete:
                conn.execute("DELETE FROM cognitive_memories WHERE memory_id = ?", (mem_id,))
                deleted_count += 1
                logger.info(f"[CognitiveMemoryEngine] Rollback deleted '{mem_id}': {content[:60]!r}")

        logger.info(f"[CognitiveMemoryEngine] Rolled back batch '{batch_id}': deleted {deleted_count} memories.")
        return deleted_count

    def run_consolidation(self, dry_run: bool = False) -> Any:
        """
        Run the Auto-Dream consolidation pipeline (dedup, prune, promote).
        """
        from .consolidation_task import MemoryConsolidationTask
        task = MemoryConsolidationTask()
        return task.run(self, dry_run=dry_run)

    def get_retrieval_gate(self, **kwargs: Any) -> Any:
        """
        Factory method to get a configured MemoryRetrievalGate wired to this engine.
        """
        from .retrieval_gate import MemoryRetrievalGate
        return MemoryRetrievalGate(self, **kwargs)

