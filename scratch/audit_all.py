import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))

with open(root / "src/brain/intent_router.py", "r", encoding="utf-8") as f:
    text = f.read()

intents = re.findall(r'Intent\("([^"]+)"', text) + re.findall(r"Intent\('([^']+)'", text)
print("=== UNIQUE INTENTS IN IntentRouter ===")
for i in sorted(set(intents)):
    print(" -", i)

with open(root / "src/brain/conversation_engine.py", "r", encoding="utf-8") as f:
    ce_text = f.read()

ce_matches = re.findall(r'intent\.name\s*(?:==|\bin\b)\s*\(?([^:\n]+)', ce_text)
print("\n=== INTENT CHECKS IN ConversationEngine ===")
for m in ce_matches:
    cleaned = [x.strip(" '\"()") for x in m.split(",") if x.strip(" '\"()")]
    for c in cleaned:
        if c:
            print(" -", c)
