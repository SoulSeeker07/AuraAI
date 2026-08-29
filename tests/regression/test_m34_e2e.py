"""
E2E Multi-Turn Regression Tests for Milestone 34
Location: tests/regression/test_m34_e2e.py

Simulates multi-turn workflows verifying:
  - Turn 1: Macro promotion & zero-token execution via preamble
  - Turn 2: UI drift detection falling back cleanly to GroundingEngine
  - Turn 3: Speculative context pre-warming on active window changes
  - Turn 4: Proactive diagnostic notification enqueuing and non-interrupting drain
"""

from unittest.mock import MagicMock, patch
import pytest

from execution.macro_compiler import MacroCompiler, MacroStep
from workspace.speculative_indexer import SpeculativeIndexer
from autonomy.proactive_diagnostics_watcher import ProactiveDiagnosticsWatcher
from routing.app_context_router import AppContext


def _make_mock_groq_response(text: str):
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    res = MagicMock()
    res.choices = [choice]
    return res


@pytest.fixture(scope="function")
def isolated_core(tmp_path):
    from core.aura_core import AuraCore
    from core.focus_manager import FocusManager

    AuraCore.reset_instance()
    FocusManager.reset_instance()
    MacroCompiler.reset_instance()
    SpeculativeIndexer.reset_instance()
    ProactiveDiagnosticsWatcher.reset_instance()

    with (
        patch("groq.Groq") as MockGroq,
        patch.dict("os.environ", {"GROQ_API_KEY": "gsk_testdummykey1234567890"}),
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_groq_response("Acknowledged.")
        MockGroq.return_value = mock_client

        core = AuraCore(config={
            "project_root": str(tmp_path),
            "memory_db_path": str(tmp_path / "Memory.db"),
        })

        fm_db = tmp_path / "storage" / "focus_threads.db"
        fm_db.parent.mkdir(parents=True, exist_ok=True)
        FocusManager.reset_instance()
        core.focus_manager = FocusManager.get_instance(db_path=fm_db)
        core.focus_manager.create("m34_session", {})

        yield core

    AuraCore.reset_instance()
    FocusManager.reset_instance()
    MacroCompiler.reset_instance()
    SpeculativeIndexer.reset_instance()
    ProactiveDiagnosticsWatcher.reset_instance()


class TestM34E2ERegression:
    def test_m34_full_lifecycle(self, isolated_core, tmp_path):
        core = isolated_core
        compiler = core.macro_compiler
        indexer = core.speculative_indexer
        watcher = core.proactive_watcher
        router = core.app_context_router

        # --- Turn 1: Macro Promotion & Zero-Token Fast-Path Execution ---
        steps = [
            MacroStep(
                action_type="click",
                target_signature={"label": "Run Benchmark", "control_type": "Button"},
                fallback_selector="#run_bench",
            )
        ]
        # Record 3 identical traces
        for _ in range(3):
            compiler.record_trace("run benchmark", "code.exe", str(tmp_path), steps, 0.95)

        # Mock active app as code.exe with valid button visible
        code_ctx = AppContext(app_name="code.exe", window_handle=301, window_title="main.py - VS Code")
        mock_page = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_visible.return_value = True
        mock_page.locator.return_value.first = mock_elem
        code_ctx.page = mock_page

        with patch.object(router, "detect_current_app", return_value=code_ctx):
            # Should execute macro with zero tokens
            res = core._vision_dictation_preamble("run benchmark")
            assert "[Executed verified macro" in res
            assert "(0 tokens)" in res

        # --- Turn 2: UI Drift Simulation Falling Back to Grounding ---
        mock_elem.is_visible.return_value = False  # UI element disappeared!
        with (
            patch.object(router, "detect_current_app", return_value=code_ctx),
            patch.object(core.grounding_engine, "resolve", return_value=None),
        ):
            # Should catch MacroDriftError and fall through gracefully
            res_drift = core._vision_dictation_preamble("run benchmark")
            assert "run benchmark" in res_drift

        # --- Turn 3: Speculative Context Pre-warming ---
        sample_code = tmp_path / "app.py"
        sample_code.write_text("def start_server():\n    pass\n", encoding="utf-8")
        indexer._compute_and_cache_context(window_title=f"app.py - {tmp_path.name} - VS Code")

        cached_ctx = indexer.get_prewarmed_context(repo_root=tmp_path)
        assert cached_ctx is not None
        assert cached_ctx.active_file == "app.py"
        assert "start_server" in cached_ctx.ast_functions

        # --- Turn 4: Proactive Diagnostics Notification Routing ---
        broken_code = tmp_path / "syntax_err.py"
        broken_code.write_text("def broken_func(\n", encoding="utf-8")

        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "syntax_err.py\n"
            mock_res.returncode = 0
            mock_run.return_value = mock_res

            diag_res = watcher.run_diagnostic_cycle(task_id="m34_session", force=True)
            assert diag_res.status == "syntax_error"

            # Check FocusManager notifications
            notifs = core.focus_manager.drain_pending_notifications()
            assert len(notifs) >= 1
            assert "Syntax error detected" in notifs[0].message
            assert notifs[0].severity == "LOW"
