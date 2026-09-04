# SPIKE-M31: Generalized Desktop Visual Grounding & Perception Feasibility

**Status**: ⚠️ **INCOMPLETE / OPEN RESEARCH SPIKE**  
**Target Roadmap Area**: Phase 10 / Generalized Desktop Perception  
**Evaluated Hardware**: NVIDIA GeForce GTX 1650 4GB (TU117 Turing, No Tensor Cores)  
**Date**: September 2, 2026  

---

## 1. Objective & Scope

SPIKE-M31 was initiated to investigate the feasibility of **generalized visual-spatial desktop UI comprehension** for opaque canvas surfaces (Figma, WebGL, custom game engines, and unexposed Win32/Qt windows) where the standard accessibility tree (UIA) returns an empty tree or a single opaque `HWND`.

The spike set out to evaluate:
1. **Can lightweight UI candidate detection run locally on consumer hardware within an 800ms end-to-end voice loop latency budget?**
2. **Can local visual grounding resolve UI elements with zero VRAM and zero cloud API dependencies?**
3. **What is the true empirical boundary between locally resolvable controls and controls requiring cloud/semantic disambiguation?**

---

## 2. The Proven Baseline (Local Text-Bearing Controls)

For controls that contain readable text labels (buttons, menu items, tabs, labeled form fields), SPIKE-M31 successfully established a high-speed, local perceptual pipeline:

```
[Screen Capture] 
      │
      ├───► [OmniParser ONNX Candidate Detector (CPU)] ──► 54ms (640x640)
      │                                                         │
      └───► [Windows WinRT Native OCR Engine (CPU)]   ──► 192ms (1080p full-frame)
                                                                │
                                                                ▼
                                      [Spatial Containment Fusion] ──► 3ms
                                                                │
                                                                ▼
                                   Resolved Labeled Widgets (E2E: ~250ms, 0 MB VRAM)
```

### Empirical Metrics
* **Candidate Bounding-Box Detection**:
  * Evaluated checkpoint: `onnx-community/OmniParser-icon_detect` (11.57 MB standalone ONNX).
  * Inference execution: `54.07ms` on CPU via `onnxruntime.InferenceSession`.
  * **GPU VRAM Impact**: **0 MiB** (leaves all 3.4 GB of GTX 1650 VRAM completely free).
  * Quality: Replaces failed OpenCV contour heuristics (which over-segmented into $8\times11\text{px}$ text character sub-strokes) with genuine interactive control boxes (median width $104\text{px}$, median height $37\text{px}$). Post-NMS (IoU 0.45) yields 35–55 clean, non-overlapping clickable targets per screen.
* **Text Extraction & Grounding**:
  * Engine: `Windows.Media.Ocr.OcrEngine` via Python `winsdk`.
  * Performance: `192ms` warm end-to-end full 1080p frame OCR (130ms engine time).
  * **GPU VRAM Impact**: **0 MiB** (native Windows OS subsystem).
  * Output: 154 text lines with per-word pixel bounding boxes.
* **End-to-End Latency**:
  $$\text{Detector (54ms)} + \text{NMS (2ms)} + \text{WinRT OCR (192ms)} + \text{Containment Map (3ms)} = \mathbf{\mathbf{\sim 251ms}}$$
  This operates with **549ms of headroom** below the 800ms voice-loop interaction contract.

---

## 3. Open Blocker #1: Non-Text Glyph Resolution (The Headline Gap)

> [!CAUTION]
> **HEADLINE FINDING**: Aura currently has **zero local semantic mechanism** to resolve non-text icons, glyphs, or symbolic controls.

While text-bearing widgets account for approximately **56%** of desktop controls, the remaining **44%** are pure non-text glyphs (toolbar symbols, window chevrons, taskbar tray icons, media playback controls, inventory slots in games).

### Why Local Matching Failed: The CLIP Salience-Bias Collapse
We evaluated `openai/clip-vit-base-patch32` on real desktop UI crops. While FP32 inference was fast on the GTX 1650 ($\sim 8.4\text{ms}$ per crop):
1. **Salience Bias Failure Mode**: Generic web-image CLIP embeddings key entirely on high-contrast, saturated chromatic features (such as bright logos or colored banners). In real UI crop testing, a red logo scored the highest similarity for every single query ("search bar", "video playback controls", "channel description"), drowning out subtle grey buttons and input boxes regardless of query text.
2. **Top-1 Resolution Failure**: Generic web-domain CLIP cannot distinguish subtle UI glyphs from container rectangles.

### Unsolved Reality
For pure glyph targets (e.g., *"click the save icon"*, *"click settings gear"*, *"click pencil tool"*), the detector produces a valid bounding box, but Aura has no local capability to determine which bounding box corresponds to the command.

