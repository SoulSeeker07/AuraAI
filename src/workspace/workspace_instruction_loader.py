"""
M19.3 Workspace Instruction Loader
===================================
Location: src/workspace/workspace_instruction_loader.py

Discovers, parses, and loads standing project-level instructions (AURA.md, .aura/AURA.md)
into system prompt context and policy rules.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WorkspaceInstructionLoader:
    """Discovers and parses project standing instructions (AURA.md)."""

    DEFAULT_FILES = [
        ".aura/AURA.md",
        "AURA.md",
        ".aura/instructions/AURA.md",
    ]

    def __init__(self, workspace_root: str | Path | None = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    def discover_files(self) -> list[Path]:
        """Find all existing AURA.md instruction files in order of priority."""
        found: list[Path] = []

        # Check default locations
        for rel_path in self.DEFAULT_FILES:
            full_path = self.workspace_root / rel_path
            if full_path.exists() and full_path.is_file():
                found.append(full_path)

        # Check .aura/instructions/ directory for extra md files
        extra_dir = self.workspace_root / ".aura" / "instructions"
        if extra_dir.exists() and extra_dir.is_dir():
            for p in extra_dir.glob("*.md"):
                if p not in found:
                    found.append(p)

        return found

    def load_instructions(self) -> dict[str, Any]:
        """
        Load and parse standing instructions from discovered AURA.md files.

        Returns:
            Dict containing 'raw_text', 'sections', and 'loaded_files'.
        """
        files = self.discover_files()
        if not files:
            logger.debug("No AURA.md workspace instruction files discovered.")
            return {
                "raw_text": "",
                "sections": {},
                "loaded_files": [],
            }

        sections: dict[str, str] = {}
        raw_parts: list[str] = []
        loaded_paths: list[str] = []

        for filepath in files:
            try:
                content = filepath.read_text(encoding="utf-8")
                raw_parts.append(f"<!-- Loaded from {filepath.name} -->\n{content}")
                loaded_paths.append(str(filepath))

                # Simple markdown section parser
                current_section = "General"
                current_lines: list[str] = []

                for line in content.splitlines():
                    if line.startswith("## "):
                        if current_lines:
                            sections[current_section] = sections.get(current_section, "") + "\n" + "\n".join(current_lines)
                            current_lines = []
                        current_section = line[3:].strip()
                    else:
                        current_lines.append(line)

                if current_lines:
                    sections[current_section] = sections.get(current_section, "") + "\n" + "\n".join(current_lines)

            except Exception as e:
                logger.warning(f"Failed to read instruction file {filepath}: {e}")

        raw_text = "\n\n".join(raw_parts).strip()
        logger.info(f"Loaded workspace instructions from {len(loaded_paths)} file(s).")

        return {
            "raw_text": raw_text,
            "sections": sections,
            "loaded_files": loaded_paths,
        }


__all__ = ["WorkspaceInstructionLoader"]
