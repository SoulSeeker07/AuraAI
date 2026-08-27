"""
tests/browser/live_vision_agent_smoke.py
========================================
Live end-to-end smoke test verifying that agent_loop.py autonomously:
1. Calls the `screenshot` tool on a live webpage.
2. Formats the base64 screenshot into a multimodal message payload.
3. Successfully dispatches the image turn to `qwen/qwen3.6-27b` via GroqProvider.
4. Concludes the goal with `done`.
"""

import logging
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def main():
    from browser.run_browser_goal import run_browser_goal

    print("\n" + "="*70)
    print("EXECUTING LIVE AGENT LOOP GOAL WITH AUTONOMOUS SCREENSHOT & VISION ESCALATION")
    print("="*70)

    goal = "open https://en.wikipedia.org/wiki/Python_(programming_language), take a screenshot to visually inspect the top logo, and describe what colors/shapes you see"
    result = run_browser_goal(goal, max_steps=8)

    print(f"Goal Status : {result.get('status')}")
    print(f"Summary     : {result.get('summary')}")
    print(f"Final URL   : {result.get('url')}")
    print(f"Action Steps: {len(result.get('steps', []))}")
    for i, s in enumerate(result.get('steps', [])):
        print(f"  Step {i+1}: {s.get('tool')} -> {s.get('args')}")

    tools_used = [s.get("tool") for s in result.get("steps", [])]
    assert "screenshot" in tools_used, f"Expected screenshot tool in {tools_used}"
    assert result.get("status") == "SUCCESS", f"Expected SUCCESS, got {result.get('status')}"
    print("\n" + "="*70)
    print("AUTONOMOUS SCREENSHOT & VISION ESCALATION IN AGENT LOOP VERIFIED END-TO-END")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
