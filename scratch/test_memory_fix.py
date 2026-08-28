import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import re
from Memory import Memory, MemoryFact
from brain.intent_router import IntentRouter
from brain.conversation_engine import ConversationEngine

m = Memory()
router = IntentRouter(m)

queries = [
    "remember that my favorite programming language is Python",
    "what is my favorite programming language",
    "close weather hud",
    "hide weather overlay",
    "open weather hud",
    "show personal os dashboard",
    "close personal os dashboard"
]

print("--- TESTING INTENT ROUTER ---")
for q in queries:
    intent = router.detect(q)
    print(f"Query: '{q}' -> Intent: {getattr(intent, 'name', None)}, data: {getattr(intent, 'data', None)}")
