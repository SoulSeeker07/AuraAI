"""
Integration tests for Vision System

Tests the complete Vision System pipeline including:
- Screenshot capture
- Image loading
- Object detection
- Layout analysis
- UI analysis
- Diagram analysis
- Code detection
"""


import pytest
import cv2
import numpy as np
import tempfile
import os
from pathlib import Path

# Import vision system modules
from src.vision.vision_manager import VisionManager
from src.vision.models import (
    VisionContext, ImageType, VisionProvider,
    ScreenshotSettings, OCRSettings
)


@pytest.fixture
def vision_manager():
    """Create a VisionManager instance for testing."""
    screenshot_settings = ScreenshotSettings()
    ocr_settings = OCRSettings()
    return VisionManager(screenshot_settings, ocr_settings)


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a sample test image."""
    # Create a simple test image
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255

    # Draw some shapes
    cv2.rectangle(img, (100, 100), (200, 200), (255, 0, 0), -1)  # Blue rectangle
    cv2.circle(img, (400, 400), 50, (0, 255, 0), -1)  # Green circle
    cv2.line(img, (50, 500), (550, 500), (0, 0, 255), 5)  # Red line

    # Save to temporary file
    img_path = tmp_path / "test_image.png"
    cv2.imwrite(str(img_path), img)

    return str(img_path)


def test_vision_manager_initialization(vision_manager):
    """Test VisionManager initialization."""
    assert vision_manager is not None
    assert vision_manager.screenshot_manager is not None
    assert vision_manager.image_loader is not None
    assert vision_manager.object_detector is not None
    assert vision_manager.layout_analyzer is not None
    assert vision_manager.ui_analyzer is not None
    assert vision_manager.diagram_analyzer is not None
    assert vision_manager.code_detector is not None
    assert vision_manager.coordinator is not None


def test_vision_manager_last_image_path(vision_manager):
    """Test getting last image path."""
    assert vision_manager.get_last_image_path() is None


def test_vision_manager_last_context(vision_manager):
    """Test getting last context."""
    assert vision_manager.get_last_context() is None


def test_vision_manager_context_info(vision_manager):
    """Test getting context info."""
    info = vision_manager.get_context_info()
    assert info is not None
    assert 'image_type' in info


def test_vision_manager_configure_screenshot(vision_manager):
    """Test configuring screenshot settings."""
    vision_manager.configure_screenshot(
        capture_type='active_window',
        include_cursor=True,
        include_timestamp=True
    )

    assert vision_manager.screenshot_settings.capture_type == 'active_window'
    assert vision_manager.screenshot_settings.include_cursor is True
    assert vision_manager.screenshot_settings.include_timestamp is True


def test_vision_manager_configure_ocr(vision_manager):
    """Test configuring OCR settings."""
    vision_manager.configure_ocr(
        provider=VisionProvider.OPENAI,
        language='eng',
        confidence_threshold=0.8
    )

    assert vision_manager.ocr_settings.provider == VisionProvider.OPENAI
    assert vision_manager.ocr_settings.language == 'eng'


def test_vision_manager_enable_feature(vision_manager):
    """Test enabling/disabling features."""
    vision_manager.enable_feature('auto_rotate', enabled=True)
    vision_manager.enable_feature('deskew', enabled=True)

    assert vision_manager.ocr_settings.auto_rotate is True
    assert vision_manager.ocr_settings.deskew is True


def test_analyze_image(vision_manager, sample_image_path):
    """Test analyzing an existing image."""
    context = vision_manager.analyze_image(sample_image_path)

    assert context is not None
    assert context.image_path is not None
    assert context.image_width > 0
    assert context.image_height > 0


def test_analyze_image_with_type(vision_manager, sample_image_path):
    """Test analyzing image with specified type."""
    context = vision_manager.analyze_image(sample_image_path, ImageType.SCREENSHOT)

    assert context is not None
    assert context.image_type == ImageType.SCREENSHOT


def test_vision_context_creation(vision_manager):
    """Test creating a VisionContext."""
    context = vision_manager.coordinator.create_context(
        image_path="test.png",
        image_type=ImageType.SCREENSHOT,
        image_width=800,
        image_height=600
    )

    assert context is not None
    assert context.image_path == "test.png"
    assert context.image_type == ImageType.SCREENSHOT


def test_vision_context_update_summary(vision_manager):
    """Test updating context summary."""
    context = vision_manager.coordinator.create_context(
        image_path="test.png",
        image_type=ImageType.SCREENSHOT,
        image_width=800,
        image_height=600
    )

    context = vision_manager.coordinator.update_with_summary(
        context,
        "Test summary",
        "Test description"
    )

    assert context.summary is not None
    assert "Test summary" in context.summary


def test_vision_context_finalize(vision_manager):
    """Test finalizing a vision context."""
    context = vision_manager.coordinator.create_context(
        image_path="test.png",
        image_type=ImageType.SCREENSHOT,
        image_width=800,
        image_height=600
    )

    vision_manager.coordinator.update_with_summary(
        context,
        "Test summary",
        "Test description"
    )

    finalized_context = vision_manager.coordinator.finalize_context(context)

    assert finalized_context is not None
    assert finalized_context.image_path == "test.png"


def test_vision_manager_last_context_after_analysis(vision_manager, sample_image_path):
    """Test that last context is updated after analysis."""
    context = vision_manager.analyze_image(sample_image_path)

    last_context = vision_manager.get_last_context()
    assert last_context is not None
    assert last_context['image_path'] == sample_image_path


def test_vision_manager_last_image_path_after_analysis(vision_manager, sample_image_path):
    """Test that last image path is updated after analysis."""
    vision_manager.analyze_image(sample_image_path)

    last_path = vision_manager.get_last_image_path()
    assert last_path is not None
    assert last_path == sample_image_path


def test_vision_manager_get_context_info_after_analysis(vision_manager, sample_image_path):
    """Test that context info is updated after analysis."""
    vision_manager.analyze_image(sample_image_path)

    info = vision_manager.get_context_info()
    assert info is not None
    assert 'image_type' in info
    assert 'image_width' in info
    assert 'image_height' in info


def test_object_detector_detection(vision_manager):
    """Test object detection."""
    # Create a simple test image
    img = np.ones((600, 400, 3), dtype=np.uint8) * 255

    # Draw some objects
    cv2.rectangle(img, (50, 50), (150, 150), (255, 0, 0), -1)
    cv2.circle(img, (300, 200), 40, (0, 255, 0), -1)

    result = vision_manager.object_detector.detect_objects(img, ImageType.SCREENSHOT)

    assert result is not None
    assert 'detected_objects' in result
    assert 'bounding_boxes' in result


def test_layout_analyzer_detection(vision_manager):
    """Test layout analysis."""
    # Create a simple test image
    img = np.ones((600, 400, 3), dtype=np.uint8) * 255

    result = vision_manager.layout_analyzer.analyze_layout(img, ImageType.SCREENSHOT)

    assert result is not None
    assert 'layout' in result
    assert 'elements' in result


def test_ui_analyzer_detection(vision_manager):
    """Test UI analysis."""
    # Create a simple test image
    img = np.ones((600, 400, 3), dtype=np.uint8) * 255

    result = vision_manager.ui_analyzer.analyze_ui(img, ImageType.SCREENSHOT)

    assert result is not None
    assert 'buttons' in result
    assert 'menus' in result


def test_diagram_analyzer_detection(vision_manager):
    """Test diagram analysis."""
    # Create a simple test image
    img = np.ones((600, 400, 3), dtype=np.uint8) * 255

    result = vision_manager.diagram_analyzer.analyze_diagram(img, ImageType.DIAGRAM)

    assert result is not None
    assert 'nodes' in result
    assert 'connections' in result


def test_code_detector_detection(vision_manager):
    """Test code detection."""
    # Create a simple test image with code-like patterns
    img = np.ones((400, 300, 3), dtype=np.uint8) * 240  # Light background

    result = vision_manager.code_detector.detect_code(img, ImageType.CODE)

    assert result is not None
    assert 'language' in result
    assert 'lines' in result


def test_vision_context_types():
    """Test that VisionContext has all expected fields."""
    from src.vision.models import VisionContext

    # Create a minimal context
    context = VisionContext(
        image_path="test.png",
        image_type=ImageType.SCREENSHOT,
        image_width=800,
        image_height=600
    )

    # Check that all expected fields exist
    expected_fields = [
        'image_path', 'image_type', 'image_width', 'image_height',
        'detected_text', 'objects', 'bounding_boxes', 'layout',
        'elements', 'sections', 'tables', 'code_snippets',
        'diagrams', 'summary', 'analysis', 'description',
        'buttons', 'menus', 'dialogs', 'forms', 'notifications',
        'network_devices', 'network_connections', 'ip_addresses',
        'vlan_ids', 'interface_names', 'errors_detected',
        'warnings', 'metadata'
    ]

    for field in expected_fields:
        assert hasattr(context, field), f"Missing field: {field}"


def test_screenshot_settings_creation():
    """Test creating ScreenshotSettings."""
    settings = ScreenshotSettings(
        capture_type='full_screen',
        monitor_index=1,
        selected_region=(100, 100, 500, 500),
        format='png',
        quality=95,
        include_cursor=True,
        include_timestamp=True,
        save_path='output'
    )

    assert settings.capture_type == 'full_screen'
    assert settings.monitor_index == 1
    assert settings.include_cursor is True


def test_ocr_settings_creation():
    """Test creating OCRSettings."""
    settings = OCRSettings(
        provider=VisionProvider.OPENAI,
        language='eng',
        table_detection=True,
        code_detection=True,
        diagram_detection=True,
        auto_rotate=True,
        deskew=True,
        confidence_threshold=0.8
    )

    assert settings.provider == VisionProvider.OPENAI
    assert settings.table_detection is True


@pytest.mark.skip(reason="Requires actual screenshot capture")
def test_capture_and_analyze_full_screen(vision_manager):
    """Test full screen capture and analysis."""
    context = vision_manager.capture_and_analyze()

    assert context is not None
    assert context.image_path is not None
    assert context.image_width > 0
    assert context.image_height > 0


@pytest.mark.skip(reason="Requires active window capture")
def test_capture_active_window_and_analyze(vision_manager):
    """Test active window capture and analysis."""
    context = vision_manager.capture_active_window_and_analyze()

    assert context is not None
    assert context.image_path is not None


def test_vision_provider_enum():
    """Test VisionProvider enum values."""
    assert VisionProvider.LOCAL_OCR == "local_ocr"
    assert VisionProvider.OPENAI == "openai"
    assert VisionProvider.GEMINI == "gemini"


def test_image_type_enum():
    """Test ImageType enum values."""
    assert ImageType.SCREENSHOT == "screenshot"
    assert ImageType.DOCUMENT == "document"
    assert ImageType.DIAGRAM == "diagram"
    assert ImageType.CODE == "code"
    assert ImageType.UI == "ui"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
