"""
tests/flight_search_test.py

Runs real flight search goal through AuraAI AutonomousBrowserEngine & GroqVisionLoop.
Goal: Find cheapest one-way flight from Bengaluru (BLR) to Mangalore (IXE) on Google Flights.
"""

import sys, os, time, json
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC  = ROOT / "src"
for p in (str(SRC), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(ROOT / ".env")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from browser.vision_loop import GroqVisionLoop
from ai.key_pool import KeyPool

SEP = "=" * 68
GOAL = (
    "Find the cheapest one-way flight from Bengaluru (BLR) to Mangalore on Google Flights. "
    "Read the flight options visible on screen, report the cheapest airline name, flight duration, "
    "and cost in INR, then conclude with action done."
)
START_URL = "https://www.google.com/travel/flights?q=Flights+from+Bengaluru+BLR+to+Mangalore+IXE+one+way"

print(f"\n{SEP}")
print("  AURAAI REAL FLIGHT SEARCH TEST")
print(f"{SEP}")
print(f"Goal   : {GOAL}")
print(f"Start  : {START_URL}")

pool = KeyPool.get_instance()
print(f"Pool   : {pool.count('groq')} active Groq keys")
print(f"{SEP}\n")

loop = GroqVisionLoop()
t0 = time.time()

result = loop.run(
    goal=GOAL,
    start_url=START_URL,
    audit_ledger=[],
    max_steps=5,
)

elapsed = time.time() - t0
print(f"\n{SEP}")
print(f"STATUS   : {result.get('status')}")
print(f"URL      : {result.get('url')}")
print(f"TITLE    : {result.get('title')}")
print(f"ELAPSED  : {elapsed:.1f}s")
print(f"ACTIONS  : {len(result.get('actions', []))} recorded")
print(f"\nSUMMARY / MESSAGE:\n{result.get('summary')}")
print(f"{SEP}\n")
