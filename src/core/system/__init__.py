"""
Aura System Knowledge & Identity Layer
Location: src/core/system/

Milestone 17.0 — System self-knowledge, capability catalog, and dynamic prompt assembly.

This package provides:
  - IdentityLoader: loads knowledge/ YAML files into a unified IdentityContext
  - CapabilityCatalog: exports a live snapshot from CapabilityRegistry at runtime
  - CommandCatalog: exports command reference from NativeManagerRegistry
  - PromptBuilder: assembles the final LLM system prompt

Startup pipeline:
    AuraCore
        └── IdentityLoader          (load knowledge/ YAMLs)
        └── CapabilityCatalog       (read CapabilityRegistry live)
        └── CommandCatalog          (read NativeManagerRegistry live)
        └── PlannerRegistry         (list_planners())
        └── BackendRegistry         (list_backends())
        └── PromptBuilder
            └── → Final Runtime Context (injected into every LLM request)
"""

from .about_report import AboutReport
from .capability_catalog import CapabilityCatalog, CatalogEntry
from .command_catalog import CommandCatalog
from .identity_loader import IdentityContext, IdentityLoader
from .prompt_builder import PromptBuilder

__all__ = [
    "AboutReport",
    "IdentityLoader",
    "IdentityContext",
    "CapabilityCatalog",
    "CatalogEntry",
    "CommandCatalog",
    "PromptBuilder",
]
