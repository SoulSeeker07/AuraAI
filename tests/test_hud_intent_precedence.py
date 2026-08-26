import pytest
from brain.intent_router import IntentRouter
from Memory import Memory

def test_hud_phrases_never_resolve_to_open_file():
    """Ensure HUD overlay commands never get shadowed or misclassified as open_file or file_search."""
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

    for phrase in hud_test_phrases:
        intent = router.detect(phrase)
        assert intent.name in ("hud_overlay", "overlay_toggle"), (
            f"Phrase '{phrase}' was misclassified as '{intent.name}' (data: {intent.data}) instead of hud_overlay"
        )

def test_actual_files_still_resolve_to_open_file():
    """Ensure actual file opening queries continue resolving to open_file."""
    mem = Memory()
    router = IntentRouter(mem)

    file_test_phrases = [
        "open resume.pdf",
        "open report.docx",
        "open notes.txt",
        "open important file",
        "find and open summary.md",
    ]

    for phrase in file_test_phrases:
        intent = router.detect(phrase)
        assert intent.name == "open_file", (
            f"File phrase '{phrase}' was misclassified as '{intent.name}'"
        )
