"""
Aura AI EIP (Error In Production) Test

This test simulates:
1. Aura generates code with a bug
2. We run the buggy code and confirm it fails
3. Aura fixes the bug
4. We run the fixed code and confirm it works
5. Report results to user
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))


def main():
    from Chatbot import ChatBot

    print("=" * 80)
    print("🧪 AURA AI EIP (ERROR IN PRODUCTION) TEST")
    print("=" * 80)
    print()

    chatbot = ChatBot()
    print(f"✅ ChatBot initialized with: {chatbot.provider_name} / {chatbot.model}")
    print()

    # Step 1: Generate buggy code
    print("-" * 80)
    print("STEP 1: ASKING AURA TO GENERATE CODE WITH A BUG")
    print("-" * 80)
    print()

    buggy_request = """
Please write a Python function to calculate the sum of numbers in a list.
Include a test case. Add a common bug that beginners make.

Generate the complete code including a main block.
"""

    response1 = chatbot.ask(buggy_request)
    print("📄 Generated Code:")
    print("=" * 80)
    print(response1)
    print("=" * 80)
    print()

    # Step 2: Run buggy code and capture error
    print("-" * 80)
    print("STEP 2: RUNNING BUGGY CODE")
    print("-" * 80)
    print()

    # Extract code from markdown if Aura includes ```python markers
    if response1.strip().startswith("```"):
        # Split by ```python and take everything after the first marker
        parts = response1.split("```python")
        if len(parts) > 1:
            buggy_code = parts[1].split("```")[0].strip()
        else:
            # Try without python keyword
            parts = response1.split("```")
            if len(parts) > 1:
                buggy_code = parts[1].split("```")[0].strip()
            else:
                buggy_code = response1.strip()
    else:
        buggy_code = response1.strip()

    buggy_file = PROJECT_ROOT / "dev" / "scratch" / "buggy_code.py"
    buggy_file.parent.mkdir(parents=True, exist_ok=True)
    with open(buggy_file, "w", encoding="utf-8") as f:
        f.write(buggy_code)

    print(f"💾 Code saved to {buggy_file}")
    print("🔄 Running buggy code...")
    print("=" * 80)

    result = subprocess.run(
        [sys.executable, str(buggy_file)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    print(result.stdout)
    if result.stderr:
        print("\n❌ ERROR OUTPUT:")
        print(result.stderr)

    print("=" * 80)
    print()

    # Step 3: Ask Aura to fix the bug
    print("-" * 80)
    print("STEP 3: ASKING AURA TO FIX THE BUG")
    print("-" * 80)
    print()

    fix_request = """
I ran the code above and got an error. Please:
1. Identify the bug
2. Fix it
3. Generate the corrected code with comments explaining the fix

Only provide the fixed code, no explanations.
"""

    response2 = chatbot.ask(fix_request)
    print("📄 Fixed Code:")
    print("=" * 80)
    print(response2)
    print("=" * 80)
    print()

    # Step 4: Run fixed code
    print("-" * 80)
    print("STEP 4: RUNNING FIXED CODE")
    print("-" * 80)
    print()

    # Extract code from markdown if Aura includes ```python markers
    if response2.strip().startswith("```"):
        # Split by ```python and take everything after the first marker
        parts = response2.split("```python")
        if len(parts) > 1:
            fixed_code = parts[1].split("```")[0].strip()
        else:
            # Try without python keyword
            parts = response2.split("```")
            if len(parts) > 1:
                fixed_code = parts[1].split("```")[0].strip()
            else:
                fixed_code = response2.strip()
    else:
        fixed_code = response2.strip()

    fixed_file = PROJECT_ROOT / "dev" / "scratch" / "fixed_code.py"
    fixed_file.parent.mkdir(parents=True, exist_ok=True)
    with open(fixed_file, "w", encoding="utf-8") as f:
        f.write(fixed_code)

    print(f"💾 Code saved to {fixed_file}")
    print("🔄 Running fixed code...")
    print("=" * 80)

    result2 = subprocess.run(
        [sys.executable, str(fixed_file)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    print(result2.stdout)
    if result2.stderr:
        print("\n❌ ERROR OUTPUT:")
        print(result2.stderr)

    print("=" * 80)
    print()

    # Step 5: Report results
    print("=" * 80)
    print("📊 TEST RESULTS REPORT")
    print("=" * 80)
    print()

    if result.returncode != 0:
        print("❌ BUGGY CODE FAILED:")
        print(f"   Exit Code: {result.returncode}")
        print(f"   Error: {result.stderr.strip()}")
        print()
        print("✅ Test PASSED - Bug detected successfully!")
    else:
        print("❌ UNEXPECTED - Buggy code ran successfully")
        print()

    print("✅ FIXED CODE:")
    if result2.returncode == 0:
        print(f"   Exit Code: {result2.returncode}")
        print("   ✅ CODE EXECUTED SUCCESSFULLY!")
    else:
        print(f"   Exit Code: {result2.returncode}")
        print(f"   Error: {result2.stderr.strip()}")
        print("   ❌ CODE STILL HAS ERRORS")

    print()
    print("=" * 80)
    print("🎯 CONCLUSION")
    print("=" * 80)

    if result.returncode != 0 and result2.returncode == 0:
        print("✅ AURA AI PASSED THE EIP TEST!")
        print()
        print("Summary:")
        print("  1. ✅ Generated buggy code")
        print("  2. ✅ Confirmed bug existed (code failed)")
        print("  3. ✅ Identified and fixed the bug")
        print("  4. ✅ Fixed code runs successfully")
    else:
        print("❌ AURA AI DID NOT COMPLETE TEST")
        print()
        print("Please check the results above")

    print("=" * 80)


if __name__ == "__main__":
    main()
