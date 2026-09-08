import os
import sys
import time
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.insert(0, "src")

# Configure UTF-8 encoding for Windows console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Enforce visible browser window
os.environ["AURA_BROWSER_HEADLESS"] = "false"

from browser.run_browser_goal import run_browser_goal, format_for_chat
from browser.browser_session import BrowserSession

def main():
    print("=" * 85)
    print("      AURA AI: LIVE AUTONOMOUS BROWSING BENCHMARK (AMAZON.IN CART)")
    print("=" * 85)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"AURA_BROWSER_HEADLESS: {os.environ.get('AURA_BROWSER_HEADLESS')}")
    print("VISIBLE MODE: True (Active browser window at 1280x850 on screen)")
    print("=" * 85 + "\n", flush=True)

    goal = "Open amazon.in and add samsung 45w charger to cart"
    print(f">>> OBJECTIVE: {goal}\n", flush=True)

    t0 = time.perf_counter()
    try:
        result = run_browser_goal(goal=goal, max_steps=15)
        total_dur = time.perf_counter() - t0

        print("\n" + "=" * 85)
        print(f"RUN COMPLETED: Status = {result.get('status')} | Total Time = {total_dur:.2f}s")
        print("=" * 85)
        print(f"Final URL: {result.get('url')}")
        if result.get("screenshot_path"):
            print(f"Verification Screenshot: {result.get('screenshot_path')}")

        steps = result.get("steps", [])
        print("\n" + "-" * 85)
        print(f"{'STEP':<6} | {'TOOL':<18} | {'LLM LATENCY':<12} | {'TOOL LATENCY':<12} | {'STEP TOTAL':<10} | {'ARGS / DETAILS'}")
        print("-" * 85)

        total_llm_time = 0.0
        total_tool_time = 0.0

        for s in steps:
            step_idx = s.get("step", 0)
            tool = s.get("tool", "")
            llm_lat = s.get("llm_latency_s", 0.0)
            tool_lat = s.get("tool_latency_s", 0.0)
            step_tot = s.get("total_step_s", llm_lat + tool_lat)
            args_str = str(s.get("args", {}))
            if len(args_str) > 35:
                args_str = args_str[:32] + "..."

            total_llm_time += llm_lat
            total_tool_time += tool_lat

            print(f"Step {step_idx:<2} | {tool:<18} | {llm_lat:>8.2f}s    | {tool_lat:>8.2f}s    | {step_tot:>6.2f}s    | {args_str}")

        print("-" * 85)
        print(f"TOTALS | {'All Steps':<18} | {total_llm_time:>8.2f}s    | {total_tool_time:>8.2f}s    | {total_dur:>6.2f}s    | End-to-end execution")
        print("=" * 85 + "\n")

        print("Agent Summary:")
        print(result.get("summary", "No summary provided"))
        print("=" * 85)
        print("\n[ACTIVE BROWSER PRESERVED]: The browser window is left OPEN on your desktop.")
        print("You can view your shopping cart, verify the item, and proceed to checkout.")
        print("=" * 85, flush=True)

        # Keep session alive on screen so Windows does not kill the browser window
        try:
            sleep_sec = int(os.getenv("TEST_KEEP_ALIVE", "15"))
            if sleep_sec > 0:
                print(f"Keeping browser open on screen for {sleep_sec}s...")
                time.sleep(sleep_sec)
        except KeyboardInterrupt:
            pass

    except Exception as e:
        total_dur = time.perf_counter() - t0
        print(f"\n[ERROR] Autonomous run failed after {total_dur:.2f}s: {e}", flush=True)

if __name__ == "__main__":
    main()
