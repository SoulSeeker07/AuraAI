"""
Prompt Builder
Location: src/core/system/prompt_builder.py

Assembles the final Aura system prompt from all identity layers.

This is the crown jewel of Milestone 17.0.
Every LLM request starts with this context block, ensuring Aura always
knows what it is, what it can do, how it is structured, and how to route work.

Startup pipeline:
    AuraCore
        └── IdentityLoader          (knowledge/ YAMLs)
        └── CapabilityCatalog       (live CapabilityRegistry)
        └── CommandCatalog          (live NativeManagerRegistry)
        └── PlannerRegistry         (registered planners)
        └── BackendRegistry         (registered backends)
        └── PromptBuilder
            └── → Final Runtime Context

Usage:
    builder = PromptBuilder()
    system_prompt = builder.build_system_prompt()
    # Inject into every LLM API call as system context
"""

from __future__ import annotations

import logging
from typing import Any

from .capability_catalog import CapabilityCatalog
from .command_catalog import CommandCatalog
from .identity_loader import IdentityContext, IdentityLoader

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Assembles the final Aura system prompt.

    Design principles:
    - Built once at startup, cached for the session lifetime
    - Reads from IdentityLoader (static YAML) + CapabilityCatalog (live registry)
    - Reads live planner and backend lists from registries
    - Gracefully degrades: if any component is missing, others still contribute
    - Token-aware: sections are ordered by importance (personality first)

    The resulting prompt has this structure:
        [PERSONALITY — Who Aura is, what it never says]
        [IDENTITY — Name, version, goal, principles]
        [PIPELINE — 7-stage execution flow]
        [PLANNERS — Which planner handles which domain]
        [BACKENDS — What each backend does]
        [LIVE CAPABILITIES — From CapabilityRegistry, grouped by category]
        [COMMAND SURFACE — From NativeManagerRegistry]
        [EXAMPLES — Few-shot NL→capability→planner→backend mappings]
    """

    _instance: PromptBuilder | None = None

    def __init__(
        self,
        identity_loader: IdentityLoader | None = None,
        capability_catalog: CapabilityCatalog | None = None,
        command_catalog: CommandCatalog | None = None,
    ) -> None:
        self._identity_loader = identity_loader or IdentityLoader.get_instance()
        self._capability_catalog = capability_catalog or CapabilityCatalog()
        self._command_catalog = command_catalog or CommandCatalog()

        # Cached outputs
        self._system_prompt: str | None = None
        self._context: IdentityContext | None = None

    @classmethod
    def get_instance(cls) -> "PromptBuilder":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (used in tests)."""
        cls._instance = None

    def _get_context(self) -> IdentityContext:
        """Load and cache IdentityContext."""
        if self._context is None:
            self._context = self._identity_loader.load()
        return self._context

    def build_system_prompt(self, include_examples: bool = True) -> str:
        """
        Build and cache the full Aura system prompt.

        This is the primary output of the identity layer.
        Call this once at startup and cache the result.

        Args:
            include_examples: Whether to include few-shot examples.
                              Set False for token-constrained contexts.

        Returns:
            The complete system prompt string for injection into LLM calls.
        """
        if self._system_prompt is not None:
            return self._system_prompt

        ctx = self._get_context()
        sections: list[str] = []

        # Section 1: Personality (most important — goes first)
        sections.append(self.build_personality_block(ctx))

        # Section 2: Core Identity
        sections.append(self.build_identity_block(ctx))

        # Section 3: Runtime Pipeline
        sections.append(self.build_pipeline_block(ctx))

        # Section 4: Planner Knowledge
        sections.append(self.build_planner_block(ctx))

        # Section 5: Backend Knowledge
        sections.append(self.build_backend_block(ctx))

        # Section 6: User-facing Skills (from aura_skills.yaml — stable, human-readable)
        skills_block = self.build_skills_block(ctx)
        if skills_block:
            sections.append(skills_block)

        # Section 7: Live Capability Catalog (from CapabilityRegistry — dynamic)
        capability_block = self.build_capability_block()
        if capability_block:
            sections.append(capability_block)

        # Section 8: Command Surface (from NativeManagerRegistry — dynamic)
        command_block = self.build_command_block()
        if command_block:
            sections.append(command_block)

        # Section 9: Limitations (from aura_limitations.yaml — refusal rules)
        limitations_block = self.build_limitations_block(ctx)
        if limitations_block:
            sections.append(limitations_block)

        # Section 10: Few-shot examples (optional)
        if include_examples:
            examples_block = self.build_examples_block(ctx, max_examples=20)
            if examples_block:
                sections.append(examples_block)

        self._system_prompt = "\n\n".join(sections)

        logger.info(
            f"PromptBuilder: system prompt assembled. "
            f"Sections: {len(sections)}, "
            f"Length: {len(self._system_prompt)} chars."
        )

        return self._system_prompt

    def build_personality_block(self, ctx: IdentityContext | None = None) -> str:
        """
        Build the personality / identity statement block.
        This is the most critical block — it overrides generic chatbot defaults.
        """
        ctx = ctx or self._get_context()
        lines: list[str] = []

        identity_stmt = ctx.identity_statement
        if identity_stmt:
            lines.append(identity_stmt)
        else:
            # Fallback minimal identity statement
            name = ctx.name or "Aura AI"
            lines.append(
                f"You are {name}.\n"
                f"You are an AI Operating System, not a chatbot.\n"
                f"You control the desktop, perform research, write code, and automate workflows.\n"
                f"You use planners before executing. You use backends to do real work.\n"
                f"You reason before you act. You never pretend to be ChatGPT or any other AI.\n"
                f"If you cannot perform an action, name the missing subsystem."
            )

        never_say = ctx.never_say
        if never_say:
            lines.append("\nYou must NEVER say any of the following:")
            for phrase in never_say[:10]:
                lines.append(f'  • "{phrase}"')

        return "\n".join(lines)

    def build_identity_block(self, ctx: IdentityContext | None = None) -> str:
        """Build the core identity block (name, version, description, principles)."""
        ctx = ctx or self._get_context()
        lines: list[str] = []

        name = ctx.name or "Aura AI"
        version = ctx.version or "unknown"
        tagline = ctx.tagline

        lines.append(f"=== {name} v{version} ===")
        if tagline:
            lines.append(tagline)

        description = ctx.description
        if description:
            lines.append(f"\n{description}")

        principles = ctx.principles
        if principles:
            lines.append("\nCore Operating Principles:")
            for principle in principles:
                lines.append(f"  • {principle}")

        domains = ctx.identity.get("capability_domains", [])
        if domains:
            lines.append(f"\nCapability Domains: {', '.join(domains)}")

        return "\n".join(lines)

    def build_pipeline_block(self, ctx: IdentityContext | None = None) -> str:
        """Build the 7-stage pipeline description block."""
        ctx = ctx or self._get_context()
        stages = ctx.pipeline_stages
        flow = ctx.pipeline.get("flow", "")

        if not stages and not flow:
            return ""

        lines: list[str] = ["=== AURA COGNITIVE PIPELINE ==="]

        if flow:
            lines.append(flow.strip())
        elif stages:
            lines.append("Aura executes every request through a 7-stage cognitive pipeline:")
            for stage in stages:
                num = stage.get("stage", "?")
                name = stage.get("name", "")
                component = stage.get("component", "")
                desc = stage.get("description", "").strip().split("\n")[0]
                lines.append(f"  Stage {num}: {name} ({component}) — {desc}")

        return "\n".join(lines)

    def build_planner_block(self, ctx: IdentityContext | None = None) -> str:
        """
        Build the planner knowledge block.
        Combines static YAML knowledge with live PlannerRegistry data.
        """
        ctx = ctx or self._get_context()
        lines: list[str] = ["=== AURA PLANNERS ==="]

        # Try live PlannerRegistry first
        live_planners = self._get_live_planners()

        # Get static knowledge from pipeline YAML
        static_planners = {
            p["role"]: p
            for p in ctx.pipeline_planners
            if isinstance(p, dict) and "role" in p
        }

        # Merge: live planners + static metadata
        displayed: set[str] = set()
        for planner_name, planner_obj in live_planners.items():
            display_name = planner_name.title() + "Planner"
            static = static_planners.get(planner_name, {})
            handles = static.get("handles", [])
            backend = static.get("backend", "")

            lines.append(f"\n{display_name}:")
            if handles:
                for pattern in handles[:8]:
                    lines.append(f"  Handles: {pattern}")
                if len(handles) > 8:
                    lines.append(f"  ... and {len(handles) - 8} more patterns")
            if backend:
                lines.append(f"  Backend: {backend}")
            displayed.add(planner_name)

        # Add static-only planners not in live registry
        for role, static in static_planners.items():
            if role not in displayed:
                handles = static.get("handles", [])
                lines.append(f"\n{static.get('name', role)}:")
                for pattern in handles[:5]:
                    lines.append(f"  Handles: {pattern}")

        if len(lines) == 1:
            lines.append("  (PlannerRegistry not available — using DecisionEngine routing)")

        return "\n".join(lines)

    def build_backend_block(self, ctx: IdentityContext | None = None) -> str:
        """
        Build the backend knowledge block.
        Combines live BackendRegistry data with static YAML knowledge.
        """
        ctx = ctx or self._get_context()
        lines: list[str] = ["=== AURA BACKENDS ==="]

        # Static backend knowledge from pipeline YAML
        static_backends = {
            b["name"]: b
            for b in ctx.pipeline_backends
            if isinstance(b, dict) and "name" in b
        }

        # Try live BackendRegistry
        live_backends = self._get_live_backends()
        displayed: set[str] = set()

        for backend_name, backend_obj in live_backends.items():
            static = static_backends.get(backend_name, {})
            strengths = static.get("strengths", [])
            description = static.get("description", "").strip().split("\n")[0]
            internet = static.get("internet_required", False)
            btype = static.get("type", "")

            lines.append(f"\n{backend_name}:")
            if btype:
                lines.append(f"  Type: {btype}")
            lines.append(f"  Internet: {'Yes' if internet else 'No (local)'}")
            if description:
                lines.append(f"  {description}")
            if strengths:
                lines.append(f"  Strengths: {', '.join(strengths)}")
            displayed.add(backend_name)

        # Add static-only backends
        for name, static in static_backends.items():
            if name not in displayed:
                strengths = static.get("strengths", [])
                description = static.get("description", "").strip().split("\n")[0]
                lines.append(f"\n{name}:")
                if description:
                    lines.append(f"  {description}")
                if strengths:
                    lines.append(f"  Strengths: {', '.join(strengths)}")

        if len(lines) == 1:
            lines.append("  (BackendRegistry not available)")

        return "\n".join(lines)

    def build_skills_block(self, ctx: IdentityContext | None = None) -> str:
        """
        Build the user-facing skills block from aura_skills.yaml.

        IMPORTANT: This uses the YAML skills, not the live capability registry.
        Skills = stable, human-readable, what Aura tells users it can do.
        Capabilities = dynamic, implementation-level, from live registries.
        """
        ctx = ctx or self._get_context()
        skill_domains = ctx.skill_domains
        if not skill_domains:
            return ""

        lines = ["=== AURA SKILLS (USER-FACING) ==="]
        lines.append(
            "When a user asks 'What can you do?', answer with these skills, not raw capability IDs:"
        )
        for domain in skill_domains:
            name = domain.get("domain", "")
            emoji = domain.get("emoji", "")
            status = domain.get("status", "")
            status_str = f" [{status}]" if status else ""
            domain_skills = domain.get("skills", [])
            lines.append(f"\n{emoji} {name}{status_str}:")
            for skill in domain_skills[:8]:
                lines.append(f"  • {skill}")
            if len(domain_skills) > 8:
                lines.append(f"  ... and {len(domain_skills) - 8} more")
        return "\n".join(lines)

    def build_limitations_block(self, ctx: IdentityContext | None = None) -> str:
        """
        Build the limitations block from aura_limitations.yaml.

        This teaches the LLM when to refuse requests.
        Hard limits = always refuse.
        Soft limits = ask for confirmation.
        """
        ctx = ctx or self._get_context()
        hard_limits = ctx.hard_limits
        ethical_rules = ctx.ethical_rules
        missing = ctx.missing_subsystems

        if not hard_limits and not ethical_rules:
            return ""

        lines = ["=== AURA LIMITATIONS & BOUNDARIES ==="]

        if hard_limits:
            lines.append("\nHard Limits (ALWAYS refuse — no exceptions):")
            for limit in hard_limits:
                desc = limit.get("description", "")
                response = limit.get("response", "").strip().split("\n")[0]
                lines.append(f"  ✗ {desc}")
                if response:
                    lines.append(f"    Say: \"{response}\"")

        if ethical_rules:
            lines.append("\nEthical Rules:")
            for rule in ethical_rules:
                desc = rule.get("description", "").strip().split("\n")[0]
                lines.append(f"  • {desc}")

        if missing:
            lines.append("\nMissing Subsystems (be honest — don't fake it):")
            for sub in missing:
                desc = sub.get("description", "")
                status = sub.get("status", "")
                lines.append(f"  ⚠ {desc}: {status}")

        return "\n".join(lines)

    def build_capability_block(self) -> str:
        """
        Build the live capability catalog block.
        Read directly from CapabilityRegistry — fully dynamic.
        """
        return self._capability_catalog.export_as_text(max_per_category=10)

    def build_command_block(self) -> str:
        """
        Build the native manager command surface block.
        Read directly from NativeManagerRegistry — fully dynamic.
        """
        return self._command_catalog.export_as_text()

    def build_examples_block(
        self, ctx: IdentityContext | None = None, max_examples: int = 20
    ) -> str:
        """
        Build the few-shot examples block.
        Selects a diverse subset from aura_examples.yaml.
        """
        ctx = ctx or self._get_context()
        examples = ctx.example_list

        if not examples:
            return ""

        lines: list[str] = ["=== FEW-SHOT ROUTING EXAMPLES ==="]
        lines.append(
            "These examples show how user requests map to capabilities, planners, and backends:"
        )

        # Select diverse examples: take 2-3 from each domain
        selected = self._select_diverse_examples(examples, max_examples)

        for ex in selected:
            user_says = ex.get("user_says", "")
            capability = ex.get("capability", "")
            planner = ex.get("planner", "")
            backend = ex.get("backend", "")
            notes = ex.get("notes", "")

            lines.append(f'\nUser: "{user_says}"')
            lines.append(f"  Capability: {capability}")
            if planner and "(none" not in planner:
                lines.append(f"  Planner:    {planner}")
            if backend and "(none" not in backend:
                lines.append(f"  Backend:    {backend}")
            if notes:
                lines.append(f"  Note:       {notes}")

        return "\n".join(lines)

    def get_compact_identity(self) -> str:
        """
        Return a compact single-paragraph identity string.
        Used for short contexts where the full prompt is too long.
        """
        ctx = self._get_context()
        name = ctx.name or "Aura AI"
        version = ctx.version
        cap_count = self._capability_catalog.count()
        planner_names = list(self._get_live_planners().keys())
        backend_names = list(self._get_live_backends().keys())

        planner_str = ", ".join(planner_names) if planner_names else "DesktopPlanner"
        backend_str = ", ".join(backend_names) if backend_names else "Native Desktop Engine"

        return (
            f"You are {name} v{version}, an AI Operating System. "
            f"You have {cap_count} registered capabilities across Desktop, Research, Coding, "
            f"Voice, Vision, Memory, and Workflow domains. "
            f"Active planners: {planner_str}. "
            f"Active backends: {backend_str}. "
            f"You reason before acting. You route through planners. You never pretend."
        )

    def invalidate_cache(self) -> None:
        """
        Invalidate the cached system prompt.
        Call this after a new manager or planner is registered at runtime.
        """
        self._system_prompt = None
        self._context = None
        logger.info("PromptBuilder: cache invalidated.")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_live_planners(self) -> dict[str, Any]:
        """Get live planner data from PlannerRegistry."""
        try:
            from src.core.orchestration.planner_registry import PlannerRegistry
            registry = PlannerRegistry.get_instance()
            return {name: registry.get_planner(name) for name in registry.list_planners()}
        except Exception as e:
            logger.debug(f"PromptBuilder: could not load PlannerRegistry: {e}")
            return {}

    def _get_live_backends(self) -> dict[str, Any]:
        """Get live backend data from BackendRegistry."""
        try:
            from src.core.backends.backend_registry import BackendRegistry
            registry = BackendRegistry.get_instance()
            return {b.name: b for b in getattr(registry, "_backends", [])}
        except Exception as e:
            logger.debug(f"PromptBuilder: could not load BackendRegistry: {e}")
            return {}

    def _select_diverse_examples(
        self, examples: list[dict], max_count: int
    ) -> list[dict]:
        """
        Select a diverse set of examples across domains.
        Aims for ~2-3 per planner type.
        """
        by_planner: dict[str, list[dict]] = {}
        for ex in examples:
            planner = ex.get("planner", "other")
            by_planner.setdefault(planner, []).append(ex)

        selected: list[dict] = []
        per_planner = max(1, max_count // max(len(by_planner), 1))

        for planner, exs in by_planner.items():
            selected.extend(exs[:per_planner])
            if len(selected) >= max_count:
                break

        return selected[:max_count]
