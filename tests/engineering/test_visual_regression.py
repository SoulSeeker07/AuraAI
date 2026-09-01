"""
Tests for Visual Regression (SSIM) Engine & Multi-Viewport Testing Subsystem
============================================================================
Location: tests/engineering/test_visual_regression.py
"""

import os
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pytest

from engineering.visual_regression import (
    BaselineManager,
    capture_qt_card_reference,
    capture_web_element,
    capture_web_viewports,
    compute_ssim,
    generate_diff_image,
)


def test_ssim_identical_images_scores_1_0():
    img = Image.new("RGB", (200, 100), color=(13, 17, 23))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 180, 80], fill=(22, 28, 40), outline=(0, 229, 255))
    draw.text((30, 30), "Aura Visual Test", fill=(243, 246, 252))

    score = compute_ssim(img, img)
    assert score == 1.0, f"Expected 1.0 for identical image, got {score}"


def test_ssim_detects_layout_and_color_shifts():
    img1 = Image.new("RGB", (200, 100), color=(13, 17, 23))
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([20, 20, 180, 80], fill=(22, 28, 40), outline=(0, 229, 255))

    # Shift position and modify outline color
    img2 = Image.new("RGB", (200, 100), color=(13, 17, 23))
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([25, 25, 185, 85], fill=(22, 28, 40), outline=(244, 63, 94))

    score = compute_ssim(img1, img2)
    assert score < 0.99, f"Expected SSIM drop on layout/color shift, got {score}"
    assert score > 0.40

    diff_img = generate_diff_image(img1, img2)
    assert isinstance(diff_img, Image.Image)
    assert diff_img.size == (200, 100)


def test_multi_viewport_visual_regression():
    project_root = Path(__file__).resolve().parents[2]
    template_path = project_root / "src" / "engineering" / "templates" / "starter_app.html"
    assert template_path.exists()
    html_content = template_path.read_text(encoding="utf-8")

    bm = BaselineManager()
    captures = capture_web_viewports(html_content)

    assert "mobile" in captures
    assert "tablet" in captures
    assert "desktop" in captures

    assert captures["mobile"].size == (375, 812)
    assert captures["tablet"].size == (768, 1024)
    assert captures["desktop"].size == (1440, 900)

    passed, results = bm.verify_captures("starter_app", captures, threshold=0.990)
    assert passed, f"Visual regression detected across viewports: {results}"
    for res in results:
        assert res["passed"]
        assert res["ssim"] >= 0.990


def test_cross_platform_qt_web_parity():
    project_root = Path(__file__).resolve().parents[2]
    parity_template = project_root / "src" / "engineering" / "templates" / "components" / "card_parity.html"
    assert parity_template.exists()

    qt_img = capture_qt_card_reference()
    web_img = capture_web_element(parity_template.read_text(encoding="utf-8"), selector="#card-parity")

    qt_resized = qt_img.resize((400, 180))
    web_resized = web_img.resize((400, 180))

    score = compute_ssim(qt_resized, web_resized)
    
    # In native GUI mode, DirectWrite parity achieves >= 0.850 (0.9254 measured).
    # In headless offscreen QPA mode (QT_QPA_PLATFORM=offscreen), FreeType fallback achieves >= 0.650 (0.6802 measured).
    is_offscreen = os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    expected_threshold = 0.650 if is_offscreen else 0.850
    assert score >= expected_threshold, (
        f"Expected cross-platform parity SSIM >= {expected_threshold} "
        f"(mode={'offscreen' if is_offscreen else 'native'}), got {score:.4f}"
    )


def test_token_hash_invalidation_flag():
    bm = BaselineManager()
    manifest = bm.load_manifest()
    token_hash = bm.get_token_hash()

    assert len(token_hash) == 16
    assert manifest.get("token_hash") == token_hash
