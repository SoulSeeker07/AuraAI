import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))
from brain.intent_router import IntentRouter
from Memory import Memory
mem = Memory()
router = IntentRouter(mem)

hud_test_phrases = [
    "open weather hud",
    "show weather hud",
    "toggle weather overlay",
    "open weather widget",
    "open system monitor",
    "show system hud",
    "toggle system overlay",
    "open resource monitor",
    "open hardware monitor",
    "open tasks widget",
    "show tasks overlay",
    "open personal os",
    "open personal os dashboard",
    "open jarvis rings",
    "toggle chat overlay",
    "open chat hud",
]

for p in hud_test_phrases:
    intent = router.detect(p)
    print(f"'{p}' -> {intent.name} (data: {intent.data})")
