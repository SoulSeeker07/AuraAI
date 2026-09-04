"""
Test Draw Iron Man Direct SVG Generation
=========================================
Location: scripts/test_draw_ironman.py
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from ai.fast_client import FastLLMClient
from gui.widgets.message_parser import parse_message_segments, SegmentType

def run():
    t0 = time.perf_counter()
    print("Testing FastLLMClient with 'draw ironman'...")
    resp = FastLLMClient.query("draw ironman")
    elapsed = time.perf_counter() - t0
    print(f"Generated response in {elapsed:.2f}s! Total length: {len(resp)} characters.\n")
    print("=== PREVIEW ===")
    print(resp[:400])
    print("...")

    segs = parse_message_segments(resp)
    print("\nParsed segments:")
    for s in segs:
        print(f" - [{s.type.name}] Title: '{s.title}', Length: {len(s.content)} chars")

    has_diag = any(s.type == SegmentType.DIAGRAM for s in segs)
    print(f"\nImmediate Vector Art Ready: {has_diag}")

if __name__ == "__main__":
    run()
