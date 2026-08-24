"""
Tests for M19.3 Workspace Instructions
Location: tests/test_workspace_instructions.py
"""

import pytest
from pathlib import Path
from workspace.workspace_instruction_loader import WorkspaceInstructionLoader


def test_instruction_loader_discovery_and_parsing(tmp_path):
    aura_md = tmp_path / "AURA.md"
    aura_md.write_text(
        "# Aura Project Instructions\n\n"
        "## Safety\nRequire confirmation for high-risk actions.\n\n"
        "## Execution\nUse pytest.\n",
        encoding="utf-8",
    )

    loader = WorkspaceInstructionLoader(workspace_root=tmp_path)
    discovered = loader.discover_files()
    assert len(discovered) == 1
    assert discovered[0] == aura_md

    res = loader.load_instructions()
    assert "Loaded from AURA.md" in res["raw_text"]
    assert "Safety" in res["sections"]
    assert "Execution" in res["sections"]
    assert "Require confirmation" in res["sections"]["Safety"]
