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


class TestVLMAndCoordinateMapping:
    def test_translate_to_screen_coordinates(self):
        from vision.grounding_engine import translate_to_screen_coordinates

        # 1. Base translation (physical to physical)
        assert translate_to_screen_coordinates((100, 200)) == (100, 200)

        # 2. Window bounds translation (physical window offset)
        bounds = (300, 150, 900, 750)
        assert translate_to_screen_coordinates((50, 60), window_bounds=bounds) == (350, 210)

        # 3. Logical DOM DPI scaling (e.g. 1.25 scaling on logical CSS units)
        assert translate_to_screen_coordinates((100, 100), dpi_scale=1.25, source_is_logical=True) == (125, 125)

        # 4. VLM downsampling reversal (e.g. 1920 -> 1280 downscale reversed: 640 / (1280/1920) = 960)
        assert translate_to_screen_coordinates((640, 360), vlm_scale_factor=1280 / 1920) == (960, 540)

        # 5. Proof against double-scaling: VLM source ignores dpi_scale even if passed
        assert translate_to_screen_coordinates(
            (500, 350),
            window_bounds=(200, 100, 1200, 800),
            dpi_scale=1.25,
            source_is_logical=False,
            vlm_scale_factor=1.0,
        ) == (700, 450)

    def test_tier2_vlm_fallback(self, engine):
        from PIL import Image

        # Mock Image
        dummy_img = Image.new("RGB", (640, 480), color=(50, 50, 50))

        # Mock Groq response
        mock_choice = MagicMock()
        mock_choice.message.content = (
            '{"found": true, "center": [250, 180], "bbox": [200, 160, 300, 200], '
            '"label": "Play Video", "confidence": 0.92}'
        )
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        mock_provider = MagicMock()
        mock_provider.vision_model = "qwen/qwen3.6-27b"
        mock_provider._get_client.return_value = mock_client

        with (
            patch.object(engine, "_resolve_tier1_a11y_or_dom", return_value=None),
            patch("desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance") as mock_reg,
            patch("ai.groq_provider.GroqProvider", return_value=mock_provider),
        ):
            # Make OCR return low confidence / no match
            mock_screen_mgr = MagicMock()
            mock_screen_mgr.execute.return_value = MagicMock(success=False)
            mock_reg.return_value.get_manager.return_value = mock_screen_mgr

            app_ctx = MagicMock()
            app_ctx.app_name = "chrome.exe"
            app_ctx.bounds = (100, 50, 740, 530)

            target = engine.resolve("Play Video", app_context=app_ctx, screen_image=dummy_img)
            assert target is not None
            assert target.label == "Play Video"
            assert target.source_tier == "tier2_vision"
            # 250 + window_bounds.left(100) = 350, 180 + window_bounds.top(50) = 230
            assert target.center == (350, 230)
            assert target.confidence == 0.92

    def test_tier2_vlm_out_of_bounds_rejected(self, engine):
        from PIL import Image

        dummy_img = Image.new("RGB", (640, 480), color=(50, 50, 50))

        # Mock Groq response returning out-of-bounds coordinates (1500, 300 on 640x480)
        mock_choice = MagicMock()
        mock_choice.message.content = (
            '{"found": true, "center": [1500, 300], "bbox": [1400, 280, 1600, 320], '
            '"label": "Offscreen Element", "confidence": 0.95}'
        )
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_provider = MagicMock()
        mock_provider.vision_model = "qwen/qwen3.6-27b"
        mock_provider._get_client.return_value = mock_client

        with patch("ai.groq_provider.GroqProvider", return_value=mock_provider):
            app_ctx = MagicMock()
            app_ctx.bounds = (0, 0, 640, 480)
            res = engine._resolve_tier2_vlm("Offscreen Element", app_ctx, screen_image=dummy_img)
            # Must strictly reject out-of-bounds predictions
            assert res is None

    def test_resolve_target_app_override(self, engine):
        with patch.object(engine, "_resolve_tier1_a11y_or_dom") as mock_tier1:
            mock_tier1.return_value = MagicMock(confidence=0.90, label="Search Box", center=(100, 200))
            target = engine.resolve("Search Box", target_app="spotify.exe")
            assert target is not None
            mock_tier1.assert_called_once()
            called_ctx = mock_tier1.call_args[0][1]
            assert called_ctx.app_name == "spotify.exe"

    def test_tier2_vlm_keypool_failover_on_429(self, engine):
        from PIL import Image
        import groq
        from ai.key_pool import KeyPool

        dummy_img = Image.new("RGB", (640, 480), color=(50, 50, 50))
        app_ctx = MagicMock()
        app_ctx.bounds = (0, 0, 640, 480)

        attempt_keys = []

        def make_mock_create(key):
            def _create(**kwargs):
                attempt_keys.append(key)
                if key == "k1":
                    mock_resp = MagicMock(status_code=429, headers={"retry-after": "5"})
                    raise groq.RateLimitError(
                        message="TPM limit exceeded",
                        response=mock_resp,
                        body={"error": {"message": "TPM limit exceeded", "code": 429}},
                    )
                elif key == "k2":
                    mock_choice = MagicMock()
                    mock_choice.message.content = (
                        '{"found": true, "center": [300, 200], "bbox": [250, 180, 350, 220], '
                        '"label": "Submit", "confidence": 0.93}'
                    )
                    return MagicMock(choices=[mock_choice])
                raise ValueError(f"Unexpected key: {key}")
            return _create

        pool = KeyPool.get_instance()
        pool._keys["groq"] = ["k1", "k2"]
        pool._cooldowns.clear()
        pool._key_indices["groq"] = 0

        with patch("groq.Groq") as mock_groq_class:
            mock_groq_class.side_effect = lambda api_key=None: MagicMock(
                chat=MagicMock(completions=MagicMock(create=make_mock_create(api_key)))
            )
            target = engine._resolve_tier2_vlm("Submit", app_ctx, screen_image=dummy_img)

        assert attempt_keys == ["k1", "k2"]
        assert target is not None
        assert target.label == "Submit"
        assert target.center == (300, 200)
