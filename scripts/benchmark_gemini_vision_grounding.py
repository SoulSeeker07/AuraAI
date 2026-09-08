import os
import sys
import time
import json
import math
from dotenv import load_dotenv
from PIL import Image

load_dotenv(override=True)
sys.path.insert(0, "src")

from ai.key_pool import KeyPool
from google import genai
from google.genai import types

def run_vision_benchmark():
    img_path = r"C:/Users/yrsre/.gemini/antigravity/brain/615c0f1b-6328-4bcc-bc14-56f9daf9490c/.user_uploaded/media_1788896312707.png"
    img = Image.open(img_path)
    img_w, img_h = img.size

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    pool = KeyPool.get_instance()
    key = pool.get_active_key("gemini")
    client = genai.Client(api_key=key)

    part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")

    # Ground Truth definitions (physical pixel coordinates in 1024x182 image)
    # Each target has a true centroid and an acceptable clickable hit-box
    targets = [
        {
            "name": "Chevron > (Small Glyph)",
            "reference": "the right-pointing chevron arrow '>' icon next to 125% (Recommended)",
            "gt_center": (987.0, 81.0),
            "hit_bbox": (970, 60, 1000, 100),  # clickable right chevron button zone
        },
        {
            "name": "125% Dropdown Button",
            "reference": "the dropdown selector displaying '125% (Recommended)'",
            "gt_center": (840.0, 78.0),
            "hit_bbox": (760, 52, 955, 105),   # full dropdown container box
        },
        {
            "name": "1920x1080 Dropdown Button",
            "reference": "the dropdown selector displaying '1920 × 1080 (Recommended)'",
            "gt_center": (868.0, 154.0),
            "hit_bbox": (750, 128, 985, 178),  # full resolution dropdown box
        },
        {
            "name": "Scale Icon (Left)",
            "reference": "the rectangular display scale icon next to 'Scale'",
            "gt_center": (45.0, 74.0),
            "hit_bbox": (30, 58, 60, 90),
        },
    ]

    models_to_test = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]

    print("=" * 86)
    print("      GEMINI MULTIMODAL VISION BENCHMARK: 1080p @ 125% DPI SCALING")
    print("=" * 86)
    print(f"Image Resolution: {img_w}x{img_h} | Target OS Display: 1080p with 125% Scale")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n", flush=True)

    results = {}

    for model in models_to_test:
        print(f">>> MODEL: {model}", flush=True)
        results[model] = []

        for tgt in targets:
            time.sleep(1.0)
            prompt = (
                f"You are a computer vision UI grounding specialist.\n"
                f"Image size: {img_w} pixels wide by {img_h} pixels high.\n"
                f"Locate: {tgt['reference']}.\n"
                f"Find the EXACT pixel center coordinates [x, y] and bounding box [left, top, right, bottom].\n"
                f"Respond with ONLY a raw JSON object (no markdown, no backticks):\n"
                f'{{"found": true, "center": [x, y], "bbox": [left, top, right, bottom], "confidence": 1.0}}'
            )

            t0 = time.perf_counter()
            resp_text = ""
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=[prompt, part],
                    config=types.GenerateContentConfig(temperature=0.0)
                )
                resp_text = (res.text or "").strip()
            except Exception as e:
                print(f"  [ERROR] {tgt['name']}: {e}", flush=True)
                continue

            dur = time.perf_counter() - t0

            # Parse JSON
            clean = resp_text.replace("```json", "").replace("```", "").strip()
            pred_x, pred_y = None, None
            hit = False
            drift = 999.0

            try:
                data = json.loads(clean)
                center = data.get("center", [])
                if len(center) == 2:
                    pred_x, pred_y = float(center[0]), float(center[1])
                    # Compute spatial drift from GT center
                    gt_x, gt_y = tgt["gt_center"]
                    drift = math.sqrt((pred_x - gt_x)**2 + (pred_y - gt_y)**2)
                    # Check hit box
                    bx1, by1, bx2, by2 = tgt["hit_bbox"]
                    hit = (bx1 <= pred_x <= bx2) and (by1 <= pred_y <= by2)
            except Exception as e:
                print(f"  Parse failure on raw text: '{clean[:60]}...' ({e})")

            status = "HIT" if hit else "MISS"
            print(
                f"  • {tgt['name']:<28} | Latency: {dur:.2f}s | "
                f"Pred: ({pred_x}, {pred_y}) | GT: {tgt['gt_center']} | "
                f"Drift: {drift:5.1f}px | {status}",
                flush=True
            )

            results[model].append({
                "target": tgt["name"],
                "latency": dur,
                "pred": (pred_x, pred_y),
                "gt": tgt["gt_center"],
                "drift": drift,
                "hit": hit,
            })

        print()

    # --- OCR & Text Recognition Benchmark ---
    print(">>> OCR & TEXT RECOGNITION FIDELITY (Reading 125% scaled UI text)")
    ocr_prompt = (
        "Extract all UI labels, dropdown values, and descriptions visible in this settings screenshot. "
        "List them accurately as JSON."
    )
    for model in models_to_test:
        time.sleep(1.0)
        t0 = time.perf_counter()
        res = client.models.generate_content(
            model=model,
            contents=[ocr_prompt, part],
            config=types.GenerateContentConfig(temperature=0.0)
        )
        dur = time.perf_counter() - t0
        text = (res.text or "").strip()
        has_125 = "125%" in text
        has_1080 = "1920" in text and "1080" in text
        has_rec = "Recommended" in text
        has_scale = "Scale" in text and "layout" in text.lower()
        ocr_perfect = has_125 and has_1080 and has_rec and has_scale
        print(f"  • {model:<23} | Latency: {dur:.2f}s | 125% detected: {has_125} | 1080p detected: {has_1080} | Perfect OCR: {ocr_perfect}")

    print("\n" + "=" * 86)
    print("                    GEMINI VISION BENCHMARK SUMMARY")
    print("=" * 86)
    header = f"{'Model':<23} | {'Avg Latency':<12} | {'Avg Drift':<11} | {'Hit Rate':<10} | {'Chevron > Result':<16}"
    print(header)
    print("-" * len(header))
    for model, m_results in results.items():
        if m_results:
            avg_lat = sum(r["latency"] for r in m_results) / len(m_results)
            avg_drift = sum(r["drift"] for r in m_results) / len(m_results)
            hits = sum(1 for r in m_results if r["hit"])
            hit_rate = f"{(hits / len(m_results)) * 100:.0f}% ({hits}/{len(m_results)})"
            chev = next((r for r in m_results if "Chevron" in r["target"]), None)
            chev_str = f"HIT ({chev['drift']:.1f}px)" if (chev and chev["hit"]) else "MISS"
            print(f"{model:<23} | {avg_lat:.2f}s        | {avg_drift:.1f}px      | {hit_rate:<10} | {chev_str:<16}")
    print("=" * 86, flush=True)

if __name__ == "__main__":
    run_vision_benchmark()
