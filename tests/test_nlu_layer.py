"""
NLU Layer Tests
Tests for text normalization, shorthand expansion, typo correction,
entity extraction, and ambiguity clarification prompts.

Run:
    python -m pytest tests/test_nlu_layer.py -v
"""

import sys
from pathlib import Path

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.nlu.ambiguity_detector import AmbiguityDetector
from core.nlu.entity_extractor import EntityExtractor
from core.nlu.nlu_engine import NLUEngine


@pytest.fixture
def nlu_engine():
    return NLUEngine()


# ── 1. Text Normalization & Typo Tests ─────────────────────────────────────────


def test_nlu_shorthand_and_typo_correction(nlu_engine):
    """
    Test shorthand expansion and typo correction:
    'opn chrome' → 'open Google Chrome'
    'open google chorme' → 'open Google Chrome'
    'wat is the weather today' → 'what is the weather today'
    """
    res1 = nlu_engine.process("opn chrome")
    assert "open" in res1.normalized_text.lower()
    assert res1.entities.get("app_name") == "Google Chrome"

    res2 = nlu_engine.process("open google chorme")
    assert res2.entities.get("app_name") == "Google Chrome"

    res3 = nlu_engine.process("wat is the weather today")
    assert "what is" in res3.normalized_text.lower()
    assert res3.entities.get("search_query") is not None


def test_nlu_conversational_phrasing(nlu_engine):
    """
    Test conversational & polite phrasing removal:
    'can u open my project folder' → 'my project folder'
    'please show me files in desktop' → 'show me files in desktop'
    """
    res1 = nlu_engine.process("can u open my project folder")
    assert res1.entities.get("directory") == "Project"

    res2 = nlu_engine.process("show me files in desktop")
    assert res2.entities.get("directory") == "Desktop"


# ── 2. Entity Extraction Tests ─────────────────────────────────────────────────


def test_entity_extraction_app_names():
    extractor = EntityExtractor()
    assert extractor.extract_entities("open notepad")["app_name"] == "Notepad"
    assert extractor.extract_entities("launch vscode")["app_name"] == "Visual Studio Code"
    assert extractor.extract_entities("bring chrome to front")["app_name"] == "Google Chrome"


def test_entity_extraction_file_paths():
    extractor = EntityExtractor()
    res1 = extractor.extract_entities("analyze the code in src/core/backends/adapters/antigravity_backend.py")
    assert res1.get("file_path") == "src/core/backends/adapters/antigravity_backend.py"


def test_entity_extraction_search_queries():
    extractor = EntityExtractor()
    res1 = extractor.extract_entities("search for quantum computing papers")
    assert "quantum computing" in res1.get("search_query", "").lower()


# ── 3. Ambiguity Detection & Clarification Prompt Tests ───────────────────────


def test_ambiguity_detection_for_destructive_action_without_target(nlu_engine):
    """
    'delete this file plz' with no specified target file must trigger is_ambiguous=True
    and return a structured clarification_prompt.
    """
    res = nlu_engine.process("delete this file plz")
    assert res.is_ambiguous is True, (
        f"Destructive action without target file must be marked ambiguous. Got: {res}"
    )
    assert res.clarification_prompt is not None
    assert "Which specific file" in res.clarification_prompt


def test_ambiguity_detection_unclear_generic_action(nlu_engine):
    """
    Generic commands like 'close app' without specifying an app name should prompt for clarification.
    """
    res = nlu_engine.process("close app")
    assert res.is_ambiguous is True
    assert "Which application" in res.clarification_prompt


def test_non_ambiguous_specific_action(nlu_engine):
    """
    Specific commands like 'open chrome' should NOT be marked ambiguous.
    """
    res = nlu_engine.process("open chrome")
    assert res.is_ambiguous is False
    assert res.entities.get("app_name") == "Google Chrome"


# ── 4. Architectural Boundaries Test ──────────────────────────────────────────


def test_nlu_does_not_execute_actions(nlu_engine):
    """
    NLUResult should contain only perception data (text, entities, confidence),
    never execution state or plan DAGs.
    """
    res = nlu_engine.process("opn chrome")
    assert hasattr(res, "normalized_text")
    assert hasattr(res, "entities")
    assert not hasattr(res, "execute")
    assert not hasattr(res, "task_graph")
