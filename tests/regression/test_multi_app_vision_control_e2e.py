"""
Multi-App Vision-Grounded Control System — End-to-End Regression Test Suite
Location: tests/regression/test_multi_app_vision_control_e2e.py

Verifies:
  - Turn 1: Grounding target in source application (Explorer)
  - Turn 2: Automatic app-switch decay preserves transferable target in CrossAppTransferRegister
  - Turn 3: Cross-app referential resolution in destination app ("upload that file" in Chrome)
  - Turn 4: Tier 2 Multimodal VLM grounding fallback for visual elements
  - Turn 5: Cross-app dependency graph resolution (automatic window.switch_to + wait_for_change)
"""

from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from core.visual_memory import VisualWorkingMemory
from routing.app_context_router import AppContext, AppContextRouter
from vision.grounding_engine import GroundedTarget, GroundingEngine
from desktop.planner.dependency_resolver import DependencyResolver
from desktop.planner.desktop_goal import DesktopGoal
from desktop.planner.desktop_step import StepType
from desktop.native.desktop_context import DesktopContext


def _make_mock_groq_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.fixture(scope="function")
def clean_system(tmp_path):
    from core.aura_core import AuraCore
    from core.focus_manager import FocusManager

    AuraCore.reset_instance()
    FocusManager.reset_instance()
    GroundingEngine.reset_instance()
    VisualWorkingMemory.reset_instance()
    AppContextRouter.reset_instance()

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
        core.focus_manager.create("multi_app_session", {})

        yield core

    AuraCore.reset_instance()
    FocusManager.reset_instance()
    GroundingEngine.reset_instance()
    VisualWorkingMemory.reset_instance()
    AppContextRouter.reset_instance()


class TestMultiAppVisionControlE2E:
    def test_multi_app_workflow_lifecycle(self, clean_system):
        core = clean_system
        vm = core.visual_memory
        engine = core.grounding_engine
        router = core.app_context_router

        # =========================================================================
        # Turn 1: Explorer Context — Ground & Remember "data_report.xlsx"
        # =========================================================================
        exp_ctx = AppContext(
            app_name="explorer.exe",
            window_handle=1001,
            window_title="D:\\Financial_Reports",
            bounds=(0, 0, 1920, 1080),
        )

        mock_elem = MagicMock()
        mock_elem.name = "data_report.xlsx"
        mock_elem.bounding_box = MagicMock(left=150, top=200, right=350, bottom=240, width=200, height=40)

        with (
            patch.object(router, "detect_current_app", return_value=exp_ctx),
            patch("desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance") as mock_reg,
        ):
            mock_uia = MagicMock()
            mock_adapter = MagicMock()
            mock_adapter.is_available.return_value = True
            mock_adapter.find_elements.return_value = [mock_elem]
            mock_uia.adapter = mock_adapter
            mock_reg.return_value.get_manager.return_value = mock_uia

            # User says "open data_report.xlsx"
            res_t1 = core._vision_dictation_preamble("open data_report.xlsx")
            assert "data_report.xlsx" in res_t1
            assert "tier1_a11y" in res_t1

        # Verify remembered in visual memory and cross-app transfer slot
        x_slot = vm.get_cross_app_transfer(task_id="multi_app_session")
        assert x_slot is not None
        assert x_slot.label == "data_report.xlsx"
        assert x_slot.metadata.get("origin_app") == "explorer.exe"

        # =========================================================================
        # Turn 2: Switch to Chrome — Decay applied, Cross-app transfer preserved
        # =========================================================================
        chrome_ctx = AppContext(
            app_name="chrome.exe",
            window_handle=2002,
            window_title="Dropbox File Upload - Google Chrome",
            is_browser=True,
            bounds=(100, 50, 1500, 950),
        )

        with patch.object(router, "detect_current_app", return_value=chrome_ctx):
            # Pure navigation fast-path executed in Chrome
            res_nav = core._vision_dictation_preamble("scroll down")
            assert res_nav == "scroll down"

        # Verify Explorer intra-app targets are not leaked for direct "open that file"
        assert vm.resolve_reference("open that file", task_id="multi_app_session", current_app="chrome.exe")[0] is None

        # But cross-app transfer slot still holds data_report.xlsx!
        assert vm.get_cross_app_transfer(task_id="multi_app_session").label == "data_report.xlsx"

        # =========================================================================
        # Turn 3: "upload that file" in Chrome — Cross-App Transfer Resolution
        # =========================================================================
        with patch.object(router, "detect_current_app", return_value=chrome_ctx):
            res_t3 = core._vision_dictation_preamble("upload that file")
            assert "data_report.xlsx" in res_t3
            assert "transfer: cross_app" in res_t3
            assert "from explorer.exe" in res_t3

        # =========================================================================
        # Turn 4: Tier 2 Multimodal VLM Grounding Fallback in Chrome
        # =========================================================================
        dummy_screenshot = Image.new("RGB", (1200, 800), color=(240, 240, 240))
        mock_vlm_json = (
            '{"found": true, "center": [700, 450], "bbox": [650, 430, 750, 470], '
            '"label": "Upload Document", "confidence": 0.94}'
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_groq_response(mock_vlm_json)
        mock_provider = MagicMock()
        mock_provider.vision_model = "qwen/qwen3.6-27b"
        mock_provider._get_client.return_value = mock_client

        with (
            patch.object(engine, "_resolve_tier1_a11y_or_dom", return_value=None),
            patch("desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance") as mock_reg,
            patch("ai.groq_provider.GroqProvider", return_value=mock_provider),
        ):
            # OCR fails or misses icon
            mock_screen_mgr = MagicMock()
            mock_screen_mgr.execute.return_value = MagicMock(success=False)
            mock_reg.return_value.get_manager.return_value = mock_screen_mgr

            target = engine.resolve("Upload Document", app_context=chrome_ctx, screen_image=dummy_screenshot)
            assert target is not None
            assert target.label == "Upload Document"
            assert target.source_tier == "tier2_vision"
            assert target.confidence == 0.94
            # 700 + chrome_ctx.bounds[0](100) = 800, 450 + chrome_ctx.bounds[1](50) = 500
            assert target.center == (800, 500)

        # =========================================================================
        # Turn 5: Cross-App Plan Generation with Automatic Window Activation
        # =========================================================================
        resolver = DependencyResolver()
        mock_context = MagicMock(spec=DesktopContext)
        mock_active = MagicMock()
        mock_active.app_name = "code.exe"
        mock_context.active_window = mock_active
        resolver.context = mock_context

        # User goal: "in Chrome, click search"
        goal = DesktopGoal(goal="in Chrome, click search")
        plan = resolver.resolve_plan(goal, "input.click")

        # Must have chained window.switch_to and screen.wait_for_change before input.click!
        step_caps = [s.capability for s in plan.steps]
        assert "window.switch_to" in step_caps
        assert "screen.wait_for_change" in step_caps
        assert "input.click" in step_caps

        switch_idx = step_caps.index("window.switch_to")
        wait_idx = step_caps.index("screen.wait_for_change")
        click_idx = step_caps.index("input.click")

        assert switch_idx < wait_idx < click_idx
        assert plan.steps[switch_idx].arguments.get("app_name") == "chrome.exe"
