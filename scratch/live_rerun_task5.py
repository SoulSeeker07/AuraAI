import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv(repo_root / ".env")

from src.codeact.drafters import GroqDrafter
from src.codeact.executor import DynamicCodeActExecutor
from src.codeact.models import CodeActRequest

def run_task5_live():
    print("=== LIVE CODEACT TASK 5 VERIFICATION ===")
    drafter = GroqDrafter()
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="Create a comprehensive markdown document with a Python cheat sheet including code blocks and explanations",
        output_filename="python_cheatsheet.md",
        max_repair_attempts=3,
        max_static_retries=2,
    )

    print(f"Goal: {req.goal}")
    print(f"Output Filename: {req.output_filename}")
    print("Starting synthesis...")

    result = executor.run(req)

    print("\n=== EXECUTION RESULT ===")
    print(f"Status: {result.status}")
    print(f"Attempts used: {len(result.attempts)}")
    print(f"Output path: {result.output_path}")
    print(f"Final error: {result.final_error}")

    for idx, att in enumerate(result.attempts, start=1):
        print(f"\n--- Attempt {idx} ---")
        print(f"Exit code: {att.exit_code}")
        print(f"Duration ms: {att.duration_ms}")
        print(f"Validation passed: {att.validation_result.passed if att.validation_result else 'N/A'}")
        print("Generated Code:")
        print(att.code)
        if att.stderr:
            print(f"Stderr: {att.stderr}")

    if result.output_path and result.output_path.exists():
        content = result.output_path.read_text(encoding="utf-8")
        print(f"\nGenerated Artifact ({len(content)} chars, {len(content.splitlines())} lines):")
        print("First 30 lines:")
        print("\n".join(content.splitlines()[:30]))

if __name__ == "__main__":
    run_task5_live()
