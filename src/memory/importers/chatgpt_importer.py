"""
ChatGPT Memory Importer
Location: src/memory/importers/chatgpt_importer.py

Parses ChatGPT's data export format into RawMemoryFact entries.

ChatGPT's export (Settings → Data controls → Export data) produces a .zip
containing a memory.json file — a flat JSON array of memory strings with
no topic structure. Classification relies entirely on SchemaMapper.

No API key, no network calls — reads static local files only.
"""

from __future__ import annotations

import json
import logging
import tempfile
import zipfile
from pathlib import Path

from memory.models import ProvenanceSource

from .base_importer import ExternalMemoryImporter, RawMemoryFact

logger = logging.getLogger(__name__)


class ChatGPTImporter(ExternalMemoryImporter):
    """Import adapter for ChatGPT's data export format."""

    @property
    def source_name(self) -> str:
        return "chatgpt"

    @property
    def provenance_source(self) -> ProvenanceSource:
        return ProvenanceSource.CHATGPT_IMPORT

    def parse(self, export_path: str) -> list[RawMemoryFact]:
        """
        Parse a ChatGPT data export into normalized RawMemoryFact entries.

        Accepts either:
        - A .zip file (will be extracted to a temp directory)
        - An already-extracted directory
        - A direct .json file path

        ChatGPT's memory format is a flat list of memory strings under
        the 'memory' or 'memories' key, or directly as a top-level array.
        No topic structure — SchemaMapper handles all classification.

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

        logger.info(f"[ChatGPTImporter] Parsed {len(facts)} facts from '{export_path}'")
        return facts

    def _parse_zip(self, zip_path: Path) -> list[RawMemoryFact]:
        """Extract and parse a ChatGPT export .zip."""
        facts: list[RawMemoryFact] = []
        with tempfile.TemporaryDirectory(prefix="aura_chatgpt_import_") as tmpdir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
            facts = self._parse_directory(Path(tmpdir))
        return facts

    def _parse_directory(self, dir_path: Path) -> list[RawMemoryFact]:
        """Parse memory files from an extracted ChatGPT export directory."""
        facts: list[RawMemoryFact] = []

        # Primary targets: memory.json or memories.json
        for candidate in ["memory.json", "memories.json"]:
            mem_file = dir_path / candidate
            if mem_file.exists():
                facts.extend(self._parse_json_file(mem_file))
                if facts:
                    return facts

        # Scan subdirectories (ChatGPT sometimes nests under a folder)
        for subdir in sorted(dir_path.iterdir()):
            if subdir.is_dir():
                for candidate in ["memory.json", "memories.json"]:
                    mem_file = subdir / candidate
                    if mem_file.exists():
                        facts.extend(self._parse_json_file(mem_file))
                        if facts:
                            return facts

        # Last resort: try any JSON file at root
        if not facts:
            for json_file in sorted(dir_path.glob("*.json")):
                if json_file.name.startswith("."):
                    continue
                parsed = self._parse_json_file(json_file)
                if parsed:
                    facts.extend(parsed)

        return facts

    def _parse_json_file(self, json_path: Path) -> list[RawMemoryFact]:
        """Parse a single JSON file for ChatGPT memory entries."""
        facts: list[RawMemoryFact] = []

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            logger.warning(f"[ChatGPTImporter] Could not parse {json_path}: {exc}")
            return facts

        entries = self._extract_memory_strings(data)

        for idx, entry_text in enumerate(entries):
            text = entry_text.strip()
            if not text:
                continue

            facts.append(
                RawMemoryFact(
                    text=text,
                    category_hint="",  # ChatGPT has no topic structure
                    timestamp="",
                    source="chatgpt",
                    original_key=f"{json_path.stem}:{idx}",
                )
            )

        return facts

    def _extract_memory_strings(self, data: object) -> list[str]:
        """
        Extract memory strings from parsed JSON.

        Handles:
        - A flat list of strings: ["memory 1", "memory 2"]
        - A dict with 'memory'/'memories' key containing a list of strings
        - A list of dicts with 'content'/'text'/'memory' keys
        - A dict with nested 'model_comparisons' or 'memory' containers
        """
        if isinstance(data, list):
            return self._flatten_list(data)

        if isinstance(data, dict):
            # Check common wrapper keys
            for key in ("memory", "memories", "entries", "items", "data",
                        "model_comparisons"):
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        return self._flatten_list(val)
                    if isinstance(val, dict):
                        # Nested one level deeper
                        for sub_key in ("memory", "memories", "entries"):
                            if sub_key in val and isinstance(val[sub_key], list):
                                return self._flatten_list(val[sub_key])

        return []

    def _flatten_list(self, items: list) -> list[str]:
        """
        Flatten a list that may contain strings or dicts into a list of strings.
        """
        result: list[str] = []
        for item in items:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                # Try common text field names
                for key in ("content", "text", "memory", "fact", "value",
                            "description"):
                    val = item.get(key)
                    if isinstance(val, str) and val.strip():
                        result.append(val.strip())
                        break
        return result
