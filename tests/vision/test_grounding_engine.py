"""
Unit tests for GroundingEngine (M33)
Location: tests/vision/test_grounding_engine.py

Covers:
  - GroundedTarget creation and dictionary serialization
  - Tier 1: DOM / Playwright resolution
  - Tier 1: UIA / Accessibility tree resolution
  - Tier 2: OCR / Screen action fallback
  - Tier 3: Fail-Closed on low confidence (< 0.75)
  - Composite confidence ranking formula reuse
"""

from unittest.mock import MagicMock, patch
import pytest

from vision.grounding_engine import GroundingEngine, GroundedTarget, MIN_GROUNDING_CONFIDENCE


@pytest.fixture
def engine():
    GroundingEngine.reset_instance()
    eng = GroundingEngine.get_instance()
    yield eng
    GroundingEngine.reset_instance()


class TestGroundedTarget:
    def test_dataclass_fields(self):
        target = GroundedTarget(
            label="Submit Button",
            center=(100, 200),
            bbox=(80, 190, 120, 210),
            confidence=0.92,
            source_tier="tier1_a11y",
            app_name="explorer.exe",
        )
        assert target.label == "Submit Button"
        assert target.center == (100, 200)
        assert target.confidence == 0.92
        assert target.source_tier == "tier1_a11y"
        d = target.to_dict()
        assert d["label"] == "Submit Button"
        assert d["center"] == (100, 200)


class TestTier1Resolution:
    def test_playwright_dom_resolution(self, engine):
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_element.is_visible.return_value = True
        mock_element.bounding_box.return_value = {"x": 50, "y": 60, "width": 100, "height": 40}
        mock_page.locator.return_value.first = mock_element

        app_context = MagicMock()
        app_context.app_name = "chrome.exe"
        app_context.page = mock_page

        target = engine.resolve("Search Input", app_context=app_context)
        assert target is not None
        assert target.label == "Search Input"
        assert target.source_tier == "tier1_dom"
        assert target.center == (100, 80)
        assert target.confidence >= MIN_GROUNDING_CONFIDENCE

    def test_uia_accessibility_resolution(self, engine):
        mock_elem = MagicMock()
        mock_elem.name = "Downloads"
        mock_elem.bounding_box = MagicMock(left=20, top=30, right=120, bottom=70, width=100, height=40)

        with patch("desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance") as mock_reg:
            mock_mgr = MagicMock()
            mock_adapter = MagicMock()
            mock_adapter.is_available.return_value = True
            mock_adapter.find_elements.return_value = [mock_elem]
            mock_mgr.adapter = mock_adapter
            mock_reg.return_value.get_manager.return_value = mock_mgr

            app_context = MagicMock()
            app_context.app_name = "explorer.exe"
            app_context.page = None

            target = engine.resolve("Downloads", app_context=app_context)
            assert target is not None
            assert target.label == "Downloads"
            assert target.source_tier == "tier1_a11y"
            assert target.center == (70, 50)
            assert target.confidence >= MIN_GROUNDING_CONFIDENCE


class TestTier2AndTier3Resolution:
    def test_tier2_ocr_fallback(self, engine):
        with (
            patch("desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance") as mock_reg,
            patch.object(engine, "_resolve_tier1_a11y_or_dom", return_value=None),
        ):
            mock_screen_mgr = MagicMock()
            mock_res = MagicMock()
            mock_res.success = True
            mock_res.data = {"coordinates": {"x": 400, "y": 300, "confidence": 0.88}}
            mock_screen_mgr.execute.return_value = mock_res
            mock_reg.return_value.get_manager.return_value = mock_screen_mgr

            app_context = MagicMock()
            app_context.app_name = "code.exe"

            target = engine.resolve("test_runner.py", app_context=app_context)
            assert target is not None
            assert target.label == "test_runner.py"
            assert target.source_tier == "tier2_vision"
            assert target.center == (400, 300)
            assert target.confidence == 0.88

    def test_tier3_fail_closed_on_low_confidence(self, engine):
        with (
            patch.object(engine, "_resolve_tier1_a11y_or_dom", return_value=None),
            patch.object(engine, "_resolve_tier2_vision", return_value=None),
        ):
            app_context = MagicMock()
            app_context.app_name = "explorer.exe"

            target = engine.resolve("non_existent_element", app_context=app_context)
            assert target is None


class TestCompositeRankingScore:
    def test_ranking_formula_behavior(self, engine):
        # Perfect distance (0.0) with 1.0 confidence -> 1.0
        assert engine.compute_composite_score(0.0, 1.0) == 1.0

        # Close distance (1.0) with 0.8 confidence -> 0.4
        score = engine.compute_composite_score(1.0, 0.8)
        assert abs(score - 0.4) < 1e-4

        # Farther distance gets discounted properly
        score_far = engine.compute_composite_score(3.0, 0.8)
        assert score_far < score
