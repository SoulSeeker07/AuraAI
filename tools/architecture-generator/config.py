"""
Architecture Layer & Component Configuration
=============================================

Defines all architectural layers in AuraAI with path matching rules,
colors, icons, allowed imports, and component classification patterns.
"""

from dataclasses import dataclass


@dataclass
class ArchitectureLayer:
    """Represents a single architectural layer."""

    name: str
    level: int
    description: str
    path_patterns: list[str]
    allowed_imports: list[str]
    forbidden_imports: list[str]
    color: str
    border_color: str
    icon: str


class ArchitectureConfig:
    """Configuration for all architectural layers and component roles in AuraAI."""

    # Layer 1: Applications & Entry Points
    APP = ArchitectureLayer(
        name="Applications & Clients",
        level=1,
        description="CLI, GUI, REST/WS API servers, main entry points",
        path_patterns=[
            "apps/",
            "clients/",
            "frontend/",
            "backend/",
            "cli.py",
            "main.py",
            "aura.py",
            "run_aura.py",
        ],
        allowed_imports=[
            "core",
            "brain",
            "desktop",
            "browser",
            "research",
            "engineering",
        ],
        forbidden_imports=[],
        color="#FEF08A",  # Soft Yellow fill
        border_color="#CA8A04",  # Dark Gold border
        icon="🚀",
    )

    # Layer 2: OS Kernel & Runtime Core
    CORE = ArchitectureLayer(
        name="OS Kernel & Executive Brain",
        level=2,
        description="AuraCore, ExecutiveBrain, RuntimeSession, MasterOrchestrator",
        path_patterns=[
            "src/core/",
            "core/",
            "master_orchestrator.py",
            "src/brain/aura_core.py",
            "src/brain/executive_brain.py",
            "src/brain/runtime_session.py",
        ],
        allowed_imports=["core", "aca", "shared", "config"],
        forbidden_imports=["gui", "frontend"],
        color="#E9D5FF",  # Soft Lavender fill
        border_color="#9333EA",  # Royal Purple border
        icon="👑",
    )

    # Layer 3: Aura Cognitive Architecture (ACA)
    ACA = ArchitectureLayer(
        name="Cognitive Architecture (ACA)",
        level=3,
        description="Cognitive Pipeline: Perception, DMM, Strategy, Policy, Planner, Coordinator, Reflection, Learning",
        path_patterns=[
            "src/brain/aca/",
            "src/brain/schemas/",
            "src/brain/execution_coordinator.py",
            "src/brain/policy_engine.py",
            "src/brain/strategy_engine.py",
            "src/brain/planner.py",
            "src/brain/goal_manager.py",
            "src/brain/confidence_gate.py",
            "src/brain/fusion_engine.py",
        ],
        allowed_imports=["core", "shared", "engine_interface", "config"],
        forbidden_imports=[
            "desktop",
            "browser",
            "research",
            "engineering",
            "vision",
            "voice",
        ],  # Enforces Guardrail 1
        color="#FFEDD5",  # Warm Peach fill
        border_color="#EA580C",  # Terracotta Red border
        icon="🧠",
    )

    # Layer 4: Domain Subsystems & Adapters
    DOMAIN = ArchitectureLayer(
        name="Domain Subsystems & Engines",
        level=4,
        description="Desktop, Browser, Research, Engineering, Vision, Voice engines and adapters",
        path_patterns=[
            "src/desktop/",
            "src/browser/",
            "src/research/",
            "src/engineering/",
            "src/voice/",
            "src/vision/",
            "src/agents/",
            "src/coding/",
            "src/execution/",
            "desktop/",
            "browser/",
            "research/",
            "engineering/",
            "vision/",
            "voice/",
        ],
        allowed_imports=["core", "shared", "backend", "config"],
        forbidden_imports=["aca"],  # Enforces Guardrail 1
        color="#CCFBF1",  # Soft Teal fill
        border_color="#0D9488",  # Deep Teal border
        icon="🎯",
    )

    # Layer 5: Memory & Knowledge Base
    MEMORY = ArchitectureLayer(
        name="Memory & Knowledge Base",
        level=5,
        description="Fact store, vector store, long-term memory, knowledge graphs, SQLite",
        path_patterns=[
            "src/memory/",
            "knowledge/",
            "Memory.py",
            "Memory.db",
            "database/",
            "src/database/",
            "memory/",
        ],
        allowed_imports=["core", "shared"],
        forbidden_imports=[],
        color="#FED7AA",  # Soft Orange fill
        border_color="#D97706",  # Amber border
        icon="📚",
    )

    # Layer 6: Core Infrastructure & Utilities
    INFRA = ArchitectureLayer(
        name="Infrastructure & Event Bus",
        level=6,
        description="EventBus, Logger, Base Contracts, Configuration, Shared Schemas",
        path_patterns=[
            "src/shared/",
            "config/",
            "logger/",
            "eventbus/",
            "events/",
            "shared/",
        ],
        allowed_imports=[],
        forbidden_imports=["desktop", "browser", "research", "engineering", "aca"],
        color="#BAE6FD",  # Sky Blue fill
        border_color="#0284C7",  # Steel Blue border
        icon="🏛️",
    )

    # Layer 7: Plugins & External Tools
    TOOLS = ArchitectureLayer(
        name="Tool Execution & Plugins",
        level=7,
        description="Plugins, Tool Registry, Extension Kits",
        path_patterns=["plugins/", "tools/", "developer/", "generated_code/"],
        allowed_imports=["core", "shared", "domain"],
        forbidden_imports=[],
        color="#E0E7FF",  # Soft Indigo fill
        border_color="#4F46E5",  # Indigo border
        icon="🔌",
    )

    ALL_LAYERS = [APP, CORE, ACA, DOMAIN, MEMORY, INFRA, TOOLS]

    @classmethod
    def get_layer_by_name(cls, name: str) -> ArchitectureLayer:
        """Get a layer by name."""
        for layer in cls.ALL_LAYERS:
            if layer.name == name:
                return layer
        # Default fallback
        return cls.INFRA

    @classmethod
    def get_layer_by_path(cls, file_path: str) -> ArchitectureLayer:
        """Get the layer a file belongs to based on path patterns (most specific match first)."""
        normalized_path = file_path.replace("\\", "/").lower()

        # Check specific ACA pattern first
        if (
            "src/brain/aca/" in normalized_path
            or "src/brain/schemas/" in normalized_path
        ):
            return cls.ACA

        # Priority order checking
        for layer in [
            cls.APP,
            cls.CORE,
            cls.ACA,
            cls.DOMAIN,
            cls.MEMORY,
            cls.TOOLS,
            cls.INFRA,
        ]:
            for pattern in layer.path_patterns:
                pattern_lower = pattern.lower()
                if pattern_lower in normalized_path:
                    return layer

        # Check parent folder matches
        if "/brain/" in normalized_path:
            return cls.ACA
        if (
            "/desktop/" in normalized_path
            or "/browser/" in normalized_path
            or "/engineering/" in normalized_path
            or "/vision/" in normalized_path
        ):
            return cls.DOMAIN
        if "/memory/" in normalized_path or "/knowledge/" in normalized_path:
            return cls.MEMORY
        if "/core/" in normalized_path:
            return cls.CORE

        # Fallback to Infrastructure for unmapped utilities
        return cls.INFRA

    @classmethod
    def get_layer_dependencies(cls) -> dict:
        """Get the expected dependency chain between layers."""
        return {
            cls.APP.name: [cls.CORE.name, cls.ACA.name, cls.DOMAIN.name],
            cls.CORE.name: [cls.ACA.name, cls.INFRA.name],
            cls.ACA.name: [cls.DOMAIN.name, cls.MEMORY.name, cls.INFRA.name],
            cls.DOMAIN.name: [cls.MEMORY.name, cls.INFRA.name],
            cls.MEMORY.name: [cls.INFRA.name],
            cls.TOOLS.name: [cls.DOMAIN.name, cls.INFRA.name],
            cls.INFRA.name: [],
        }

    LAYERS = [layer.name for layer in ALL_LAYERS]
    LAYERS_BY_LEVEL = {layer.level: layer for layer in ALL_LAYERS}


# Module-level convenience exports
LAYERS = ArchitectureConfig.LAYERS
LAYERS_BY_LEVEL = ArchitectureConfig.LAYERS_BY_LEVEL
ARCH_LAYERS = [layer.name for layer in ArchitectureConfig.ALL_LAYERS]
ARCH_LAYERS_BY_LEVEL = {layer.level: layer for layer in ArchitectureConfig.ALL_LAYERS}
