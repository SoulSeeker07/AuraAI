"""
Unit tests for CapabilityDiscoveryMatcher.
Verifies word-boundary enforcement, token-length precedence, tier hierarchy, and deterministic tie-breaking.
"""

from unittest.mock import MagicMock
import logging
from src.desktop.native.capability_matcher import CapabilityDiscoveryMatcher, tokenize
from src.desktop.native.capability_registry import CapabilityDescriptor, CapabilityRegistry


def test_tokenize_basic():
    """Verify string normalization and punctuation stripping."""
    assert tokenize("Read text from clipboard!") == ["read", "text", "from", "clipboard"]
    assert tokenize("open_app (notepad) - NOW") == ["open", "app", "notepad", "now"]
    assert tokenize("") == []
    assert tokenize(None) == []


def test_word_boundary_enforcement():
    """Verify substrings do not match across token boundaries (e.g. commute != mute)."""
    matcher = CapabilityDiscoveryMatcher()

    # 'commute' contains 'mute' as a substring, but token is 'commute' -> must NOT match toggle_mute
    assert matcher.match("daily commute to work") is None

    # 'mute' as exact token matches toggle_mute
    assert matcher.match("please mute system sound") == "toggle_mute"
    assert matcher.match("mute") == "toggle_mute"


def test_token_length_precedence():
    """Verify longer matching token sequences beat shorter generic matches."""
    matcher = CapabilityDiscoveryMatcher()

    # 4 tokens: 'read text from clipboard' -> clipboard.read_text
    assert matcher.match("could you read text from clipboard please") == "clipboard.read_text"

    # 2 tokens: 'clear clipboard' -> clipboard.clear
    assert matcher.match("clear clipboard now") == "clipboard.clear"

    # 4 tokens: 'copy text to clipboard' -> clipboard.write_text
    assert matcher.match("copy text to clipboard") == "clipboard.write_text"


def test_curated_tier1_beats_registry_tier2():
    """Verify curated keyword dictionary (Tier 1) takes precedence over registry descriptors (Tier 2)."""
    mock_registry = MagicMock()
    desc = CapabilityDescriptor(
        name="custom.clipboard_override",
        description="Custom handler",
        manager="CustomManager",
        category="custom",
        usage_examples=["read text from clipboard and do something complex"],
    )
    mock_registry.list_all.return_value = [desc]

    matcher = CapabilityDiscoveryMatcher(registry=mock_registry)

    # Even though registry has a 7-token usage_example, curated phrase in Tier 1 matches first
    result = matcher.match("read text from clipboard")
    assert result == "clipboard.read_text"


def test_registry_tier2_fallback_when_tier1_misses():
    """Verify registry fallback (Tier 2) is used when curated dictionary has no match."""
    mock_registry = MagicMock()
    desc = CapabilityDescriptor(
        name="custom.special_dock_action",
        description="Dock special utility",
        manager="CustomManager",
        category="dock",
        usage_examples=["dock special utility"],
    )
    mock_registry.list_all.return_value = [desc]

    matcher = CapabilityDiscoveryMatcher(registry=mock_registry)

    # Not in curated dictionary, but in registry usage_examples
    result = matcher.match("dock special utility")
    assert result == "custom.special_dock_action"


def test_deterministic_tie_breaking_keyword_coverage():
    """Verify 100% keyword coverage beats partial keyword match of equal matched length."""
    custom_keywords = {
        "short_exact": ["read text"],
        "long_partial": ["read text in browser window"],
    }
    matcher = CapabilityDiscoveryMatcher(curated_keywords=custom_keywords)

    # Goal matches 2 tokens against both, but short_exact has 100% coverage (2/2) vs long_partial (2/4)
    assert matcher.match("read text") == "short_exact"


def test_deterministic_tie_breaking_namespace_affinity():
    """Verify namespace token in goal breaks ties when token length and coverage are identical."""
    custom_keywords = {
        "clipboard.read": ["read content"],
        "display.read": ["read content"],
    }
    matcher = CapabilityDiscoveryMatcher(curated_keywords=custom_keywords)

    # Goal has 'clipboard' token -> clipboard.read wins
    assert matcher.match("read content from clipboard") == "clipboard.read"

    # Goal has 'display' token -> display.read wins
    assert matcher.match("read content on display") == "display.read"


def test_deterministic_tie_breaking_alphabetical_fallback(caplog):
    """Verify pure tie falls back to deterministic alphabetical sort and logs debug trace."""
    custom_keywords = {
        "zebra.action": ["execute operation"],
        "alpha.action": ["execute operation"],
    }
    matcher = CapabilityDiscoveryMatcher(curated_keywords=custom_keywords)

    with caplog.at_level(logging.DEBUG):
        result = matcher.match("please execute operation")
        assert result == "alpha.action"
        assert any("Deterministic tie-break" in record.message for record in caplog.records)
