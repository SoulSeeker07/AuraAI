import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))
from brain.intent_router import IntentRouter
from Memory import Memory

mem = Memory()
router = IntentRouter(mem)

phrases = [
    "show weather hud",
    "toggle weather overlay",
    "open weather widget",
    "show system hud",
    "toggle system overlay",
    "open resource monitor",
    "open tasks widget",
    "show tasks overlay",
    "toggle chat overlay",
    "open chat hud",
]

for p in phrases:
    norm = p.lower().strip()
    print(f"Phrase: '{p}' | _asks_for_hud_overlay: {router._asks_for_hud_overlay(norm)}")
    intent = router.detect(p)
    print(f"  -> Intent: {intent.name}")
