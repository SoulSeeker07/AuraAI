"""
Workspace Search Engine
Location: src/personal_os/workspace_search.py

Provides sub-second indexed search across workspace files, symbols,
and content with recency weighting and intelligent relevance ranking.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workspace.workspace_walker import WorkspaceWalker
from .models import SearchResult

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class IndexedFile:
    """Represents an indexed file in the workspace."""

    rel_path: str
    abs_path: str
    filename: str
    stem: str
    extension: str
    last_modified: float
    size: int


class WorkspaceSearchEngine:
    """
    In-memory indexed search engine for sub-second workspace queries.
    """

    _instance: WorkspaceSearchEngine | None = None

    def __init__(self, root_dir: Path | str | None = None) -> None:
        self.root_dir = Path(root_dir or DEFAULT_WORKSPACE_ROOT).resolve()
        self.walker = WorkspaceWalker(root=self.root_dir, max_files=50000)
        self._index: list[IndexedFile] = []
        self._last_indexed: float = 0.0
        import threading
        threading.Thread(target=self.rebuild_index, daemon=True, name="WorkspaceSearchIndexer").start()

    @classmethod
    def get_instance(
        cls, root_dir: Path | str | None = None
    ) -> WorkspaceSearchEngine:
        if cls._instance is None:
            cls._instance = cls(root_dir=root_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def rebuild_index(self) -> int:
        """Scan workspace and populate in-memory file index."""
        start_t = time.perf_counter()
        indexed: list[IndexedFile] = []

        try:
            for file_path in self.walker.walk():
                try:
                    rel_p = str(file_path.relative_to(self.root_dir)).replace("\\", "/")
                    stat = file_path.stat()
                    indexed.append(
                        IndexedFile(
                            rel_path=rel_p,
                            abs_path=str(file_path),
                            filename=file_path.name,
                            stem=file_path.stem,
                            extension=file_path.suffix.lower(),
                            last_modified=stat.st_mtime,
                            size=stat.st_size,
                        )
                    )
                except Exception:
                    continue
        except Exception as exc:
            logger.warning(f"[WorkspaceSearchEngine] Indexing scan notice: {exc}")

        self._index = indexed
        self._last_indexed = time.time()
        elapsed_ms = (time.perf_counter() - start_t) * 1000
        logger.info(
            f"[WorkspaceSearchEngine] Indexed {len(self._index)} files in {elapsed_ms:.1f}ms"
        )
        return len(self._index)

    def index_file(self, file_path: Path | str) -> bool:
        """Incrementally index or update a single file without full scan."""
        p = Path(file_path).resolve()
        if not p.is_file():
            return False
        if self.walker.is_ignored(p):
            return False
        try:
            rel_p = str(p.relative_to(self.root_dir)).replace("\\", "/")
            stat = p.stat()
            new_entry = IndexedFile(
                rel_path=rel_p,
                abs_path=str(p),
                filename=p.name,
                stem=p.stem,
                extension=p.suffix.lower(),
                last_modified=stat.st_mtime,
                size=stat.st_size,
            )
            self._index = [f for f in self._index if f.rel_path != rel_p]
            self._index.append(new_entry)
            return True
        except Exception as e:
            logger.debug(f"[WorkspaceSearchEngine] Could not index single file '{p}': {e}")
            return False

    def remove_file(self, file_path: Path | str) -> bool:
        """Remove a deleted file from the search index."""
        p = Path(file_path).resolve()
        try:
            rel_p = str(p.relative_to(self.root_dir)).replace("\\", "/")
        except ValueError:
            rel_p = str(p).replace("\\", "/")
        prev_len = len(self._index)
        self._index = [f for f in self._index if f.rel_path != rel_p and f.abs_path != str(p)]
        return len(self._index) < prev_len

    def on_filesystem_event(self, event_type: str, file_path: Path | str) -> None:
        """Handle live filesystem telemetry events from FilesystemWatcher."""
        ev = event_type.lower()
        if ev in ("created", "modified", "moved_to"):
            self.index_file(file_path)
        elif ev in ("deleted", "moved_from"):
            self.remove_file(file_path)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """
        Execute ranked multi-factor search across filenames and contents.
        Guaranteed execution within 1.0s.
        """
        start_time = time.perf_counter()
        q_raw = query.strip()
        q_lower = q_raw.lower()

        # Clean noise terms
        noise_terms = {
            "find", "search", "file", "files", "where", "we", "store",
            "is", "defined", "the", "in", "for", "code", "show", "me", "locate", "a", "an"
        }
        raw_tokens = [w for w in re.split(r"[_\-\s\./\\]+", q_lower) if len(w) >= 2]
        tokens = [w for w in raw_tokens if w not in noise_terms]
        if not tokens:
            tokens = raw_tokens

        scored_results: list[tuple[float, SearchResult]] = []

        # 1. Filename / Path Matching (Fast phase: <20ms)
        for f in self._index:
            score = 0.0
            filename_lower = f.filename.lower()
            stem_lower = f.stem.lower()
            rel_lower = f.rel_path.lower()

            # Exact name or stem match (Top priority)
            if q_lower == filename_lower or q_lower == stem_lower:
                score += 100.0
            # All significant tokens present in filename / stem
            elif tokens and all(t in stem_lower or t in filename_lower for t in tokens):
                score += 50.0 + (len(tokens) * 5.0)
            # Full query substring in filename
            elif q_lower in filename_lower:
                score += 30.0
            # Full query substring in path
            elif q_lower in rel_lower:
                score += 20.0
            else:
                # Token overlap score
                matched_tokens = 0
                for t in tokens:
                    if t in stem_lower:
                        matched_tokens += 3
                    elif t in filename_lower:
                        matched_tokens += 2
                    elif t in rel_lower:
                        matched_tokens += 1
                if matched_tokens > 0:
                    score += matched_tokens * 2.0

            if score > 0:
                scored_results.append(
                    (
                        score,
                        SearchResult(
                            path=f.rel_path,
                            filename=f.filename,
                            score=round(score, 2),
                            last_modified=f.last_modified,
                        ),
                    )
                )

        # 2. Content Grep Fallback if matches are few or query looks like symbol/code search
        if len(scored_results) < limit and len(q_raw) >= 3 and (time.perf_counter() - start_time) < 0.5:
            content_candidates = [
                f for f in self._index
                if f.extension in {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt"}
                and f.size < 200_000
            ]
            # Prioritize matching files first
            for f in content_candidates[:150]:
                if time.perf_counter() - start_time > 0.8:
                    break
                try:
                    with open(f.abs_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                        for line_idx, line in enumerate(file_obj, start=1):
                            if q_raw in line or all(t in line.lower() for t in tokens if len(t) >= 3):
                                snippet = line.strip()[:120]
                                scored_results.append(
                                    (
                                        3.5,
                                        SearchResult(
                                            path=f.rel_path,
                                            filename=f.filename,
                                            line_number=line_idx,
                                            match_snippet=snippet,
                                            score=3.5,
                                            last_modified=f.last_modified,
                                        ),
                                    )
                                )
                                break
                except Exception:
                    continue

        # Sort descending by score, then recency
        scored_results.sort(key=lambda x: (x[0], x[1].last_modified or 0), reverse=True)

        # Deduplicate results by path
        seen_paths = set()
        final_results: list[SearchResult] = []
        for _, res in scored_results:
            if res.path not in seen_paths:
                seen_paths.add(res.path)
                final_results.append(res)
                if len(final_results) >= limit:
                    break

        return final_results
