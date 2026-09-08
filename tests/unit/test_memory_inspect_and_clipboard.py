"""
Tests for Memory Inspection Determinism, CapabilityRegistry, & Clipboard Sequence Gating
========================================================================================
Location: tests/unit/test_memory_inspect_and_clipboard.py
"""

import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.context.ambient_context_builder import AmbientContextBuilder
from core.orchestration.decision_engine import DecisionEngine, IntentType
from core.system.system_knowledge_resolver import SystemKnowledgeResolver


def test_memory_inspect_capability_registered():
    """Verify memory.inspect is registered in universal CapabilityRegistry."""
    reg = CapabilityRegistry.get_instance()
    cap = reg.get_capability("memory.inspect")
    assert cap is not None, "memory.inspect capability must be registered"
    assert cap.domain == "memory"
    assert "inspect" in cap.tags
    assert cap.is_live is True


def test_decision_engine_memory_inspect_routing():
    """Verify diverse memory inspection phrases resolve to memory.inspect capability."""
    engine = DecisionEngine()
    test_queries = [
        "inspect active working memory",
        "inspect memory",
        "show working memory",
        "dump memory",
        "view stored facts",
        "list my facts",
        "inspect memory vault",
        "what's in memory",
    ]

    for q in test_queries:
        outcome = engine.evaluate(q)
        assert outcome.intent_type == IntentType.MEMORY, f"Failed on query: {q}"
        assert outcome.capability == "memory.inspect", f"Failed capability on query: {q}"
        assert outcome.needs_planner is False, f"Inspection should not need planner on: {q}"


def test_system_knowledge_resolver_deterministic_memory_snapshot():
    """Verify SystemKnowledgeResolver returns structured memory and task data directly."""
    result = SystemKnowledgeResolver.resolve("inspect active working memory")
    assert "Live Personal OS & Memory Vault" in result
    assert "Stored User Facts & Preferences" in result
    assert "Active Tasks Queue" in result
    assert "Memory Stats" in result


def test_ambient_context_clipboard_sequence_gating():
    """
    Verify clipboard sequence number gating:
    1. When clipboard sequence number matches baseline -> omitted from ambient context
    2. When sequence number increments (user copied something new) -> included with passive framing
    3. When user explicitly asks about clipboard -> included regardless of sequence number
    """
    # 1. Baseline unchanged -> Omitted
    AmbientContextBuilder.reset_clipboard_baseline(force_seq=1000)
    # Mock current sequence to be identical to baseline
    original_get_seq = AmbientContextBuilder._get_current_clipboard_sequence
    AmbientContextBuilder._get_current_clipboard_sequence = classmethod(lambda cls: 1000)
    try:
        ctx_unrelated = AmbientContextBuilder.build_ambient_context(query="what is the weather today?")
        assert "Clipboard Buffer" not in ctx_unrelated
        assert "Clipboard Preview" not in ctx_unrelated

        # 2. Sequence changed (fresh copy during session) -> Included on Turn N with passive guard
        AmbientContextBuilder._get_current_clipboard_sequence = classmethod(lambda cls: 1001)
        original_get_clip = AmbientContextBuilder._get_clipboard_preview
        AmbientContextBuilder._get_clipboard_preview = classmethod(lambda cls: "error: test sequence change")
        try:
            # Turn N: fresh copy detected -> included
            ctx_turn_n = AmbientContextBuilder.build_ambient_context(query="what is the weather today?")
            assert "Clipboard Buffer" in ctx_turn_n
            assert "Passive background context only — do NOT proactively diagnose" in ctx_turn_n
            assert "test sequence change" in ctx_turn_n

            # Turn N+1: user asks another question without copying anything new -> omitted again!
            ctx_turn_n_plus_1 = AmbientContextBuilder.build_ambient_context(query="tell me a joke")
            assert "Clipboard Buffer" not in ctx_turn_n_plus_1, "Turn N+1 must omit clipboard since sequence did not advance"
            assert "Clipboard Preview" not in ctx_turn_n_plus_1
        finally:
            AmbientContextBuilder._get_clipboard_preview = original_get_clip

        # 3. Explicit query with unchanged sequence -> Included because user explicitly requested it
        AmbientContextBuilder._get_current_clipboard_sequence = classmethod(lambda cls: 1001)
        AmbientContextBuilder._get_clipboard_preview = classmethod(lambda cls: "pasted content")
        try:
            ctx_explicit = AmbientContextBuilder.build_ambient_context(query="what did i copy to my clipboard?")
            assert "Clipboard Buffer" in ctx_explicit
            assert "pasted content" in ctx_explicit
        finally:
            AmbientContextBuilder._get_clipboard_preview = original_get_clip
    finally:
        AmbientContextBuilder._get_current_clipboard_sequence = original_get_seq
        AmbientContextBuilder.reset_clipboard_baseline()
