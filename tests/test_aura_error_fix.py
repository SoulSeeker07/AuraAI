"""Test Aura's ability to generate buggy code and fix it"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

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
    print("💾 Saving fixed code to test_aura_fixed.py")
    with open("test_aura_fixed.py", "w", encoding="utf-8") as f:
        f.write(fixed_response)
    
    print("🚀 Running fixed code...")
    print("=" * 70)
    import subprocess
    result = subprocess.run(
        [str(Path(PROJECT_ROOT) / ".venv" / "Scripts" / "python.exe"), "test_aura_fixed.py"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT
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
