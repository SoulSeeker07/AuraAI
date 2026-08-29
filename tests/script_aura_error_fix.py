"""Test Aura's ability to generate buggy code and fix it"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))


def main():
    from Chatbot import ChatBot

    print("🧪 Testing Aura's error detection and fixing")
    print("=" * 70)
    print()

    try:
        chatbot = ChatBot()
        print("✅ ChatBot created")
        print()

        # Ask for code with intentional bug
        buggy_code = """
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)

# Test it
result = factorial(5)
print(f"Factorial of 5 is {result}")
"""

        print("📝 Generating code with potential bug...")
        response = chatbot.ask(buggy_code + "\nDoes this code have any errors?")

        print("✅ Aura's analysis:")
        print("=" * 70)
        print(response)
        print("=" * 70)
        print()

        # Ask for fixed code
        print("📝 Requesting fixed version...")
        fixed_response = chatbot.ask("Please fix any errors in the factorial code above")

        print("✅ Fixed code:")
        print("=" * 70)
        print(fixed_response)
        print("=" * 70)
        print()

        # Save and test the fixed code
        fixed_file = PROJECT_ROOT / "dev" / "scratch" / "test_aura_fixed.py"
        fixed_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"💾 Saving fixed code to {fixed_file}")
        with open(fixed_file, "w", encoding="utf-8") as f:
            f.write(fixed_response)

        print("🚀 Running fixed code...")
        print("=" * 70)
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(fixed_file),
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        print("=" * 70)
        print("✅ Error detection and fixing test completed!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
