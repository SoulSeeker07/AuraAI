import os
import sys

sys.path.insert(0, os.getcwd())

from core.memory.memory_manager import MemoryManager
from Memory import Memory

memory = Memory()
manager = MemoryManager(memory=memory)

# Store messages
print("Storing messages...")
memory.remember_exchange(
    "Let's discuss networking.", "Sure! What would you like to know?", "General"
)
memory.remember_exchange(
    "What protocol elects DR and BDR?",
    "In OSPF, the Designated Router (DR) and Backup DR (BDR) are elected using the OSPF Hello protocol.",
    "Networking",
)
memory.remember_exchange("Switch topic.", "What's next?", "General")
memory.remember_exchange(
    "Let's discuss Python.", "Great choice! Python is versatile.", "Python"
)

# Get recent messages
messages = manager.get_recent_messages(limit=5)
print(f"\nTotal messages: {len(messages)}")
if messages:
    print(f"First message: {messages[0]}")
    print(f"First message topic: {messages[0].get('topic')}")
    print(f"First message keys: {messages[0].keys()}")

# Check if topic field is present
for i, msg in enumerate(messages):
    print(f"Message {i} topic: {msg.get('topic')}")

# Check the chat log directly
print("\n--- Checking chat log directly ---")
chat_log = memory.load_chat_log()
print(f"Chat log has {len(chat_log)} messages")
if len(chat_log) >= 5:
    print(f"5th message: {chat_log[-5]}")
