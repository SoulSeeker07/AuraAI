"""
Unit Tests — Aura System Knowledge & Identity Layer
Location: tests/unit/system/test_identity_loader.py

Tests IdentityLoader, CapabilityCatalog, and PromptBuilder.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


# ── IdentityLoader tests ──────────────────────────────────────────────────────


class TestIdentityLoader:
    """Tests for IdentityLoader and IdentityContext."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.system.identity_loader import IdentityLoader

        IdentityLoader.reset_instance()

    def test_load_returns_identity_context(self):
        """IdentityLoader.load() returns a populated IdentityContext."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        assert ctx is not None
        assert ctx.is_loaded(), "IdentityContext should be loaded from knowledge/ dir"

    def test_identity_name(self):
        """IdentityContext.name returns the Aura name."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        assert "aura" in ctx.name.lower(), f"Expected Aura in name, got: {ctx.name!r}"

    def test_identity_version(self):
        """IdentityContext.version is set."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        assert ctx.version != "unknown"

    def test_capability_groups_loaded(self):
        """IdentityContext.capability_groups has entries from dynamic CapabilityCatalog."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        assert len(ctx.capability_groups) > 0, "Should have capability groups"
        group_names = [g.get("group", "") for g in ctx.capability_groups]
        window_groups = [
            g for g in group_names if g in ("window", "audio", "clipboard", "display")
        ]
        assert (
            len(window_groups) > 0
        ), "Should have native desktop capability categories"

    def test_pipeline_stages_loaded(self):
        """IdentityContext.pipeline_stages has 7 stages."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        stages = ctx.pipeline_stages
        assert len(stages) == 7, f"Expected 7 pipeline stages, got {len(stages)}"

    def test_examples_loaded(self):
        """IdentityContext.example_list has many examples."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        examples = ctx.example_list
        assert (
            len(examples) >= 50
        ), f"Expected at least 50 examples, got {len(examples)}"

    def test_personality_loaded(self):
        """IdentityContext.identity_statement is non-empty."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        stmt = ctx.identity_statement
        assert len(stmt) > 20, "Identity statement should be substantial"
        assert "Aura" in stmt or "aura" in stmt.lower()

    def test_never_say_list(self):
        """IdentityContext.never_say contains ChatGPT-like phrases."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx = loader.load()
        never_say = ctx.never_say
        assert len(never_say) > 0
        # Ensure ChatGPT reference is in the never-say list
        chatgpt_in_list = any(
            "chatgpt" in phrase.lower() or "ChatGPT" in phrase for phrase in never_say
        )
        assert chatgpt_in_list, "never_say should include ChatGPT reference"

    def test_reload_refreshes_context(self):
        """reload() clears cache and re-loads."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx1 = loader.load()
        ctx2 = loader.reload()
        assert ctx1 is not ctx2, "reload() should return a fresh context"
        assert ctx2.name == ctx1.name  # content should be identical

    def test_missing_knowledge_dir(self, tmp_path):
        """IdentityLoader gracefully handles missing knowledge dir."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=tmp_path / "nonexistent")
        ctx = loader.load()
        assert not ctx.is_loaded()
        assert len(ctx.load_errors) > 0

    def test_caching(self):
        """Calling load() twice returns the same context object."""
        from core.system.identity_loader import IdentityLoader

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        ctx1 = loader.load()
        ctx2 = loader.load()
        assert ctx1 is ctx2, "load() should return cached context on second call"


# ── CapabilityCatalog tests ───────────────────────────────────────────────────


class TestCapabilityCatalog:
    """Tests for CapabilityCatalog — live registry export."""

    def test_export_live_returns_list(self):
        """export_live() returns a list (possibly empty if registry unavailable)."""
        from core.system.capability_catalog import CapabilityCatalog

        catalog = CapabilityCatalog()
        entries = catalog.export_live()
        assert isinstance(entries, list)

    def test_export_live_with_mock_registry(self):
        """export_live() correctly maps CapabilityDescriptor fields to CatalogEntry."""
        from core.system.capability_catalog import CapabilityCatalog

        catalog = CapabilityCatalog()

        # Mock the registry
        mock_registry = MagicMock()
        mock_desc = MagicMock()
        mock_desc.description = "List all open windows"
        mock_desc.category = "window"
        mock_desc.manager = "window"
        mock_desc.risk_level.value = "safe"
        mock_desc.permission.value = "read"
        mock_desc.requires_confirmation = False
        mock_desc.is_destructive = False
        mock_desc.usage_examples = ["List all open windows"]
        mock_desc.tags = ["window"]

        mock_registry._capabilities = {"list_windows": mock_desc}
        catalog._registry = mock_registry
        catalog._registry_loaded = True

        entries = catalog.export_live()
        assert len(entries) == 1
        assert entries[0].name == "list_windows"
        assert entries[0].category == "window"

    def test_export_as_text_returns_string(self):
        """export_as_text() returns a non-empty string."""
        from core.system.capability_catalog import CapabilityCatalog

        catalog = CapabilityCatalog()
        text = catalog.export_as_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_export_by_category_groups_correctly(self):
        """export_by_category() groups entries by category."""
        from core.system.capability_catalog import CapabilityCatalog, CatalogEntry

        catalog = CapabilityCatalog()

        # Mock export_live to return controlled data
        mock_entries = [
            CatalogEntry(
                name="list_windows", description="", category="window", manager="window"
            ),
            CatalogEntry(
                name="activate_window",
                description="",
                category="window",
                manager="window",
            ),
            CatalogEntry(
                name="mute", description="", category="audio", manager="audio"
            ),
        ]
        catalog.export_live = lambda: mock_entries  # type: ignore

        grouped = catalog.export_by_category()
        assert "window" in grouped
        assert "audio" in grouped
        assert len(grouped["window"]) == 2
        assert len(grouped["audio"]) == 1

    def test_has_capability_with_mock(self):
        """has_capability() returns True for existing capabilities."""
        from core.system.capability_catalog import CapabilityCatalog

        catalog = CapabilityCatalog()
        mock_registry = MagicMock()
        mock_registry._capabilities = {"mute": MagicMock()}
        catalog._registry = mock_registry
        catalog._registry_loaded = True

        assert catalog.has_capability("mute") is True
        assert catalog.has_capability("nonexistent") is False

    def test_count_with_mock(self):
        """count() returns number of registered capabilities."""
        from core.system.capability_catalog import CapabilityCatalog

        catalog = CapabilityCatalog()
        mock_registry = MagicMock()
        mock_registry._capabilities = {"a": MagicMock(), "b": MagicMock()}
        catalog._registry = mock_registry
        catalog._registry_loaded = True
        assert catalog.count() == 2


