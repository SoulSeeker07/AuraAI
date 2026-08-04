import sys
import os
sys.path.insert(0, os.getcwd())

from core.memory.memory_manager import MemoryManager
from Memory import Memory

print("Creating fresh memory...")
memory = Memory()
manager = MemoryManager(memory=memory)

print("\nStoring messages with topic field...")
memory.remember_exchange("Let's discuss networking.", "Sure!", "General")
memory.remember_exchange("Question 1", "Answer 1", "Networking")
memory.remember_exchange("Switch topic.", "What's next?", "General")
memory.remember_exchange("Let's discuss Python.", "Great!", "Python")

print("\nGetting recent messages...")
messages = manager.get_recent_messages(limit=10)

print(f"\nTotal messages: {len(messages)}")
for i, msg in enumerate(messages):
    print(f"Message {i}: role={msg.get('role')}, topic={msg.get('topic')[:20] if msg.get('topic') else 'None'}")

print(f"\nFinding Python messages...")
python_messages = [m for m in messages if m.get('topic') == 'Python']
print(f"Python messages found: {len(python_messages)}")

if python_messages:
    print(f"First Python message: {python_messages[0]}")
else:
    print("ERROR: No Python messages found!")
    print(f"All topics: {[m.get('topic') for m in messages]}")
