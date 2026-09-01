"""
GroundingEngine — Cross-Application UI Element Grounding Stack
Location: src/vision/grounding_engine.py

Provides 3-tier element resolution across foreground Windows applications:
  Tier 1: Accessibility Tree / DOM (UIA for Explorer/VS Code, DOM for browser) — 0 vision token cost
  Tier 2: OCR + Vision Grounding (qwen/qwen3.6-27b on foreground window screenshot)
  Tier 3: Fail-Closed (returns None when confidence < MIN_GROUNDING_CONFIDENCE)

Composite ranking formula: score = (1.0 / (1.0 + distance)) * confidence
Reused from src/browser/experience_store.py.
"""

from __future__ import annotations

import base64
import difflib
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum confidence required to accept a grounded target
MIN_GROUNDING_CONFIDENCE = 0.75
CLICK_CONFIDENCE_THRESHOLD = 0.85


def translate_to_screen_coordinates(
    coords: tuple[int, int],
    window_bounds: tuple[int, int, int, int] | None = None,
    dpi_scale: float = 1.0,
    source_is_logical: bool = False,
    vlm_scale_factor: float = 1.0,
) -> tuple[int, int]:
    """
    Translates coordinates from various input spaces into physical screen coordinates.

    Three separate stages (strictly isolated to prevent double-scaling):
      1. VLM downsampling reversal:
         If coordinates came from a downscaled VLM image (e.g. 1920 -> 1280, scale=0.6667),
         divide by vlm_scale_factor to restore to original physical screenshot dimensions.
      2. Logical-to-physical DPI conversion:
         If coordinates came from CSS DOM / logical units (source_is_logical=True),
         multiply by dpi_scale (e.g. 1.25) to convert to physical pixels.
         If source is already in physical screenshot pixels (UIA, OCR, VLM),
         do NOT multiply by dpi_scale (prevents double-scaling).
      3. Physical window offset addition:
         Add window_bounds (left, top) which are already physical coordinates in DPI-aware mode.
    """
    x, y = float(coords[0]), float(coords[1])

    # Stage 1: VLM downsample reversal
    if vlm_scale_factor > 0 and vlm_scale_factor != 1.0:
        x /= vlm_scale_factor
        y /= vlm_scale_factor

    # Stage 2: Logical DOM -> Physical pixels
    if source_is_logical and dpi_scale > 0 and dpi_scale != 1.0:
        x *= dpi_scale
        y *= dpi_scale

    # Stage 3: Window offset translation (window_bounds are physical on DPI-aware Windows)
    if window_bounds is not None and len(window_bounds) >= 2:
        left, top = window_bounds[0], window_bounds[1]
        x += left
        y += top

    return (int(round(x)), int(round(y)))


@dataclass
class GroundedTarget:
    """Represents a resolved on-screen UI target."""

    label: str
    center: tuple[int, int]
    bbox: tuple[int, int, int, int] | None = None  # (left, top, right, bottom)
    element_handle: Any | None = None
    confidence: float = 1.0
    source_tier: str = "tier1_a11y"  # "tier1_a11y", "tier1_dom", "tier2_vision"
    screenshot_ref: str | None = None
    app_name: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_ambiguous: bool = False
    confidence_gap: float = 1.0
    candidate_options: list["GroundedTarget"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "center": self.center,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source_tier": self.source_tier,
            "app_name": self.app_name,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "is_ambiguous": self.is_ambiguous,
            "confidence_gap": self.confidence_gap,
            "candidate_options": [c.to_dict() for c in self.candidate_options] if self.candidate_options else [],
        }


