import pytest
from brain.intent_router import IntentRouter
from Memory import Memory

def test_restart_intents_resolve_cleanly():
    """Ensure restart phrases across CLI and GUI resolve to restart_aura."""
    mem = Memory()
    router = IntentRouter(mem)

    restart_phrases = [
        "restart",
        "restart aura",
        "restart aura ai",
        "reboot",
        "reboot aura",
        "restart yourself",
        "restart the app",
        "restart application",
        "reload aura",
        "relaunch aura",
        "restart now",
        "aura restart",
    ]

    for phrase in restart_phrases:
        intent = router.detect(phrase)
        assert intent.name == "restart_aura", (
            f"Phrase '{phrase}' resolved to '{intent.name}' instead of restart_aura"
        )
