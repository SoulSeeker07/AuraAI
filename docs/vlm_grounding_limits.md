# VLM Grounding Specification & Operational Boundaries

**Module**: `src/vision/grounding_engine.py`  
**Applicable Tiers**: Tier 1 (A11y/UIA/DOM), Tier 2A (OCR), Tier 2B (Multimodal VLM - Qwen/Groq), Tier 3 (Fail-Closed)  
**Date**: September 2026  

---

## 1. Coordinate Space Pipeline (3-Stage Invariant)

To guarantee that mouse events land on the correct physical display pixel on scaled monitors (e.g., 125% DPI scaling / 120 DPI on 1920×1080), all coordinates must pass through three isolated transformation stages.

```
+-----------------------------------------------------------------------------+
| Stage 1: VLM Downsample Reversal                                            |
|   (x1, y1) = (x0 / vlm_scale_factor, y0 / vlm_scale_factor)                 |
|   Note: If image was downscaled to fit VLM max dimension (e.g. 1024px),      |
|   this recovers physical screenshot pixel space.                            |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| Stage 2: Logical DOM DPI Scaling                                            |
|   (x2, y2) = (x1 * dpi_scale, y1 * dpi_scale)  IF source_is_logical=True     |
|   (x2, y2) = (x1, y1)                          IF source_is_logical=False    |
|   CRITICAL: VLM image coordinates and UIA bounding boxes are ALREADY         |
|   physical pixels. Multiplying them by dpi_scale causes double-scaling.     |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| Stage 3: Window Offset Translation                                          |
|   (x_screen, y_screen) = (x2 + window_left, y2 + window_top)                 |
|   Translates window-local pixels to absolute virtual desktop screen pixels. |
+-----------------------------------------------------------------------------+
```

### Reference Implementation: `translate_to_screen_coordinates()`
```python
def translate_to_screen_coordinates(
    coords: Tuple[int, int],
    window_bounds: Optional[Tuple[int, int, int, int]] = None,
    dpi_scale: float = 1.0,
    source_is_logical: bool = False,
    vlm_scale_factor: float = 1.0,
) -> Tuple[int, int]:
    x, y = float(coords[0]), float(coords[1])

    # Stage 1: Reverse VLM image downscaling
    if vlm_scale_factor > 0.0 and vlm_scale_factor != 1.0:
        x = x / vlm_scale_factor
        y = y / vlm_scale_factor

    # Stage 2: Logical DOM coordinates to physical pixels
    if source_is_logical and dpi_scale > 0.0 and dpi_scale != 1.0:
        x = x * dpi_scale
        y = y * dpi_scale

    # Stage 3: Local to screen offset translation
    if window_bounds and len(window_bounds) == 4:
        left, top = window_bounds[0], window_bounds[1]
        x += left
        y += top

    return int(round(x)), int(round(y))
```

---

## 2. Geometric Bounds Validation Guard

VLM outputs can hallucinate coordinates outside image boundaries or invert bounding boxes ($x_2 \le x_1$). The engine must enforce strict fail-closed validation before coordinate translation:

```python
# Image dimension clamp & check
img_w, img_h = img_for_vlm.size
raw_cx, raw_cy = float(center[0]), float(center[1])

if not (0 <= raw_cx <= img_w and 0 <= raw_cy <= img_h):
    logger.warning(f"[GroundingEngine] VLM center ({raw_cx}, {raw_cy}) outside image bounds ({img_w}x{img_h}).")
    return None

if bbox and len(bbox) == 4:
    bx1, by1, bx2, by2 = [float(v) for v in bbox]
    if not (0 <= bx1 < bx2 <= img_w and 0 <= by1 < by2 <= img_h):
        logger.warning(f"[GroundingEngine] VLM bbox {bbox} invalid or outside image bounds ({img_w}x{img_h}).")
        return None
```

Any prediction failing bounds validation returns `None` (triggers Tier 3 fail-closed).

---

## 3. KeyPool Multi-Key Failover for VLM Calls

Groq and cloud vision models enforce strict rate limits on free or standard tiers (e.g. 8,000 Tokens Per Minute on vision tokens, where a single base64 screenshot consumes $\sim 2,000 \dots 2,400$ tokens).

