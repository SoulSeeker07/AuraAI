"""
Unit tests for ProactiveDiagnosticsWatcher (M34)
Location: tests/autonomy/test_proactive_diagnostics.py

Covers:
  - State-change cost gate (short-circuits with 0 tokens when workspace is unchanged)
  - Staging directory retention and pruning (<= 10 directories, <= 24 hours)
  - Non-interrupting FocusManager notification routing (severity="LOW", no focus stealing)
  - Syntax error diagnostic detection
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from autonomy.proactive_diagnostics_watcher import (
    ProactiveDiagnosticsWatcher,
    DiagnosticResult,
)
from core.focus_manager import FocusManager


@pytest.fixture
def watcher(tmp_path):
    FocusManager.reset_instance()
    fm_db = tmp_path / "storage" / "focus_threads.db"
    fm_db.parent.mkdir(parents=True, exist_ok=True)
    fm = FocusManager.get_instance(db_path=fm_db)
    fm.create("task_alpha", {})

    ProactiveDiagnosticsWatcher.reset_instance()
    w = ProactiveDiagnosticsWatcher.get_instance(repo_root=tmp_path)
    yield w, fm
    ProactiveDiagnosticsWatcher.reset_instance()
    FocusManager.reset_instance()


class TestProactiveDiagnosticsWatcher:
    def test_state_change_cost_gate_short_circuits(self, watcher, tmp_path):
        w, fm = watcher

        # Run 1: initial run
        res1 = w.run_diagnostic_cycle(task_id="task_alpha")
        assert res1.status in ("healthy", "syntax_error")

        # Run 2: without modifying any files -> short-circuits (0 tokens)
        res2 = w.run_diagnostic_cycle(task_id="task_alpha")
        assert res2.status == "skipped"
        assert res2.message == "Workspace unchanged"

    def test_syntax_error_enqueues_low_severity_notification(self, watcher, tmp_path):
        w, fm = watcher

        # Create a python file with syntax error in repo root
        broken_file = tmp_path / "broken.py"
        broken_file.write_text("def invalid_syntax(\n", encoding="utf-8")

        # Force diagnostic cycle
        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "broken.py\n"
            mock_res.returncode = 0
            mock_run.return_value = mock_res

            res = w.run_diagnostic_cycle(task_id="task_alpha", force=True)

            assert res.status == "syntax_error"
            assert "Syntax error detected" in res.message

            # Verify notification enqueued into FocusManager without stealing focus
            current = fm.get_current()
            assert current is not None
            assert current.task_id == "task_alpha"

            notifs = fm.drain_pending_notifications()
            assert len(notifs) >= 1
            assert "Syntax error detected" in notifs[0].message
            assert notifs[0].severity == "LOW"

    def test_staging_retention_and_cleanup(self, watcher, tmp_path):
        w, fm = watcher
        staging_dir = tmp_path / ".aura_staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Create 15 dummy staging task directories
        for i in range(15):
            d = staging_dir / f"task_test_{i}"
            d.mkdir(parents=True, exist_ok=True)
            # Set older mtime
            past_time = time.time() - (1000 * (15 - i))
            import os
            os.utime(str(d), (past_time, past_time))

        pruned = w.cleanup_staging_directories()
        assert pruned >= 5  # Pruned down to MAX_STAGING_DIRECTORIES (10)

        remaining = [d for d in staging_dir.iterdir() if d.is_dir()]
        assert len(remaining) <= 10
