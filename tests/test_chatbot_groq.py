"""Test ChatBot with GROQ API"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from Chatbot import ChatBot

print("🧪 Testing ChatBot with GROQ API")
print("=" * 70)
print()

try:
    # Create ChatBot instance
    print("Creating ChatBot instance...")
    chatbot = ChatBot()
    print("✅ ChatBot created successfully!")
    print()
    
    # Get configuration info
    print("📊 Configuration:")
    print(f"   Provider: {chatbot.provider_name}")
    print(f"   Model: {chatbot.model}")
    print(f"   Username: {chatbot.username}")
    print(f"   Assistant Name: {chatbot.assistant_name}")
    print()
    
    # Test a simple query
    print("🤖 Testing query: 'Write a Python function for Fibonacci'")
    print()
    
    response = chatbot.ask("Write a Python function for Fibonacci")
    
    print("✅ Response received!")
    print()
    print("=" * 70)
    print("ANSWER:")
    print("=" * 70)
    print(response)
    print("=" * 70)
    print()
    
    print("✅ ChatBot test completed successfully!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("📝 Troubleshooting:")
    print("   - Check that GROQ_API_KEY is set in .env file")
    print("   - Check that GROQ_API_KEY is valid")
    print("   - Check your internet connection")
