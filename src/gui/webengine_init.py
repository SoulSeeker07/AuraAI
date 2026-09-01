"""
WebEngine Initialization & VRAM Safety
======================================
Location: src/gui/webengine_init.py

Configures Chromium runtime flags for QtWebEngine before QApplication creation
to enforce software rendering and zero VRAM allocation on resource-constrained GPUs.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

_INITIALIZED = False


def ensure_webengine_flags() -> None:
    """
    Sets QTWEBENGINE_CHROMIUM_FLAGS to force software rendering and disable GPU compositing.
    MUST be called before any QApplication or QGuiApplication instantiation.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    # Check if flags are already explicitly set by the environment
    existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    flags = [
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-software-rasterizer=false",
    ]

    combined = f"{existing_flags} {' '.join(flags)}".strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = combined
    _INITIALIZED = True
    logger.debug(f"[WebEngineInit] Set QTWEBENGINE_CHROMIUM_FLAGS: {combined}")
