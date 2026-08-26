import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv(repo_root / ".env")

from src.codeact.drafters import GroqDrafter
from src.codeact.executor import DynamicCodeActExecutor
from src.codeact.models import CodeActRequest

def run_live_eval_sweep():
    tasks = [
        {
            "id": "Task 5 (Repeat Run 2)",
            "goal": "Create a comprehensive markdown document with a Python cheat sheet including code blocks and explanations",
            "output": "python_cheatsheet_r2.md"
        },
        {
            "id": "Variant A (API Reference Guide)",
            "goal": "Generate an API reference markdown guide for a REST service with code snippets in python and bash, an endpoints table, and JSON response examples",
            "output": "api_reference_guide.md"
        },
        {
            "id": "Variant B (Linux Troubleshooting Playbook)",
            "goal": "Create a Markdown troubleshooting playbook for Linux system errors with bash commands, log outputs, and configuration snippets",
            "output": "troubleshooting_playbook.md"
        }
    ]

    drafter = GroqDrafter()
    executor = DynamicCodeActExecutor(drafter=drafter)

    print("=== STARTING MULTI-GOAL LIVE CODEACT SWEEP ===")
    results = []

    for task in tasks:
        print(f"\n--- Running: {task['id']} ---")
        print(f"Goal: {task['goal']}")
        req = CodeActRequest(
            goal=task["goal"],
            output_filename=task["output"],
            max_repair_attempts=3,
            max_static_retries=2,
        )
        res = executor.run(req)
        print(f"Status: {res.status} | Attempts: {len(res.attempts)} | Duration: {res.attempts[0].duration_ms if res.attempts else 'N/A'}ms")
        if res.output_path and res.output_path.exists():
            content = res.output_path.read_text(encoding="utf-8")
            print(f"Output File: {res.output_path.name} ({len(content)} chars, {len(content.splitlines())} lines)")
            print("Preview first 5 lines:")
            print("\n".join(content.splitlines()[:5]))
        results.append((task["id"], res))

    print("\n=== SUMMARY OF LIVE RUNS ===")
    for tid, r in results:
        att = len(r.attempts)
        print(f"• {tid}: Status={r.status}, Attempts={att}, Error={r.final_error}")

if __name__ == "__main__":
    run_live_eval_sweep()
