import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

from Memory import Memory
from brain.conversation_engine import ConversationEngine
from brain.intent_router import IntentRouter

m = Memory()
ce = ConversationEngine(m, None)

for q in ["start listening", "voice listening status", "stop listening"]:
    intent = ce.intent_router.detect(q)
    resp = ce._answer_local_intent(intent)
    print(f"[{q}] -> Intent: {intent.name} ({intent.data}) -> Response: {repr(resp)}")
