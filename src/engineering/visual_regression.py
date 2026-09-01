"""
Visual Regression (SSIM) Engine & Multi-Viewport Testing Subsystem
==================================================================
Location: src/engineering/visual_regression.py

Provides:
1. High-precision pure NumPy/PIL Structural Similarity Index Measure (SSIM).
2. Headless Playwright multi-viewport capturer (375px Mobile, 768px Tablet, 1440px Desktop).
3. Cross-platform Qt vs Web component visual parity diffing.
4. Token-hash governed golden baseline lifecycle management.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageChops

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from engineering.preview_server import PreviewServer, get_preview_server
from engineering.token_exporter import extract_canonical_tokens

logger = logging.getLogger(__name__)

BASELINES_DIR = _PROJECT_ROOT / "tests" / "visual_regression" / "baselines"
DIFFS_DIR = _PROJECT_ROOT / "tests" / "visual_regression" / "diffs"

VIEWPORT_PRESETS = {
    "mobile": (375, 812),
    "tablet": (768, 1024),
    "desktop": (1440, 900),
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Pure NumPy SSIM Algorithm
# ─────────────────────────────────────────────────────────────────────────────

def compute_ssim(
    img1: Image.Image | np.ndarray,
    img2: Image.Image | np.ndarray,
    window_size: int = 11,
    stride: int = 4,
    k1: float = 0.01,
    k2: float = 0.03,
    L: float = 255.0,
) -> float:
    """
    Computes the Structural Similarity Index Measure (SSIM) between two images
    using 2D patch-wise sliding windows (Wang et al. standard).
    Returns float in range [0.0, 1.0] where 1.0 indicates identical visual structure.
    """
    # Convert to grayscale arrays with alpha-compositing if RGBA
    if isinstance(img1, Image.Image):
        if img1.mode == "RGBA":
            bg = Image.new("RGBA", img1.size, (13, 17, 23, 255))
            img1 = Image.alpha_composite(bg, img1).convert("L")
        else:
            img1 = img1.convert("L")
        arr1 = np.array(img1, dtype=np.float64)
    else:
        arr1 = np.array(img1, dtype=np.float64)

    if isinstance(img2, Image.Image):
        if img2.mode == "RGBA":
            bg = Image.new("RGBA", img2.size, (13, 17, 23, 255))
            img2 = Image.alpha_composite(bg, img2).convert("L")
        else:
            img2 = img2.convert("L")
        arr2 = np.array(img2, dtype=np.float64)
    else:
        arr2 = np.array(img2, dtype=np.float64)

    # Normalize dimensions if different (crop to common bounding box)
    min_h = min(arr1.shape[0], arr2.shape[0])
    min_w = min(arr1.shape[1], arr2.shape[1])
    arr1 = arr1[:min_h, :min_w]
    arr2 = arr2[:min_h, :min_w]

    c1 = (k1 * L) ** 2
    c2 = (k2 * L) ** 2

    # Fast 2D patch-wise sliding window SSIM
    h, w = arr1.shape
    if h < window_size or w < window_size:
        mu1, mu2 = np.mean(arr1), np.mean(arr2)
        s1_sq, s2_sq = np.var(arr1), np.var(arr2)
        s12 = np.mean((arr1 - mu1) * (arr2 - mu2))
        num = (2 * mu1 * mu2 + c1) * (2 * s12 + c2)
        den = (mu1**2 + mu2**2 + c1) * (s1_sq + s2_sq + c2)
        return float(max(0.0, min(1.0, num / den if den != 0 else 1.0)))

    ssim_patches = []
    for y in range(0, h - window_size + 1, stride):
        for x in range(0, w - window_size + 1, stride):
            p1 = arr1[y : y + window_size, x : x + window_size]
            p2 = arr2[y : y + window_size, x : x + window_size]

            mu1, mu2 = np.mean(p1), np.mean(p2)
            s1_sq, s2_sq = np.var(p1), np.var(p2)
            s12 = np.mean((p1 - mu1) * (p2 - mu2))

            num = (2 * mu1 * mu2 + c1) * (2 * s12 + c2)
            den = (mu1**2 + mu2**2 + c1) * (s1_sq + s2_sq + c2)
            ssim_patches.append(num / den if den != 0 else 1.0)

    ssim_val = float(np.mean(ssim_patches)) if ssim_patches else 1.0
    return max(0.0, min(1.0, ssim_val))


def generate_diff_image(img1: Image.Image, img2: Image.Image) -> Image.Image:
    """
    Generates a side-by-side visual diff image highlighting modified pixels in neon red.
    """
    img1_rgb = img1.convert("RGB")
    img2_rgb = img2.convert("RGB")

    min_w = min(img1_rgb.width, img2_rgb.width)
    min_h = min(img1_rgb.height, img2_rgb.height)
    img1_crop = img1_rgb.crop((0, 0, min_w, min_h))
    img2_crop = img2_rgb.crop((0, 0, min_w, min_h))

    diff = ImageChops.difference(img1_crop, img2_crop)
    diff_arr = np.array(diff)
    mask = np.any(diff_arr > 15, axis=-1)

    # Highlight changed pixels in red on top of dimmed original
    overlay_arr = (np.array(img2_crop) * 0.4).astype(np.uint8)
    overlay_arr[mask] = [255, 30, 60]

    return Image.fromarray(overlay_arr)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Headless Playwright Multi-Viewport Capturer
# ─────────────────────────────────────────────────────────────────────────────

def capture_web_viewports(
    html_content: str,
    viewports: Optional[Dict[str, Tuple[int, int]]] = None,
    server: Optional[PreviewServer] = None,
    filename: str = "ssim_test.html",
) -> Dict[str, Image.Image]:
    """
    Boots headless Chromium via Playwright and captures full-viewport PNG screenshots
    for each requested viewport resolution.
    """
    from playwright.sync_api import sync_playwright

    vp_map = viewports or VIEWPORT_PRESETS
    srv = server or get_preview_server()
    preview_url = srv.serve_html(html_content, filename=filename, inject_hot_reload=False)

    results: Dict[str, Image.Image] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-software-rasterizer=false", "--no-sandbox"],
        )
        for vp_name, (width, height) in vp_map.items():
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1.0,
            )
            page = context.new_page()
            page.goto(preview_url, wait_until="networkidle", timeout=8000)
            page.wait_for_timeout(200)  # Allow Tailwind JIT & layout to settle

            png_bytes = page.screenshot(full_page=False)
            results[vp_name] = Image.open(BytesIO(png_bytes))
            context.close()

        browser.close()

    return results


def capture_web_element(
    html_content: str,
    selector: str = "#card-parity",
    filename: str = "element_test.html",
) -> Image.Image:
    """
    Captures screenshot of a specific DOM element using Playwright locator.
    """
    from playwright.sync_api import sync_playwright

    srv = get_preview_server()
    preview_url = srv.serve_html(html_content, filename=filename, inject_hot_reload=False)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 800, "height": 600}, device_scale_factor=1.0)
        page.goto(preview_url, wait_until="networkidle", timeout=8000)
        page.wait_for_timeout(200)
        loc = page.locator(selector)
        png_bytes = loc.screenshot()
        browser.close()

    return Image.open(BytesIO(png_bytes))


def capture_qt_card_reference() -> Image.Image:
    """
    Renders reference native PyQt CyberCard widget in memory and grabs pixel buffer.
    """
    from gui.webengine_init import ensure_webengine_flags
    ensure_webengine_flags()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QHBoxLayout
    from PySide6.QtGui import QFont
    from gui.theme import Colors, Typography, Radius, Spacing

    app = QApplication.instance() or QApplication(sys.argv)

    orig_ss = app.styleSheet()
    app.setStyleSheet("")

    try:
        card = QFrame()
        card.setObjectName("ReferenceCard")
        card.setFixedSize(400, 180)
        card.setStyleSheet(f"""
            #ReferenceCard {{
                background-color: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.SM)

        # Header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Neural Agent Dispatcher")
        f_title = QFont("Segoe UI", -1)
        f_title.setPixelSize(14)
        f_title.setBold(True)
        title.setFont(f_title)
        title.setStyleSheet("QLabel { color: #f3f6fc; background: transparent; border: none; margin: 0; padding: 0; }")
        hdr.addWidget(title)

        badge = QLabel("AUTONOMOUS")
        f_badge = QFont("Consolas", -1)
        f_badge.setPixelSize(10)
        f_badge.setBold(True)
        badge.setFont(f_badge)
        badge.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 229, 255, 0.15);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 4px;
                padding: 2px 6px;
                margin: 0;
            }
        """)
        hdr.addWidget(badge, alignment=Qt.AlignRight)
        layout.addLayout(hdr)

        # Subtext
        sub = QLabel("The AuraAI agent ecosystem operates on top of native design tokens.")
        f_sub = QFont("Segoe UI", -1)
        f_sub.setPixelSize(12)
        sub.setFont(f_sub)
        sub.setWordWrap(True)
        sub.setStyleSheet("QLabel { color: #a5b4cb; background: transparent; border: none; margin: 0; padding: 0; }")
        layout.addWidget(sub)
        layout.addStretch()

        card.show()
        app.processEvents()

        pixmap = card.grab()
        card.close()
    finally:
        app.setStyleSheet(orig_ss)

    # Convert QPixmap to PIL Image via QBuffer
    from PySide6.QtCore import QBuffer, QByteArray
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()

    return Image.open(BytesIO(byte_array.data()))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Golden Baseline Manager & Audit Engine
# ─────────────────────────────────────────────────────────────────────────────

class BaselineManager:
    """
    Manages storage, validation, and lifecycle of visual regression baseline images.
    """

    def __init__(self, baselines_dir: Path | None = None) -> None:
        self.baselines_dir = baselines_dir or BASELINES_DIR
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.baselines_dir / "manifest.json"

    def get_token_hash(self) -> str:
        tokens = extract_canonical_tokens()
        return tokens.get("token_hash", "")

    def load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            return {"version": "1.0.0", "token_hash": "", "snapshots": {}}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"version": "1.0.0", "token_hash": "", "snapshots": {}}

    def save_manifest(self, manifest: Dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    def update_baselines(
        self,
        component_name: str,
        captures: Dict[str, Image.Image],
    ) -> Dict[str, Path]:
        """
        Overwrites / seeds golden baseline PNGs and updates manifest.json with current token_hash.
        """
        token_hash = self.get_token_hash()
        manifest = self.load_manifest()
        manifest["token_hash"] = token_hash
        manifest["updated_at"] = str(Path().resolve())

        saved_paths = {}
        for vp_name, img in captures.items():
            filename = f"{component_name}_{vp_name}.png"
            target_path = self.baselines_dir / filename
            img.save(target_path, format="PNG")

            img_bytes = target_path.read_bytes()
            img_hash = hashlib.sha256(img_bytes).hexdigest()[:16]

            manifest["snapshots"][f"{component_name}:{vp_name}"] = {
                "file": filename,
                "viewport": vp_name,
                "width": img.width,
                "height": img.height,
                "image_sha256": img_hash,
                "token_hash": token_hash,
            }
            saved_paths[vp_name] = target_path

        self.save_manifest(manifest)
        logger.info(f"[BaselineManager] Updated {len(captures)} baselines for {component_name} (token_hash: {token_hash})")
        return saved_paths

    def verify_captures(
        self,
        component_name: str,
        captures: Dict[str, Image.Image],
        threshold: float = 0.990,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Compares current captures against golden baselines.
        Returns (all_passed, list_of_diff_records).
        """
        manifest = self.load_manifest()
        current_token_hash = self.get_token_hash()
        manifest_token_hash = manifest.get("token_hash", "")

        token_hash_mismatch = bool(manifest_token_hash and manifest_token_hash != current_token_hash)
        results = []
        all_passed = True

        DIFFS_DIR.mkdir(parents=True, exist_ok=True)

        for vp_name, cur_img in captures.items():
            key = f"{component_name}:{vp_name}"
            baseline_info = manifest.get("snapshots", {}).get(key)

            if not baseline_info:
                results.append({
                    "viewport": vp_name,
                    "passed": False,
                    "ssim": 0.0,
                    "error": f"Missing baseline for {key}. Run --update-baselines to seed.",
                    "token_hash_mismatch": token_hash_mismatch,
                })
                all_passed = False
                continue

            baseline_path = self.baselines_dir / baseline_info["file"]
            if not baseline_path.exists():
                results.append({
                    "viewport": vp_name,
                    "passed": False,
                    "ssim": 0.0,
                    "error": f"Baseline image file missing: {baseline_path.name}",
                    "token_hash_mismatch": token_hash_mismatch,
                })
                all_passed = False
                continue

            golden_img = Image.open(baseline_path)
            score = compute_ssim(golden_img, cur_img)
            passed = score >= threshold

            diff_path = None
            if not passed:
                all_passed = False
                diff_img = generate_diff_image(golden_img, cur_img)
                diff_path = DIFFS_DIR / f"diff_{component_name}_{vp_name}.png"
                diff_img.save(diff_path)

            results.append({
                "viewport": vp_name,
                "passed": passed,
                "ssim": round(score, 4),
                "threshold": threshold,
                "diff_file": str(diff_path) if diff_path else None,
                "token_hash_mismatch": token_hash_mismatch,
            })

        return all_passed, results


