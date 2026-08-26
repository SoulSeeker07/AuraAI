import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

from Memory import Memory
from src.brain.conversation_engine import ConversationEngine

m = Memory()
class MockPM:
    pass

ce = ConversationEngine(m, MockPM())

t1 = "remember that my favorite programming language is Python"
intent1 = ce.intent_router.detect(t1)
res1 = ce._answer_local_intent(intent1)
print("Query 1:", t1)
print("Intent 1:", intent1.name)
print("Answer 1:", res1)
print("-" * 50)

t2 = "what is my favorite programming language"
intent2 = ce.intent_router.detect(t2)
res2 = ce._answer_local_intent(intent2)
print("Query 2:", t2)
print("Intent 2:", intent2.name)
print("Answer 2:", res2)
print("-" * 50)

t3 = "close weather hud"
intent3 = ce.intent_router.detect(t3)
res3 = ce._answer_local_intent(intent3)
print("Query 3:", t3)
print("Intent 3:", intent3.name, intent3.data)
print("Answer 3:", res3)
print("-" * 50)

t4 = "open weather hud"
intent4 = ce.intent_router.detect(t4)
res4 = ce._answer_local_intent(intent4)
print("Query 4:", t4)
print("Intent 4:", intent4.name, intent4.data)
print("Answer 4:", res4)
