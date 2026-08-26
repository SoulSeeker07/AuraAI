"""
Claude Memory Importer
Location: src/memory/importers/claude_importer.py

Parses Claude's data export format into RawMemoryFact entries.

Claude's export (Settings → Privacy → Export data) produces a .zip containing
memory files. The importer handles both .zip archives and extracted directories,
looking for memory entries in JSON format.

No API key, no network calls — reads static local files only.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path

from memory.models import ProvenanceSource

from .base_importer import ExternalMemoryImporter, RawMemoryFact

logger = logging.getLogger(__name__)


class ClaudeImporter(ExternalMemoryImporter):
    """Import adapter for Claude's data export format."""

    @property
    def source_name(self) -> str:
        return "claude"

    @property
    def provenance_source(self) -> ProvenanceSource:
        return ProvenanceSource.CLAUDE_IMPORT

    def parse(self, export_path: str) -> list[RawMemoryFact]:
        """
        Parse a Claude data export into normalized RawMemoryFact entries.

        Accepts either:
        - A .zip file (will be extracted to a temp directory)
        - An already-extracted directory

        Looks for memory data in common Claude export structures:
        - claude_memories/ directory containing JSON files
        - memories.json at root level
        - Any JSON file containing memory-shaped entries

        Returns:
            List of RawMemoryFact, one per memory entry found.
        """
        path = Path(export_path)
        facts: list[RawMemoryFact] = []

        if path.is_file() and path.suffix.lower() == ".zip":
            facts = self._parse_zip(path)
        elif path.is_dir():
            facts = self._parse_directory(path)
        elif path.is_file() and path.suffix.lower() == ".json":
            facts = self._parse_json_file(path)
        else:
            raise ValueError(
                f"Unsupported export path: {export_path}. "
                "Expected a .zip file, .json file, or extracted directory."
            )

        logger.info(f"[ClaudeImporter] Parsed {len(facts)} facts from '{export_path}'")
        return facts

    def _parse_zip(self, zip_path: Path) -> list[RawMemoryFact]:
        """Extract and parse a Claude export .zip."""
        facts: list[RawMemoryFact] = []
        with tempfile.TemporaryDirectory(prefix="aura_claude_import_") as tmpdir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
            facts = self._parse_directory(Path(tmpdir))
        return facts

    def _parse_directory(self, dir_path: Path) -> list[RawMemoryFact]:
        """Parse all memory-related JSON files in a directory tree."""
        facts: list[RawMemoryFact] = []

        # Look for claude_memories/ subdirectory first
        memories_dir = dir_path / "claude_memories"
        if not memories_dir.exists():
            # Also check without underscore
            memories_dir = dir_path / "memories"

        if memories_dir.exists() and memories_dir.is_dir():
            for json_file in sorted(memories_dir.glob("*.json")):
                facts.extend(self._parse_json_file(json_file))

        # Also check for a top-level memories.json
        for candidate in ["memories.json", "claude_memories.json", "memory.json"]:
            mem_file = dir_path / candidate
            if mem_file.exists():
                facts.extend(self._parse_json_file(mem_file))

        # Scan for any other JSON files that might contain memory data
        if not facts:
            for json_file in sorted(dir_path.glob("*.json")):
                if json_file.name.startswith("."):
                    continue
                parsed = self._parse_json_file(json_file)
                if parsed:
                    facts.extend(parsed)

        return facts

    def _parse_json_file(self, json_path: Path) -> list[RawMemoryFact]:
        """Parse a single JSON file for Claude memory entries."""
        facts: list[RawMemoryFact] = []

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            logger.warning(f"[ClaudeImporter] Could not parse {json_path}: {exc}")
            return facts

        entries = self._extract_memory_entries(data)

        for entry in entries:
            fact = self._entry_to_raw_fact(entry, json_path.stem)
            if fact is not None:
                facts.append(fact)

        return facts

    def _extract_memory_entries(self, data: object) -> list[dict]:
        """
        Extract memory-shaped entries from parsed JSON.

        Handles several possible structures:
        - A list of memory dicts directly
        - A dict with a 'memories' or 'entries' key containing a list
        - A single memory dict
        """
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict)]

        if isinstance(data, dict):
            # Check common wrapper keys
            for key in ("memories", "entries", "items", "data", "facts"):
                if key in data and isinstance(data[key], list):
                    return [e for e in data[key] if isinstance(e, dict)]

            # Maybe it's a single memory entry
            if "content" in data or "text" in data or "description" in data:
                return [data]

        return []

    def _entry_to_raw_fact(self, entry: dict, file_context: str) -> RawMemoryFact | None:
        """Convert a Claude memory entry dict to a RawMemoryFact."""
        # Try common field names for the memory text
        text = ""
        for key in ("content", "text", "description", "memory", "fact", "value"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                text = val.strip()
                break

        if not text:
            return None

        # Strip markdown formatting artifacts
        text = text.strip("- ").strip()
        if not text:
            return None

        # Extract timestamp
        timestamp = ""
        for key in ("created_at", "timestamp", "date", "created", "updated_at"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                timestamp = val.strip()
                break

        # Extract category/type hint
        category_hint = ""
        for key in ("type", "category", "topic", "tag", "label"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                category_hint = val.strip()
                break

        return RawMemoryFact(
            text=text,
            category_hint=category_hint,
            timestamp=timestamp,
            source="claude",
            original_key=f"{file_context}:{entry.get('id', '')}",
        )
