"""
Test High-Detail Masterpiece SVG Generation & Quality Check
===========================================================
Location: scripts/test_masterpiece_art.py
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from ai.key_pool import KeyPool

pool = KeyPool.get_instance()

ARTIST_SYSTEM_PROMPT = """You are a World-Class Master SVG Vector Graphic Illustrator & Digital Artist.
When asked to draw an illustration, character, deity, object, or scene:
1. ALWAYS generate a breathtaking, highly detailed, professional-grade SVG illustration.
2. Use rich <defs> with sophisticated multi-stop linear and radial gradients (e.g. glowing gold, rich rubies, sacred saffron, deep shading, metallic highlights).
3. Use drop shadows and glow filters (<filter id="glow">).
4. Use intricate, realistic Bezier paths (<path d="M... C... Q... Z">) for smooth curves, contours, jewelry, ornate crowns (mukut), sacred tilak, expressive features, traditional ornaments, and delicate details.
5. Create a complete, stunning, layered composition with a beautiful dark-mode or thematic background (viewBox="0 0 800 800").
6. Output the complete, working, valid ```svg ... ``` code block. Never output simplistic basic primitive doodles or toy shapes."""

def generate_art(prompt):
    def _call(key):
        from groq import Groq
        c = Groq(api_key=key)
        resp = c.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": ARTIST_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096,
            temperature=0.6
        )
        return resp.choices[0].message.content
    return pool.execute_with_failover(_call, service="groq")

if __name__ == "__main__":
    t0 = time.perf_counter()
    print("Generating masterpiece SVG with openai/gpt-oss-120b...")
    svg_art = generate_art("Draw a detailed, ornate, majestic vector art illustration of Lord Ganesha with golden crown, ornate trunk, sacred tilak, and divine aura.")
    elapsed = time.perf_counter() - t0
    print(f"Generated in {elapsed:.2f}s! Total length: {len(svg_art)} characters.")
    print("=== PREVIEW ===")
    print(svg_art[:400])
    print("...")
    print(svg_art[-200:])

    # Save to artifacts for inspection
    out_path = PROJECT_ROOT / "artifacts" / "ganesha_masterpiece.svg"
    import re
    m = re.search(r"(<svg[\s\S]*?</svg>)", svg_art)
    if m:
        out_path.write_text(m.group(1), encoding="utf-8")
        print(f"Saved masterpiece SVG to {out_path}")
