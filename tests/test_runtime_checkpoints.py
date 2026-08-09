"""
Tests for M19.4 Runtime Checkpoint System
Location: tests/test_runtime_checkpoints.py
"""

import pytest
from src.core.orchestration.runtime_checkpoint import (
    RuntimeCheckpointManager,
    ActionReversibility,
)


def test_checkpoint_creation_and_persistence(tmp_path):
    db_file = tmp_path / "test_memory.db"
    dummy_file = tmp_path / "sample.txt"
    dummy_file.write_text("hello aura", encoding="utf-8")

    mgr = RuntimeCheckpointManager(db_path=db_file)

    cp = mgr.create_checkpoint(
        session_id="sess_123",
        goal="Edit sample.txt",
        step_id=1,
        files=[str(dummy_file)],
        browser_url="https://youtube.com",
        reversibility=ActionReversibility.REVERSIBLE,
    )

    assert cp.checkpoint_id is not None
    assert cp.files_and_hashes[str(dummy_file)] != ""
    assert cp.reversibility == ActionReversibility.REVERSIBLE

    # Verify persistence & loading
    loaded = mgr.load_last_checkpoint("sess_123")
    assert loaded is not None
    assert loaded.checkpoint_id == cp.checkpoint_id
    assert loaded.goal == "Edit sample.txt"
    assert loaded.reversibility == ActionReversibility.REVERSIBLE