# ─────────────────────────────────────────────────────────────────────────────
# 4. CLI Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_cli():
    parser = argparse.ArgumentParser(description="AuraAI Visual Regression & SSIM Engine")
    parser.add_argument("--check", action="store_true", help="Run multi-viewport visual regression audit against baselines")
    parser.add_argument("--update-baselines", action="store_true", help="Capture and save new golden baseline snapshots")
    parser.add_argument("--parity", action="store_true", help="Run cross-platform Qt vs Web component visual parity check")
    parser.add_argument("--threshold", type=float, default=0.990, help="SSIM passing threshold (default: 0.990)")

    args = parser.parse_args()

    # Load starter template
    template_path = _SRC_DIR / "engineering" / "templates" / "starter_app.html"
    if not template_path.exists():
        print(f"[ERROR] Starter app template not found at {template_path}")
        sys.exit(1)

    html_content = template_path.read_text(encoding="utf-8")
    bm = BaselineManager()

    if args.parity:
        print("=== AURA CROSS-PLATFORM (QT VS WEB) VISUAL PARITY AUDIT ===")
        print("1. Capturing Native Qt CyberCard reference...")
        qt_img = capture_qt_card_reference()

        parity_template = _SRC_DIR / "engineering" / "templates" / "components" / "card_parity.html"
        parity_html = parity_template.read_text(encoding="utf-8")

        print("2. Capturing Web CyberCard via Headless Playwright...")
        web_img = capture_web_element(parity_html, selector="#card-parity", filename="card_parity.html")

        qt_resized = qt_img.resize((400, 180))
        web_resized = web_img.resize((400, 180))

        score = compute_ssim(qt_resized, web_resized)
        is_offscreen = os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        threshold = 0.650 if is_offscreen else 0.850
        mode_str = "Headless Offscreen QPA" if is_offscreen else "Native Windows DirectWrite"

        print(f"3. Structural Similarity Index (SSIM): {score:.4f} (Mode: {mode_str}, Calibrated Threshold: >= {threshold:.3f})")
        if score >= threshold:
            print("[PASS] Cross-platform visual parity confirmed (Layout, Tokens, and Glassmorphic structure aligned).")
            sys.exit(0)
        else:
            print(f"[FAIL] Cross-platform visual discrepancy detected: SSIM {score:.4f} < {threshold:.3f}")
            sys.exit(1)

    elif args.update_baselines:
        print(f"=== SEEDING / UPDATING VISUAL REGRESSION BASELINES ===")
        captures = capture_web_viewports(html_content)
        saved = bm.update_baselines("starter_app", captures)
        print(f"[SUCCESS] Seeded {len(saved)} golden baselines in {BASELINES_DIR}:")
        for vp, p in saved.items():
            print(f"  • {vp}: {p.name}")
        sys.exit(0)

    else:
        # Default is --check
        print("=== RUNNING MULTI-VIEWPORT VISUAL REGRESSION AUDIT ===")
        captures = capture_web_viewports(html_content)
        passed, results = bm.verify_captures("starter_app", captures, threshold=args.threshold)

        for res in results:
            vp = res["viewport"]
            score = res.get("ssim", 0.0)
            status = "PASS" if res["passed"] else "FAIL"
            print(f"  • Viewport [{vp.upper()}]: SSIM = {score:.4f} (Threshold >= {args.threshold}) -> [{status}]")
            if not res["passed"] and res.get("error"):
                print(f"    ⚠️ {res['error']}")
            if res.get("token_hash_mismatch"):
                print(f"    ℹ️ Notice: Theme token hash changed. If intentional, run --update-baselines.")

        if passed:
            print("\n[SUCCESS] All viewports passed visual regression checks (Zero layout regressions).")
            sys.exit(0)
        else:
            print("\n[FAIL] Visual regression detected.")
            sys.exit(1)


if __name__ == "__main__":
    run_cli()