VLM calls must execute via `KeyPool.execute_with_failover()`:
```python
def _invoke_groq_vision(key: str):
    from groq import Groq
    c = Groq(api_key=key)
    return c.chat.completions.create(
        model=provider.vision_model or "qwen/qwen3.6-27b",
        messages=[...],
        temperature=0.0,
        max_tokens=1024,
    )

resp = pool.execute_with_failover(_invoke_groq_vision, service="groq")
```
* **Failure Mode Prevented**: When `GROQ_API_KEY` hits HTTP 429 TPM burst limits, KeyPool marks the key on cooldown (parsed from error text retry duration or 15.0s default in `src/ai/key_pool.py`) and immediately rotates to `GROQ_API_KEY1..4`.
* **Important**: Do not call `execute_with_retry()` (which was a previous typo). Always use `execute_with_failover()`.
* **Verification**: Verified via unit test `test_tier2_vlm_keypool_failover_on_429` using simulated `groq.RateLimitError(status_code=429)` across mocked keys. (Not claimed as an organic live hardware test).

---

## 4. Empirical Grounding Limits & Operational Boundaries

Empirical benchmarks run on live hardware ($1920 \times 1080$, $125\%$ DPI scaling) against `qwen/qwen3.6-27b` established the following spatial resolution boundaries:

### Measured Accuracies by Control Size

| Control Category | Target Dimensions | Example Target | Observed Localization Variance | Hit / Miss Result |
| :--- | :--- | :--- | :--- | :--- |
| **Large Labeled Control** | $\ge 60\text{px}$ width | `"125% (Recommended)"` Dropdown ($129 \times 35\text{px}$) | $\Delta X = 28\text{px}$, $\Delta Y = 6\text{px}$ | **HIT (100%)**: Drift is absorbed by the interactive surface. |
| **Small Isolated Glyph** | $< 25\text{px}$ | Scale Icon ($18 \times 16\text{px}$) | $\Delta = 5.4\text{px}$ | **HIT**: Centered on distinct glyph. |
| **Small Isolated Glyph** | $< 25\text{px}$ | Chevron `>` Arrow ($6 \times 11\text{px}$) | $\Delta = 5.0\text{px}$ (Specific prompt)<br>$\Delta = 28.8\text{px}$ (Ambiguous prompt) | **UNSTABLE (50% Overall)**: $28.8\text{px}$ drift produces an **outright miss**. |
| **Dense Ribbon/Palette** | Sub-20px icons packed with $<5\text{px}$ margin | Paint brush styles, CAD tools | Untested empirically | **HIGH RISK OF MISCLICK** (Theoretical based on observed $\sim 28\text{px}$ drift). |

### Prompt Phrasing Sensitivity
* At `temperature = 0.0`, Qwen is **100% deterministic given the identical prompt** ($\text{StdDev} = 0.00\text{px}$).
* Across **different natural language phrasings**, spatial visual attention shifts by **$\sim 20\text{px} \dots 30\text{px}$**:
  * On a button with text and a box, the model shifts between the text centroid and the container centroid.
  * On a tiny glyph, an ambiguous phrase shifts attention to adjacent whitespace.

---

## 5. Architectural Invariant Rules

1. **Tier 1 Primary**: For any control under $\sim 40\text{px}$, Tier 1 (Accessibility tree / UIA / DOM bounding boxes) **must remain the primary interaction path**.
2. **Gated VLM Fallback**: If Tier 1 fails and Tier 2B VLM must ground a control $< 40\text{px}$ (or in a dense toolbar), the action must be assigned `ActionRisk.MEDIUM` or `HIGH` requiring visual change verification (`wait_for_change`) or user confirmation.
3. **Never Trust VLM Bounding Box Widths for Hit Testing**: Bounding boxes generated for small icons are coarse ($\sim 24 \dots 34\text{px}$ spans). Downstream interaction logic must use the `center` coordinate, not the `bbox` boundaries, when clicking.

---

## 6. Verification & Process Lessons

1. **Test Identification**: Always verify test presence and symbol names against `git diff` and actual `pytest -v` output, rather than paraphrasing test file docstrings or prose summaries.
2. **Causal Claims Require Direct Traces**: Latencies or runtime delays must be backed by captured artifacts (e.g. response headers, retry logs) rather than deduced plausible hypotheses.
3. **Hardware Ground Truth**: Visual and DPI claims must be proven on the target display configuration ($125\%$ DPI, physical coordinates) and confirmed through actual OS interactions.
