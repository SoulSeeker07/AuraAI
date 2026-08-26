"""
Unit tests for ScreenshotManager scoped lifecycle, fail-open preservation,
retention pruning, and unified capture dispatching.
"""

import os
import time
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from vision.screenshot_manager import ScreenshotManager
from vision.models import ScreenshotSettings


@pytest.fixture
def temp_screenshot_dir(tmp_path):
    """Fixture providing isolated temporary screenshot storage directory."""
    d = tmp_path / "runtime" / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_screenshot_scoped_lifecycle_success_deletes_file(temp_screenshot_dir):
    """Verify that a successful capture_scoped block deletes the temporary screenshot."""
    settings = ScreenshotSettings(save_path=str(temp_screenshot_dir))
    sm = ScreenshotManager(settings=settings)

    dummy_img = Image.new("RGB", (100, 100), color="blue")
    with patch.object(sm, "_grab_safe", return_value=dummy_img):
        captured_file = None
        with sm.capture_scoped(capture_type="full_screen") as path:
            captured_file = path
            assert captured_file is not None
            assert Path(captured_file).exists()
            assert Path(captured_file).parent == temp_screenshot_dir

        # After clean exit from with-block, file MUST be deleted
        assert not Path(captured_file).exists()


def test_screenshot_scoped_lifecycle_failure_preserves_file(temp_screenshot_dir):
    """Verify that an exception in the consumer preserves the screenshot for debugging."""
    settings = ScreenshotSettings(save_path=str(temp_screenshot_dir))
    sm = ScreenshotManager(settings=settings)

    dummy_img = Image.new("RGB", (100, 100), color="red")
    captured_file = None

    with patch.object(sm, "_grab_safe", return_value=dummy_img):
        with pytest.raises(ValueError, match="Simulated consumer crash"):
            with sm.capture_scoped(capture_type="full_screen") as path:
                captured_file = path
                assert Path(captured_file).exists()
                raise ValueError("Simulated consumer crash")

        # After exception, file MUST be preserved on disk for visual post-mortem
        assert captured_file is not None
        assert Path(captured_file).exists()


def test_prune_failure_captures_enforces_count_cap(temp_screenshot_dir):
    """Verify _prune_failure_captures enforces max_count cap."""
    settings = ScreenshotSettings(save_path=str(temp_screenshot_dir))
    sm = ScreenshotManager(settings=settings)

    # Create 25 dummy screenshot files
    now = time.time()
    for i in range(25):
        f = temp_screenshot_dir / f"screenshot_test_{i}.png"
        f.write_text("fake_png_data")
        # Stagger mtimes
        os.utime(f, (now - (100 - i) * 10, now - (100 - i) * 10))

    assert len(list(temp_screenshot_dir.glob("*.png"))) == 25

    # Prune with max_count=10
    deleted = sm._prune_failure_captures(max_count=10, max_age_hours=24)
    assert deleted == 15
    remaining = list(temp_screenshot_dir.glob("*.png"))
    assert len(remaining) == 10


def test_prune_failure_captures_enforces_age_cap(temp_screenshot_dir):
    """Verify _prune_failure_captures enforces max_age_hours cap."""
    settings = ScreenshotSettings(save_path=str(temp_screenshot_dir))
    sm = ScreenshotManager(settings=settings)

    now = time.time()
    # 3 recent files (1 hour old)
    for i in range(3):
        f = temp_screenshot_dir / f"screenshot_recent_{i}.png"
        f.write_text("recent_data")
        os.utime(f, (now - 3600, now - 3600))

    # 4 stale files (48 hours old)
    for i in range(4):
        f = temp_screenshot_dir / f"screenshot_stale_{i}.png"
        f.write_text("stale_data")
        os.utime(f, (now - 48 * 3600, now - 48 * 3600))

    assert len(list(temp_screenshot_dir.glob("*.png"))) == 7

    # Prune with max_age_hours=24
    deleted = sm._prune_failure_captures(max_count=20, max_age_hours=24)
    assert deleted == 4
    remaining = list(temp_screenshot_dir.glob("*.png"))
    assert len(remaining) == 3
    assert all("recent" in f.name for f in remaining)


def test_capture_internal_dispatch(temp_screenshot_dir):
    """Verify capture_internal dispatches to specific capture methods."""
    settings = ScreenshotSettings(save_path=str(temp_screenshot_dir))
    sm = ScreenshotManager(settings=settings)

    dummy_img = Image.new("RGB", (100, 100), color="green")
    with patch.object(sm, "_grab_safe", return_value=dummy_img), \
         patch.object(sm, "_get_monitors", return_value=[{"rect": (0, 0, 1920, 1080)}]):
        # 1. Full screen
        p1 = sm.capture_internal(capture_type="full_screen")
        assert "screenshot_full_" in p1
        assert Path(p1).exists()

        # 2. Monitor
        p2 = sm.capture_internal(capture_type="active_monitor", monitor_index=0)
        assert "screenshot_monitor_0_" in p2
        assert Path(p2).exists()

        # 3. Selected region
        p3 = sm.capture_internal(capture_type="region", region=(0, 0, 50, 50))
        assert "screenshot_region_0_0_50_50_" in p3
        assert Path(p3).exists()

        # 4. Active window
        with patch("win32gui.GetForegroundWindow", return_value=1234), \
             patch("win32gui.GetWindowRect", return_value=(10, 10, 800, 600)), \
             patch("win32gui.GetWindowText", return_value="Visual Studio Code"):
            p4 = sm.capture_internal(capture_type="active_window")
            assert "screenshot_window_" in p4
            assert Path(p4).exists()

        # 5. Window by title
        with patch("win32gui.FindWindow", return_value=5678), \
             patch("win32gui.GetWindowRect", return_value=(20, 20, 900, 700)):
            p5 = sm.capture_internal(capture_type="window", window_title="Notepad")
            assert "screenshot_window_" in p5
            assert "Notepad" in p5
            assert Path(p5).exists()