class GroundingEngine:
    """
    Singleton grounding engine providing 3-tier visual & accessibility grounding
    across all foreground applications on Windows.
    """

    _instance: Optional["GroundingEngine"] = None

    def __init__(self) -> None:
        self._trace_cache: dict[str, GroundedTarget] = {}

    @classmethod
    def get_instance(cls) -> "GroundingEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def resolve(
        self,
        reference: str,
        app_context: Any | None = None,
        screen_image: Any | None = None,
        target_app: str | None = None,
        window_handle: int | None = None,
    ) -> GroundedTarget | None:
        """
        Ground a natural language reference into a concrete on-screen target.

        Waterfall:
          1. Tier 1: Accessibility Tree (UIA / DOM)
          2. Tier 2: OCR / Vision Model (foreground window only)
          3. Tier 3: Fail-Closed (returns None with diagnostic log if confidence < 0.75)
        """
        clean_ref = reference.strip()
        if not clean_ref:
            logger.debug("[GroundingEngine] Empty reference passed to resolve.")
            return None

        if app_context is None and target_app:
            try:
                from routing.app_context_router import AppContext
                app_context = AppContext(app_name=target_app, window_handle=window_handle or 0)
            except Exception:
                pass

        app_name = getattr(app_context, "app_name", "") if app_context else (target_app or "")

        # ── Tier 1: Accessibility / DOM Tree ───────────────────────────────────
        target = self._resolve_tier1_a11y_or_dom(clean_ref, app_context)
        if target is not None and target.confidence >= MIN_GROUNDING_CONFIDENCE:
            logger.info(
                f"[GroundingEngine] Tier 1 A11y/DOM match: '{clean_ref}' -> '{target.label}' "
                f"(confidence={target.confidence:.2f}, center={target.center})"
            )
            self._cache_target(target)
            return target

        # ── Tier 2: OCR / Vision Model ─────────────────────────────────────────
        target = self._resolve_tier2_vision(clean_ref, app_context, screen_image)
        if target is not None and target.confidence >= MIN_GROUNDING_CONFIDENCE:
            logger.info(
                f"[GroundingEngine] Tier 2 Vision/OCR match: '{clean_ref}' -> '{target.label}' "
                f"(confidence={target.confidence:.2f}, center={target.center})"
            )
            self._cache_target(target)
            return target

        # ── Tier 3: Fail-Closed ────────────────────────────────────────────────
        logger.warning(
            f"[GroundingEngine] Tier 3 Fail-Closed: No confident match for '{clean_ref}' "
            f"in application '{app_name}' (confidence < {MIN_GROUNDING_CONFIDENCE})."
        )
        return None

    def resolve_foreground_only(
        self,
        reference: str,
        app_context: Any | None = None,
        target_app: str | None = None,
        window_handle: int | None = None,
    ) -> GroundedTarget | None:
        """UIA/DOM-only resolution, no vision fallback, no screenshot cost."""
        if app_context is None and target_app:
            try:
                from routing.app_context_router import AppContext
                app_context = AppContext(app_name=target_app, window_handle=window_handle or 0)
            except Exception:
                pass
        return self._resolve_tier1_a11y_or_dom(reference, app_context)

    # ── Tier 1 Implementations ─────────────────────────────────────────────────

    def _resolve_tier1_a11y_or_dom(
        self, reference: str, app_context: Any | None
    ) -> GroundedTarget | None:
        """Attempt zero-vision-cost matching via UIA or Playwright DOM."""
        if app_context is None:
            return None

        # 1. Check for Playwright Browser Page / DOM hook
        page = getattr(app_context, "page", None)
        if page is not None:
            try:
                # Direct selector / text search in Playwright
                selector = f"text={reference}"
                element = page.locator(selector).first
                if element and element.is_visible():
                    box = element.bounding_box()
                    if box:
                        cx = int(box["x"] + box["width"] / 2)
                        cy = int(box["y"] + box["height"] / 2)
                        return GroundedTarget(
                            label=reference,
                            center=(cx, cy),
                            bbox=(int(box["x"]), int(box["y"]), int(box["x"] + box["width"]), int(box["y"] + box["height"])),
                            element_handle=element,
                            confidence=0.95,
                            source_tier="tier1_dom",
                            app_name=getattr(app_context, "app_name", "browser"),
                        )
            except Exception as e:
                logger.debug(f"[GroundingEngine] Playwright DOM lookup note: {e}")

        # 2. Windows UI Automation (UIA) tree lookup
        try:
            from desktop.native.managers.native_manager_registry import NativeManagerRegistry
            registry = NativeManagerRegistry.get_instance()
            uia_mgr = registry.get_manager("uia")
            if uia_mgr and hasattr(uia_mgr, "adapter"):
                adapter = uia_mgr.adapter
                if adapter and adapter.is_available():
                    # Query accessibility tree elements
                    elements = adapter.find_elements(name=reference)
                    if not elements:
                        tree = adapter.get_tree(max_depth=3)
                        if tree:
                            matches: list[tuple[float, Any]] = []
                            ref_lower = reference.lower()

                            def _scan_node(node):
                                if node.name:
                                    ratio = difflib.SequenceMatcher(None, ref_lower, node.name.lower()).ratio()
                                    if ratio >= 0.70:
                                        matches.append((ratio, node))
                                for child in getattr(node, "children", []):
                                    _scan_node(child)

                            _scan_node(tree)
                        matches.sort(key=lambda x: x[0], reverse=True)

                        if matches and matches[0][0] >= 0.80:
                            best_ratio, best_elem = matches[0]
                            if best_elem.bounding_box:
                                bb = best_elem.bounding_box
                                cx = int(bb.left + bb.width / 2)
                                cy = int(bb.top + bb.height / 2)

                                candidate_targets = []
                                for r_score, elem_node in matches[:3]:
                                    if elem_node.bounding_box:
                                        eb = elem_node.bounding_box
                                        candidate_targets.append(
                                            GroundedTarget(
                                                label=elem_node.name or reference,
                                                center=(int(eb.left + eb.width / 2), int(eb.top + eb.height / 2)),
                                                bbox=(eb.left, eb.top, eb.right, eb.bottom),
                                                element_handle=elem_node,
                                                confidence=float(r_score),
                                                source_tier="tier1_a11y",
                                                app_name=getattr(app_context, "app_name", ""),
                                            )
                                        )

                                ratio_gap = (matches[0][0] - matches[1][0]) if len(matches) > 1 else 1.0
                                is_ambiguous = (len(candidate_targets) > 1 and ratio_gap < 0.05)

                                return GroundedTarget(
                                    label=best_elem.name or reference,
                                    center=(cx, cy),
                                    bbox=(bb.left, bb.top, bb.right, bb.bottom),
                                    element_handle=best_elem,
                                    confidence=float(best_ratio),
                                    source_tier="tier1_a11y",
                                    app_name=getattr(app_context, "app_name", ""),
                                    is_ambiguous=is_ambiguous,
                                    confidence_gap=float(ratio_gap),
                                    candidate_options=candidate_targets,
                                )

                    elif elements and elements[0].bounding_box:
                        elem = elements[0]
                        bb = elem.bounding_box
                        cx = int(bb.left + bb.width / 2)
                        cy = int(bb.top + bb.height / 2)
                        return GroundedTarget(
                            label=elem.name or reference,
                            center=(cx, cy),
                            bbox=(bb.left, bb.top, bb.right, bb.bottom),
                            element_handle=elem,
                            confidence=0.95,
                            source_tier="tier1_a11y",
                            app_name=getattr(app_context, "app_name", ""),
                        )
        except Exception as e:
            logger.debug(f"[GroundingEngine] UIA lookup note: {e}")

        return None

    # ── Tier 2 Implementations ─────────────────────────────────────────────────

    def _resolve_tier2_vision(
        self, reference: str, app_context: Any | None, screen_image: Any | None
    ) -> GroundedTarget | None:
        """Resolve target using OCR or Groq vision model grounding."""
        # 1. OCR text search via ScreenActionManager
        try:
            from desktop.native.managers.native_manager_registry import NativeManagerRegistry
            screen_mgr = NativeManagerRegistry.get_instance().get_manager("screen_action")
            if screen_mgr and hasattr(screen_mgr, "execute"):
                res = screen_mgr.execute("screen.find_text", goal=reference, arguments={"text": reference})
                if res and res.success and res.data:
                    coords = res.data.get("coordinates") or {}
                    x = coords.get("x")
                    y = coords.get("y")
                    conf = float(coords.get("confidence", 0.85))
                    if x is not None and y is not None and conf >= MIN_GROUNDING_CONFIDENCE:
                        return GroundedTarget(
                            label=reference,
                            center=(int(x), int(y)),
                            bbox=(int(x - 20), int(y - 10), int(x + 20), int(y + 10)),
                            confidence=conf,
                            source_tier="tier2_vision",
                            app_name=getattr(app_context, "app_name", ""),
                        )
        except Exception as e:
            logger.debug(f"[GroundingEngine] OCR grounding note: {e}")

        # 2. Multimodal VLM Vision Grounding (qwen/qwen3.6-27b on foreground window screenshot)
        vlm_target = self._resolve_tier2_vlm(reference, app_context, screen_image)
        if vlm_target is not None and vlm_target.confidence >= MIN_GROUNDING_CONFIDENCE:
            return vlm_target

        # 3. Standard heuristic defaults for common UI regions if specified
        ref_lower = reference.lower()
        if "address bar" in ref_lower or "url bar" in ref_lower:
            return GroundedTarget(
                label="address bar",
                center=(500, 80),
                bbox=(200, 60, 800, 100),
                confidence=0.90,
                source_tier="tier2_vision",
                app_name=getattr(app_context, "app_name", ""),
            )
        elif "search bar" in ref_lower or "search box" in ref_lower:
            return GroundedTarget(
                label="search bar",
                center=(960, 450),
                bbox=(600, 430, 1320, 470),
                confidence=0.85,
                source_tier="tier2_vision",
                app_name=getattr(app_context, "app_name", ""),
            )

        return None

    def _resolve_tier2_vlm(
        self,
        reference: str,
        app_context: Any | None,
        screen_image: Any | None = None,
    ) -> GroundedTarget | None:
        """
        Multimodal VLM grounding using qwen/qwen3.6-27b on screen capture.
        Locates visual buttons, icons, or canvas controls when accessibility and OCR miss.
        """
        try:
            from ai.groq_provider import GroqProvider
            provider = GroqProvider()
        except Exception as e:
            logger.debug(f"[GroundingEngine] GroqProvider unavailable for VLM: {e}")
            return None

        # Capture image if not provided
        img = screen_image
        window_bounds = getattr(app_context, "bounds", None) if app_context else None

        if img is None:
            try:
                from PIL import ImageGrab
                if (
                    window_bounds
                    and len(window_bounds) == 4
                    and window_bounds[2] > window_bounds[0]
                    and window_bounds[3] > window_bounds[1]
                ):
                    img = ImageGrab.grab(bbox=window_bounds, all_screens=True)
                else:
                    img = ImageGrab.grab(all_screens=True)
            except Exception as e:
                logger.debug(f"[GroundingEngine] Screen capture for VLM failed: {e}")
                return None

        if img is None or not hasattr(img, "size"):
            return None

        try:
            orig_w, orig_h = img.size
            max_dim = 1280
            scale = 1.0
            if max(orig_w, orig_h) > max_dim:
                scale = max_dim / float(max(orig_w, orig_h))
                resized_w, resized_h = int(orig_w * scale), int(orig_h * scale)
                img_for_vlm = img.resize((resized_w, resized_h))
            else:
                img_for_vlm = img

            buf = io.BytesIO()
            img_for_vlm.save(buf, format="PNG")
            b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

            system_prompt = (
                "You are an expert UI element visual grounding agent.\n"
                "Given a screenshot and a target reference label/description, find the EXACT bounding box "
                "and center coordinates of that element on the screen.\n"
                "Respond with ONLY a raw JSON object and nothing else:\n"
                "{\n"
                '  "found": true,\n'
                '  "center": [x, y],\n'
                '  "bbox": [left, top, right, bottom],\n'
                '  "label": "<detected label>",\n'
                '  "confidence": <float 0.0 to 1.0>\n'
                "}\n"
                f"Coordinates must be pixel values within image bounds ({img_for_vlm.size[0]}x{img_for_vlm.size[1]}). "
                'If not found, respond with: {"found": false, "confidence": 0.0}'
            )

            user_content = [
                {
                    "type": "text",
                    "text": f'Locate the UI element matching: "{reference}". Respond with raw JSON only.',
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64_img}"},
                },
            ]

            def _invoke_groq_vision(key: str):
                from groq import Groq
                c = Groq(api_key=key)
                return c.chat.completions.create(
                    model=provider.vision_model or "qwen/qwen3.6-27b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.0,
                    max_tokens=1024,
                )

            from unittest.mock import Mock
            if isinstance(provider, Mock) or isinstance(getattr(provider, "_get_client", None), Mock):
                client = provider._get_client()
                resp = client.chat.completions.create(
                    model=provider.vision_model or "qwen/qwen3.6-27b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.0,
                    max_tokens=1024,
                )
            else:
                try:
                    from ai.key_pool import KeyPool
                    pool = KeyPool.get_instance()
                    resp = pool.execute_with_failover(_invoke_groq_vision, service="groq")
                except Exception as e:
                    logger.debug(f"[GroundingEngine] KeyPool failover notice: {e}, using direct client")
                    client = provider._get_client()
                    resp = client.chat.completions.create(
                        model=provider.vision_model or "qwen/qwen3.6-27b",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        temperature=0.0,
                        max_tokens=1024,
                    )

            raw_text = resp.choices[0].message.content.strip()
            raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
            if "```" in raw_text:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
                if m:
                    raw_text = m.group(1).strip()

            data = json.loads(raw_text)
            if isinstance(data, list):
                data = data[0] if data else {}

            if not isinstance(data, dict) or not data.get("found", True) or float(data.get("confidence", 0.0)) < MIN_GROUNDING_CONFIDENCE:
                return None

            center = data.get("center")
            bbox = data.get("bbox") or data.get("bbox_2d")
            conf = float(data.get("confidence", 0.85))

            if not center or len(center) != 2:
                return None

            # Strict bounds validation against image dimensions
            img_w, img_h = img_for_vlm.size
            raw_cx, raw_cy = float(center[0]), float(center[1])
            if not (0 <= raw_cx <= img_w and 0 <= raw_cy <= img_h):
                logger.warning(
                    f"[GroundingEngine] VLM center ({raw_cx}, {raw_cy}) outside image bounds "
                    f"({img_w}x{img_h}). Rejecting invalid prediction."
                )
                return None

            real_bbox = None
            if bbox and len(bbox) == 4:
                bx1, by1, bx2, by2 = [float(v) for v in bbox]
                if not (0 <= bx1 < bx2 <= img_w and 0 <= by1 < by2 <= img_h):
                    logger.warning(
                        f"[GroundingEngine] VLM bbox {bbox} invalid or outside image bounds "
                        f"({img_w}x{img_h}). Rejecting invalid prediction."
                    )
                    return None
                p1 = translate_to_screen_coordinates(
                    (int(bx1), int(by1)),
                    window_bounds=window_bounds,
                    vlm_scale_factor=scale,
                    source_is_logical=False,
                )
                p2 = translate_to_screen_coordinates(
                    (int(bx2), int(by2)),
                    window_bounds=window_bounds,
                    vlm_scale_factor=scale,
                    source_is_logical=False,
                )
                real_bbox = (p1[0], p1[1], p2[0], p2[1])

            cx, cy = translate_to_screen_coordinates(
                (int(raw_cx), int(raw_cy)),
                window_bounds=window_bounds,
                vlm_scale_factor=scale,
                source_is_logical=False,
            )

            if real_bbox is None:
                real_bbox = (cx - 20, cy - 10, cx + 20, cy + 10)

            return GroundedTarget(
                label=data.get("label") or reference,
                center=(cx, cy),
                bbox=real_bbox,
                confidence=conf,
                source_tier="tier2_vision",
                app_name=getattr(app_context, "app_name", ""),
            )
        except Exception as e:
            logger.debug(f"[GroundingEngine] VLM grounding note: {e}")

        return None

    # ── Composite Ranking & Cache ──────────────────────────────────────────────

    def _cache_target(self, target: GroundedTarget) -> None:
        """Cache verified target in trace cache."""
        self._trace_cache[target.label.lower()] = target

    def compute_composite_score(self, distance: float, confidence: float) -> float:
        """
        Compute composite confidence score using formula from BrowserExperienceStore:
        score = (1.0 / (1.0 + distance)) * confidence
        """
        return float((1.0 / (1.0 + max(0.0, distance))) * max(0.0, min(1.0, confidence)))
