"""
Identity Loader
Location: src/core/system/identity_loader.py

Loads all knowledge/ YAML files into a unified IdentityContext.
IdentityContext is the in-memory representation of Aura's self-knowledge.

Usage:
    loader = IdentityLoader()
    ctx = loader.load()
    print(ctx.identity["name"])  # "Aura AI"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Locate the knowledge/ directory ──────────────────────────────────────────
# Walk up from this file's location to find the project root (contains knowledge/).
# This is robust against different working directories.
_THIS_FILE = Path(__file__).resolve()

def _find_knowledge_dir() -> Path:
    """Walk up from src/core/system/ to find the project root knowledge/ dir containing aura_identity.yaml."""
    search = _THIS_FILE.parent
    for _ in range(8):  # max 8 levels up
        candidate = search / "knowledge"
        if candidate.is_dir() and (candidate / "aura_identity.yaml").is_file():
            return candidate
        search = search.parent
    # Fallback: project root relative to cwd
    fallback = Path.cwd() / "knowledge"
    logger.warning(
        f"IdentityLoader: could not auto-locate knowledge/ directory. Using {fallback}"
    )
    return fallback


@dataclass
class IdentityContext:
    """
    Unified in-memory representation of all Aura knowledge documents.

    Populated by IdentityLoader from the knowledge/ directory.
    Read-only at runtime — refresh by calling IdentityLoader.reload().

    IMPORTANT — What belongs here vs. live registries:
      YAML (static, version-controlled):
        - identity       = who Aura is, goals, mission, principles
        - commands       = documentation-level command reference
        - examples       = NL routing examples (Aura's experience)
        - personality    = tone, never_say, forbidden phrases
        - pipeline       = 7-stage pipeline documentation
        - skills         = user-facing skill descriptions
        - limitations    = hard limits, soft limits, ethical rules
      Live registries (dynamic, auto-discovered):
        - capabilities   = from CapabilityRegistry at runtime
        - managers       = from NativeManagerRegistry at runtime
        - planners       = from PlannerRegistry at runtime
        - backends       = from BackendRegistry at runtime
    """

    # From aura_identity.yaml
    identity: dict[str, Any] = field(default_factory=dict)

    # From aura_commands.yaml
    commands: dict[str, Any] = field(default_factory=dict)

    # From aura_examples.yaml
    examples: dict[str, Any] = field(default_factory=dict)

    # From aura_personality.yaml
    personality: dict[str, Any] = field(default_factory=dict)

    # From aura_pipeline.yaml
    pipeline: dict[str, Any] = field(default_factory=dict)

    # From aura_skills.yaml — user-facing skill descriptions
    skills: dict[str, Any] = field(default_factory=dict)

    # From aura_limitations.yaml — hard limits, soft limits, ethics
    limitations: dict[str, Any] = field(default_factory=dict)

    # Load metadata
    knowledge_dir: str = ""
    loaded_files: list[str] = field(default_factory=list)
    load_errors: list[str] = field(default_factory=list)

    @property
    def skill_domains(self) -> list[dict[str, Any]]:
        """All skill domains from aura_skills.yaml."""
        return self.skills.get("skills", [])

    @property
    def hard_limits(self) -> list[dict[str, Any]]:
        """Hard limits from aura_limitations.yaml."""
        return self.limitations.get("hard_limits", [])

    @property
    def soft_limits(self) -> list[dict[str, Any]]:
        """Soft limits (require confirmation) from aura_limitations.yaml."""
        return self.limitations.get("soft_limits", [])

    @property
    def ethical_rules(self) -> list[dict[str, Any]]:
        """Ethical rules from aura_limitations.yaml."""
        return self.limitations.get("ethical_rules", [])

    @property
    def capability_groups(self) -> list[dict[str, Any]]:
        """Live capability groups from CapabilityCatalog."""
        try:
            from .capability_catalog import CapabilityCatalog
            grouped = CapabilityCatalog().export_by_category()
            return [{"group": cat, "capabilities": [e.name for e in entries]} for cat, entries in grouped.items()]
        except Exception:
            return []

    @property
    def missing_subsystems(self) -> list[dict[str, Any]]:
        """Honest capability gaps from aura_limitations.yaml."""
        return self.limitations.get("missing_subsystems", [])

    @property
    def name(self) -> str:
        """Aura's canonical name."""
        return self.identity.get("name", "Aura AI")

    @property
    def version(self) -> str:
        """Current version string."""
        return str(self.identity.get("version", "unknown"))

    @property
    def description(self) -> str:
        """Long-form identity description."""
        return self.identity.get("description", "").strip()

    @property
    def tagline(self) -> str:
        """One-line tagline."""
        return self.identity.get("tagline", "").strip()

    @property
    def principles(self) -> list[str]:
        """Core operating principles."""
        return self.identity.get("principles", [])

    @property
    def pipeline_stages(self) -> list[dict[str, Any]]:
        """All 7 pipeline stages from aura_pipeline.yaml."""
        return self.pipeline.get("stages", [])

    @property
    def pipeline_planners(self) -> list[dict[str, Any]]:
        """Planner knowledge from aura_pipeline.yaml."""
        return self.pipeline.get("planners", [])

    @property
    def pipeline_backends(self) -> list[dict[str, Any]]:
        """Backend knowledge from aura_pipeline.yaml."""
        return self.pipeline.get("backends", [])

    @property
    def identity_statement(self) -> str:
        """The core personality identity statement."""
        return self.personality.get("identity_statement", "").strip()

    @property
    def never_say(self) -> list[str]:
        """Phrases Aura must never say."""
        return self.personality.get("never_say", [])

    @property
    def example_list(self) -> list[dict[str, Any]]:
        """All NL → capability → planner → backend examples."""
        return self.examples.get("examples", [])

    def is_loaded(self) -> bool:
        """True if at least the identity file was loaded successfully."""
        return bool(self.identity)


class IdentityLoader:
    """
    Loads all knowledge/ YAML files into an IdentityContext.

    Features:
    - Lazy loading (first call only)
    - In-memory caching
    - Graceful partial load (individual file errors don't crash startup)
    - reload() for hot-refresh
    """

    _instance: IdentityLoader | None = None

    def __init__(self, knowledge_dir: Path | str | None = None):
        self._knowledge_dir = Path(knowledge_dir) if knowledge_dir else _find_knowledge_dir()
        self._context: IdentityContext | None = None

    @classmethod
    def get_instance(cls) -> "IdentityLoader":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (used in tests)."""
        cls._instance = None

    def load(self) -> IdentityContext:
        """
        Load (or return cached) IdentityContext.
        On first call, reads all knowledge/ YAML files.
        Subsequent calls return the cached context.
        """
        if self._context is None:
            self._context = self._load_all()
        return self._context

    def reload(self) -> IdentityContext:
        """Force-reload all knowledge files, clearing the cache."""
        self._context = None
        return self.load()

    def _load_all(self) -> IdentityContext:
        """Read all YAML knowledge files and build IdentityContext."""
        ctx = IdentityContext(knowledge_dir=str(self._knowledge_dir))

        if not self._knowledge_dir.exists():
            msg = f"IdentityLoader: knowledge/ directory not found at {self._knowledge_dir}"
            logger.error(msg)
            ctx.load_errors.append(msg)
            return ctx

        file_map = {
            "aura_identity.yaml":     "identity",
            "aura_commands.yaml":     "commands",
            "aura_examples.yaml":     "examples",
            "aura_personality.yaml":  "personality",
            "aura_pipeline.yaml":     "pipeline",
            "aura_skills.yaml":       "skills",
            "aura_limitations.yaml":  "limitations",
            # NOTE: aura_capabilities.yaml is intentionally excluded.
            # Capabilities are loaded dynamically from CapabilityRegistry.
            # See CapabilityCatalog for live capability discovery.
        }

        for filename, attr in file_map.items():
            filepath = self._knowledge_dir / filename
            data = self._load_yaml(filepath)
            if data is not None:
                setattr(ctx, attr, data)
                ctx.loaded_files.append(filename)
            else:
                ctx.load_errors.append(f"Failed to load {filename}")

        logger.info(
            f"IdentityLoader: loaded {len(ctx.loaded_files)}/{len(file_map)} knowledge files. "
            f"Identity: '{ctx.name}' v{ctx.version}. "
            f"Capability groups: {len(ctx.capability_groups)}. "
            f"Examples: {len(ctx.example_list)}."
        )

        if ctx.load_errors:
            logger.warning(f"IdentityLoader errors: {ctx.load_errors}")

        return ctx

    def _load_yaml(self, filepath: Path) -> dict[str, Any] | None:
        """Load a single YAML file. Returns None on error."""
        try:
            import yaml  # type: ignore[import]
        except ImportError:
            logger.warning("PyYAML not installed. Falling back to safe minimal loader.")
            return self._load_yaml_minimal(filepath)

        try:
            with filepath.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data or {}
        except FileNotFoundError:
            logger.warning(f"IdentityLoader: file not found: {filepath}")
            return None
        except Exception as exc:
            logger.error(f"IdentityLoader: error loading {filepath}: {exc}")
            return None

    def _load_yaml_minimal(self, filepath: Path) -> dict[str, Any] | None:
        """
        Fallback YAML loader for environments without PyYAML.
        Returns an empty dict — the system still starts, just without knowledge context.
        """
        if not filepath.exists():
            return None
        logger.warning(
            f"IdentityLoader: PyYAML unavailable — {filepath.name} loaded as empty dict. "
            f"Install PyYAML for full identity context."
        )
        return {}
