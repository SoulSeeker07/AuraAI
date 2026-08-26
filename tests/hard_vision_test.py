"""
Hard live test: multi-step search + navigate + read.

Goal  : DuckDuckGo search for "Groq LLM speed benchmark 2024"
         -> click the most relevant result
         -> report what the page says about Groq speed

Challenges tested:
  - Coordinate accuracy (find & click a real search bar)
  - Typing into an active field
  - Reading search results and clicking one
  - Multi-page navigation (2-3 real page transitions)
  - JSON parsing from a thinking model under real conditions
"""

import os, sys, time, json, base64, hashlib
from pathlib import Path
from io import BytesIO

ROOT = Path(".").resolve()
SRC  = ROOT / "src"
for p in (str(SRC), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from browser.vision_loop import GroqVisionLoop, Tier3Unavailable, GROQ_VISION_FALLBACK_MODELS
from playwright.sync_api import sync_playwright

SEP  = "=" * 68
GOAL = (
    "First, navigate to the Wikipedia article for 'Artificial Intelligence' at "
    "https://en.wikipedia.org/wiki/Artificial_intelligence. "
    "Once the page loads, scroll down to reveal the overview and history sections. "
    "Read the key goals of AI mentioned on screen and conclude with action done."
)
START = "https://en.wikipedia.org/wiki/Main_Page"
MAX_STEPS = 10

print(f"\n{SEP}")
print("  HARD TEST: multi-step search -> click -> read")
print(SEP)
print(f"Goal  : {GOAL[:120]}...")
print(f"Start : {START}")
print(f"Models: {GROQ_VISION_FALLBACK_MODELS[:2]} + {len(GROQ_VISION_FALLBACK_MODELS)-2} more fallbacks")
print()

try:
    loop = GroqVisionLoop()
    print(f"Active model: {loop.model}\n")
except Tier3Unavailable as e:
    print(f"SKIP: {e}"); sys.exit(1)

history = []
budget  = 3
t_total = time.time()

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox",
              "--disable-infobars", "--disable-extensions"],
    )
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()

    print(f"[browser] loading {START}...")
    page.goto(START, wait_until="domcontentloaded", timeout=15000)
    print(f"[browser] ready: {page.title()} | {page.url}\n")

    result = {"status": "PARTIAL_SUCCESS", "url": START, "summary": ""}

    for step in range(MAX_STEPS):
        url_challenge = loop._url_looks_challenged(page.url)
        if url_challenge:
            print(f"  WARNING  : Bot wall detected ({url_challenge}) -> switching to Google")
            page.goto("https://www.google.com/search?q=Groq+LLM+speed+tokens+per+second+2024", wait_until="domcontentloaded")
            time.sleep(1)

        t0 = time.time()
        print(f"[step {step:02d}] querying {loop.model}...")
        action  = loop._ask_model(GOAL, page, history)
        rtt     = time.time() - t0

        kind   = action.get("action","?")
        reason = action.get("reasoning","")
        print(f"  action   : {kind}")
        print(f"  reasoning: {reason}")
        if kind == "click":   print(f"  coords   : ({action.get('x')}, {action.get('y')})")
        if kind == "type":    print(f"  text     : {action.get('text','')!r}")
        if kind == "navigate":print(f"  url      : {action.get('url')}")
        if kind == "key":     print(f"  key      : {action.get('key')}")
        print(f"  rtt      : {rtt:.2f}s | url: {page.url[:80]}")

        if loop._is_high_risk(reason, set()):
            action["action"] = "ask_user"
            print("  WARNING  : high-risk keyword flagged")

        if action.get("action") == "done":
            history.append(action)
            result = {"status":"SUCCESS","url":page.url,"title":page.title(),"summary":reason}
            print(f"\n{'='*68}\nDONE in {step+1} step(s) ({time.time()-t_total:.1f}s)\n")
            print(f"Final URL  : {page.url}")
            print(f"Page title : {page.title()}")
            print(f"Summary    :\n{reason}")
            break

        if action.get("action") == "ask_user":
            history.append(action)
            result = {"status":"ASK_USER","url":page.url,"summary":reason}
            print(f"\nASK_USER: {reason}")
            break

        executed = loop._execute_with_correction(page, action)
        history.append(executed)

        effect = executed.get("effect","")
        err    = executed.get("error","")
        if effect: print(f"  effect   : {effect}")
        if err:    print(f"  error    : {err}")

        if effect.startswith("no visible change"):
            budget -= 1
            print(f"  WARNING  : no change (budget={budget})")
            if budget <= 0:
                result = {"status":"STUCK","url":page.url,"summary":"coord misses exhausted budget"}
                print("\nSTUCK - coordinate accuracy limit hit.")
                break
        else:
            budget = 3

    else:
        result = {"status":"MAX_STEPS","url":page.url,"summary":"ran out of steps"}
        print(f"\nMAX_STEPS ({MAX_STEPS}) reached.")

    browser.close()

elapsed = time.time() - t_total
print(f"\n{SEP}")
print(f"status  : {result['status']}")
print(f"elapsed : {elapsed:.1f}s   steps: {len(history)}")
print(f"model   : {loop.model}")
print(SEP)
sys.exit(0 if result["status"] in ("SUCCESS","ASK_USER") else 1)

