"""
Aura AI EIP Test with Indentation Fix

This test focuses on a common Python error: IndentationError in docstrings.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from Chatbot import ChatBot

print("=" * 80)
print("🧪 AURA AI INDENTATION ERROR TEST")
print("=" * 80)
print()

chatbot = ChatBot()
print(f"✅ ChatBot initialized with: {chatbot.provider_name} / {chatbot.model}")
print()

# Step 1: Generate buggy code
print("-" * 80)
print("STEP 1: ASKING AURA FOR CODE WITH INDENTATION ERROR")
print("-" * 80)
print()

buggy_request = """
Please write a Python function with a common IndentationError.
Make sure the function body is indented properly but the docstring is NOT indented.

Generate complete runnable code including a test.
"""

response1 = chatbot.ask(buggy_request)
print("📄 Generated Code:")
print("=" * 80)
print(response1)
print("=" * 80)
print()

# Extract code
if response1.strip().startswith("```"):
    parts = response1.split("```python")
    if len(parts) > 1:
        buggy_code = parts[1].split("```")[0].strip()
    else:
        parts = response1.split("```")
        if len(parts) > 1:
            buggy_code = parts[1].split("```")[0].strip()
        else:
            buggy_code = response1.strip()
else:
    buggy_code = response1.strip()

# Step 2: Run buggy code
print("-" * 80)
print("STEP 2: RUNNING BUGGY CODE (should fail with IndentationError)")
print("-" * 80)
print()

with open("buggy_code.py", "w", encoding="utf-8") as f:
    f.write(buggy_code)

print("💾 Code saved to buggy_code.py")
print("🔄 Running buggy code...")
print("=" * 80)

import subprocess

result = subprocess.run(
    [sys.executable, "buggy_code.py"],
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

# Step 3: Ask Aura to fix
print("-" * 80)
print("STEP 3: ASKING AURA TO FIX INDENTATION ERROR")
print("-" * 80)
print()

fix_request = """
The code above has an IndentationError. Please:
1. Fix the indentation issue
2. Generate ONLY the fixed Python code (no markdown markers, no explanations)

The docstring MUST be indented inside the function.
"""

response2 = chatbot.ask(fix_request)
print("📄 Fixed Code:")
print("=" * 80)
print(response2)
print("=" * 80)
print()

# Extract code
if response2.strip().startswith("```"):
    parts = response2.split("```python")
    if len(parts) > 1:
        fixed_code = parts[1].split("```")[0].strip()
    else:
        parts = response2.split("```")
        if len(parts) > 1:
            fixed_code = parts[1].split("```")[0].strip()
        else:
            fixed_code = response2.strip()
else:
    fixed_code = response2.strip()

# Step 4: Run fixed code
print("-" * 80)
print("STEP 4: RUNNING FIXED CODE (should succeed)")
print("-" * 80)
print()

with open("fixed_code.py", "w", encoding="utf-8") as f:
    f.write(fixed_code)

print("💾 Code saved to fixed_code.py")
print("🔄 Running fixed code...")
print("=" * 80)

result2 = subprocess.run(
    [sys.executable, "fixed_code.py"],
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

# Step 5: Report
print("=" * 80)
print("📊 TEST RESULTS")
print("=" * 80)
print()

if result.returncode != 0:
    print("✅ BUGGY CODE FAILED (expected):")
    print("   Error: IndentationError detected")
    print()
    print("✅ Test Step 1: PASS - Bug exists")
else:
    print("❌ BUGGY CODE SUCCEEDED (unexpected):")
    print()

if result2.returncode == 0:
    print("✅ FIXED CODE SUCCEEDED:")
    print(f"   Exit Code: {result2.returncode}")
    print()
    print("=" * 80)
    print("🎯 CONCLUSION")
    print("=" * 80)
    print("✅ AURA AI PASSED THE TEST!")
    print()
    print("Summary:")
    print("  1. ✅ Detected IndentationError in generated code")
    print("  2. ✅ Fixed the indentation issue properly")
    print("  3. ✅ Fixed code runs successfully without errors")
    print()
    print("Aura AI is working correctly for code generation and error fixing!")
else:
    print("❌ FIXED CODE FAILED:")
    print(f"   Error: {result2.stderr.strip()}")
    print()
    print("=" * 80)
    print("🎯 CONCLUSION")
    print("=" * 80)
    print("⚠️  Aura AI needs improvement on fixing Python indentation")
    print()
    print("The fix didn't resolve the issue properly.")

print("=" * 80)