### Viable Forward Paths
1. **Evaluate Dedicated UI Icon Embedding Models**: Investigate specialized icon models (e.g. `IconCLIP`, `SeeClick`, or vector glyph fingerprinting) trained on UI dataset icon-caption pairs rather than generic web photographs.
2. **Rate-Budget-Gated Cloud Disambiguation Tier**: Route *only* the ~44% pure glyph subset to cloud vision (Groq Qwen 27B / Gemini), strictly gated behind visual hash caching and frame-diffing.

---

## 4. Open Blocker #2: Licensing & Weights Provenance (TD-015)

The working ONNX detector (`onnx-community/OmniParser-icon_detect`) is an export of Microsoft's `OmniParser`, which is licensed under the **GNU Affero General Public License v3 (AGPLv3)**.

### The Search for Permissive Alternatives Failed
An exhaustive initial check on HuggingFace for Apache-2.0 or MIT alternatives revealed:
1. `SumeetSuman83/ui_element_detection` (Apache-2.0): **Non-viable**. Artifacts are legacy TensorFlow 1.x / Keras H5 checkpoints (`cnn-rico-1.h5`), incompatible with modern PyTorch/ONNX runtimes.
2. `Virasad/yolov5-desktop-icon-detection` (MIT): **Non-viable without code risk**. Checkpoint is a pickled PyTorch `.pt` file that instantiates `models.yolo.Model`. It is blocked by PyTorch 2.6+ `weights_only=True` security checks and requires unpickling code from the AGPLv3-licensed `yolov5` repository.

### Technical Debt Recorded
* **`TD-015: Desktop Visual Grounding Detector Relies on AGPLv3-Derived ONNX Weights`**: If Aura is ever distributed or open-sourced under a permissive license (MIT/Apache), these weights cannot be bundled without imposing AGPL copyleft questions. A permissive detector (e.g. an Apache-2.0 RT-DETR or custom trained YOLO-UI ONNX model) must be developed or converted to replace it.

---

## 5. Methodology Note: Corpus Drift & Process Lesson

During Gate C benchmarking, an initial report claimed "PASSED" based on disk fixtures rather than the pre-committed 4-surface corpus:
1. **Corpus Drift**: Stale screenshots (`temp/screenshots/screenshot_full_...`, `tests/visual_regression/offscreen_qt.png`) were tested instead of active Device Manager, Paint, or Steam sessions.
2. **Query Resolution Masked as Throughput**: Raw detector and OCR throughput were measured, but the 12 pre-committed target queries were not evaluated against ground truth.
3. **The Root Cause**: Attempting live screen capture during a locked Windows session (`HWND 0`) produced pitch-black buffers (`Min: 0, Max: 0`), which led to testing old disk files that contained error overlays (`'screen pixels cannot be captured'`).

**Process Invariant Reaffirmed**: A benchmark is only valid if executed against the exact committed surfaces with ground-truth query resolution verified, not deduced from component throughput.

---

## 6. Unresolved / Retry Needed: Real 4-Surface Corpus Capture

Live desktop capture via GDI `BitBlt` requires an active, unlocked user session.

### Pre-Condition Guard for Next Run
Any automated screen capture script must verify interactive desktop availability before benchmarking:
```python
hwnd = win32gui.GetForegroundWindow()
if hwnd == 0 or not win32gui.GetWindowText(hwnd):
    raise RuntimeError("Pre-condition failed: Windows desktop is locked or display session is detached.")
```

### Pending Action
When running in an active interactive desktop session:
1. Launch and capture the 4 real committed surfaces:
   * **Surface 1 (Chromium/Hybrid)**: VS Code workbench.
   * **Surface 2 (Win32 Native Dialog)**: Task Manager (`Taskmgr.exe`) or Device Manager (`devmgmt.msc`).
   * **Surface 3 (Creative Canvas)**: MS Paint (`mspaint.exe`) or Web Photopea.
   * **Surface 4 (Custom Render/Game)**: Steam client (`steam.exe`).
2. Run the 12 pre-committed evaluation queries and record individual resolution pass/fail rates.

---

## 7. Explicit Non-Decision: Milestone 31 Status

* **`docs/milestones/milestone31.md` will NOT be written as an active milestone.**
* SPIKE-M31 remains **OPEN as an active research spike**.
* It cannot graduate to a scheduled milestone until:
  1. A viable local or rate-budgeted semantic matcher for pure non-text glyphs (Blocker #1) is demonstrated on real UI crops.
  2. The licensing status of the UI detector weights (Blocker #2 / TD-015) is formally resolved.