# ── PromptBuilder tests ───────────────────────────────────────────────────────


class TestPromptBuilder:
    """Tests for PromptBuilder — final system prompt assembly."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        PromptBuilder.reset_instance()
        IdentityLoader.reset_instance()

    def test_build_system_prompt_returns_string(self):
        """build_system_prompt() returns a non-empty string."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        prompt = builder.build_system_prompt(include_examples=False)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_personality_block_no_chatgpt(self):
        """Personality block does not contain ChatGPT."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        ctx = loader.load()
        block = builder.build_personality_block(ctx)
        assert "ChatGPT" not in block or "never" in block.lower()

    def test_personality_block_contains_aura(self):
        """Personality block identifies as Aura."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        ctx = loader.load()
        block = builder.build_personality_block(ctx)
        assert "Aura" in block

    def test_identity_block_contains_version(self):
        """Identity block contains the version."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        ctx = loader.load()
        block = builder.build_identity_block(ctx)
        assert "0." in block  # version like "0.17"

    def test_pipeline_block_has_stages(self):
        """Pipeline block includes stage descriptions."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        ctx = loader.load()
        block = builder.build_pipeline_block(ctx)
        assert len(block) > 0
        # Should contain either the flow diagram or stage list
        assert "Memory" in block or "Stage" in block

    def test_build_system_prompt_cached(self):
        """build_system_prompt() returns the same object on second call."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        p1 = builder.build_system_prompt(include_examples=False)
        p2 = builder.build_system_prompt(include_examples=False)
        assert p1 is p2, "build_system_prompt() should return cached prompt"

    def test_invalidate_cache(self):
        """invalidate_cache() forces a fresh build on next call."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        p1 = builder.build_system_prompt(include_examples=False)
        builder.invalidate_cache()
        p2 = builder.build_system_prompt(include_examples=False)
        assert p1 is not p2, "After invalidate, prompt should be rebuilt"

    def test_compact_identity_non_empty(self):
        """get_compact_identity() returns a concise identity string."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        compact = builder.get_compact_identity()
        assert isinstance(compact, str)
        assert "Aura" in compact
        assert len(compact) < 2000  # Should be compact

    def test_examples_block_with_real_data(self):
        """build_examples_block() produces formatted examples."""
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        ctx = loader.load()
        block = builder.build_examples_block(ctx, max_examples=5)
        if ctx.example_list:
            assert "User:" in block or "User:" in block
            assert "Capability:" in block


# ── Integration smoke test ────────────────────────────────────────────────────


class TestIdentityLayerIntegration:
    """Smoke tests for the full identity layer pipeline."""

    def test_full_pipeline_no_crash(self):
        """
        Full pipeline: IdentityLoader → CapabilityCatalog → PromptBuilder
        should not crash even if external registries are unavailable.
        """
        from core.system.capability_catalog import CapabilityCatalog
        from core.system.command_catalog import CommandCatalog
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        catalog = CapabilityCatalog()
        cmd_catalog = CommandCatalog()
        builder = PromptBuilder(
            identity_loader=loader,
            capability_catalog=catalog,
            command_catalog=cmd_catalog,
        )

        # Should not raise
        prompt = builder.build_system_prompt(include_examples=True)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_query_contains_aura_not_chatgpt(self):
        """
        A system_query should produce a response identifying Aura,
        not ChatGPT or a generic AI.
        """
        from core.system.identity_loader import IdentityLoader
        from core.system.prompt_builder import PromptBuilder

        PromptBuilder.reset_instance()
        IdentityLoader.reset_instance()

        loader = IdentityLoader(knowledge_dir=KNOWLEDGE_DIR)
        builder = PromptBuilder(identity_loader=loader)
        compact = builder.get_compact_identity()

        assert "Aura" in compact
        assert "ChatGPT" not in compact
        assert "language model" not in compact.lower()
