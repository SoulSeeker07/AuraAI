"""
WinRT Native Windows OCR Engine Wrapper
Location: src/vision/winrt_ocr.py

Provides native Windows OCR via Windows.Media.Ocr.OcrEngine.
- 0 MB GPU VRAM footprint (native CPU/OS subsystem).
- Sub-200ms 1080p full-frame recognition.
- Returns word-level and line-level bounding box coordinates.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

# Lazy-loaded WinRT modules to avoid hard import failures on non-Windows platforms
_imaging: Any = None
_ocr: Any = None
_streams: Any = None
_winrt_available: bool | None = None


def is_winrt_ocr_available() -> bool:
    """Check if Windows WinRT OCR SDK is installed and available."""
    global _imaging, _ocr, _streams, _winrt_available
    if _winrt_available is not None:
        return _winrt_available
    try:
        import winsdk.windows.graphics.imaging as imaging
        import winsdk.windows.media.ocr as ocr
        import winsdk.windows.storage.streams as streams

        _imaging = imaging
        _ocr = ocr
        _streams = streams
        _winrt_available = True
    except Exception as e:
        logger.debug(f"[WinRTOcr] WinRT OCR unavailable: {e}")
        _winrt_available = False
    return _winrt_available


async def run_ocr_on_pil_image_async(pil_img: Image.Image) -> dict[str, Any] | None:
    """
    Asynchronously run Windows native OCR on a PIL Image.

    Returns:
        dict with:
            - 'text': full concatenated recognized text
            - 'lines': list of line dicts containing 'text' and 'words'
                       where each word has 'text', 'x', 'y', 'w', 'h'
            - 'total_ms': total end-to-end execution time in ms
            - 'rec_ms': engine recognition time in ms
        or None if WinRT OCR is unavailable or recognition fails.
    """
    if not is_winrt_ocr_available():
        logger.warning("[WinRTOcr] WinRT OCR is not available in the current environment.")
        return None

    t0 = time.perf_counter()
    try:
        # 1. Convert PIL image to PNG bytes in-memory
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        bytes_data = buf.getvalue()

        # 2. Write to WinRT InMemoryRandomAccessStream
        writer = _streams.DataWriter()
        writer.write_bytes(bytes_data)
        ibuffer = writer.detach_buffer()

        mem_stream = _streams.InMemoryRandomAccessStream()
        await mem_stream.write_async(ibuffer)
        mem_stream.seek(0)

        # 3. Decode as SoftwareBitmap
        decoder = await _imaging.BitmapDecoder.create_async(mem_stream)
        software_bitmap = await decoder.get_software_bitmap_async()

        # 4. Initialize OcrEngine
        engine = _ocr.OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            logger.error("[WinRTOcr] Failed to create Windows OcrEngine from user profile languages.")
            return None

        t_engine = time.perf_counter()

        # 5. Recognize text
        result = await engine.recognize_async(software_bitmap)
        t_rec = time.perf_counter()

        total_ms = (t_rec - t0) * 1000
        rec_ms = (t_rec - t_engine) * 1000

        lines: list[dict[str, Any]] = []
        for line in result.lines:
            line_text = line.text
            words_info: list[dict[str, Any]] = []
            for word in line.words:
                rect = word.bounding_rect
                words_info.append({
                    "text": word.text,
                    "x": int(rect.x),
                    "y": int(rect.y),
                    "w": int(rect.width),
                    "h": int(rect.height),
                })
            lines.append({"text": line_text, "words": words_info})

        return {
            "text": result.text,
            "lines": lines,
            "total_ms": total_ms,
            "rec_ms": rec_ms,
        }

    except Exception as e:
        logger.error(f"[WinRTOcr] OCR execution failed: {e}", exc_info=True)
        return None


def run_ocr_on_pil_image_sync(pil_img: Image.Image) -> dict[str, Any] | None:
    """
    Synchronous convenience wrapper around run_ocr_on_pil_image_async.
    Handles event loop execution safely whether a loop is already running or not.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, run_ocr_on_pil_image_async(pil_img)).result()
        else:
            return loop.run_until_complete(run_ocr_on_pil_image_async(pil_img))
    except RuntimeError:
        return asyncio.run(run_ocr_on_pil_image_async(pil_img))
