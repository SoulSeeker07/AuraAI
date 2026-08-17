"""
Coding Capability Provider
==========================
Location: src/core/capabilities/providers/coding_provider.py

Provides capability descriptors for the Coding Agent and Engineering subsystems.
Distinguishes physically operational backends (is_live=True) from scaffolded ones (is_live=False).
"""

from __future__ import annotations

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


class CodingCapabilityProvider(ICapabilityProvider):
    """Provider for coding intelligence, file editing, and AST analysis capabilities."""

    DOMAIN = "coding"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = self._build_capabilities()

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def _build_capabilities(self) -> dict[str, Capability]:
        caps = [
            # 1. AST & Code Analysis (Live)
            Capability(
                name="code.analyze",
                domain=self.DOMAIN,
                description="Analyze repository AST, symbol hierarchy, call graphs, and architectural dependencies.",
                category="analysis",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_files": {"type": "array", "items": {"type": "string"}},
                        "symbols": {"type": "array", "items": {"type": "string"}},
                    },
                },
                output_schema={"type": "object", "properties": {"symbols": {"type": "array"}, "dependencies": {"type": "object"}}},
                risk_level=ActionRisk.LOW,
                permissions=["filesystem:read"],
                execution_backend="coding_backend",
                is_live=True,
                availability="online",
                tags=["ast", "symbols", "dependencies", "read_only"],
            ),
            # 2. Workspace File Traversal (Live)
            Capability(
                name="workspace.walk",
                domain=self.DOMAIN,
                description="Walk workspace files respecting .gitignore hierarchies and token/file safety caps.",
                category="workspace",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target_files": {"type": "array", "items": {"type": "string"}},
                        "max_files": {"type": "integer", "default": 200},
                    },
                },
                output_schema={"type": "object", "properties": {"files": {"type": "array"}}},
                risk_level=ActionRisk.LOW,
                permissions=["filesystem:read"],
                execution_backend="coding_backend",
                is_live=True,
                availability="online",
                tags=["workspace", "gitignore", "walker"],
            ),
            # 3. Antigravity Plan & Code Generation (Live)
            Capability(
                name="code.generate",
                domain=self.DOMAIN,
                description="Generate structured code modifications and implementation plans via Antigravity agy delegation.",
                category="generation",
                input_schema={
                    "type": "object",
                    "required": ["goal"],
                    "properties": {
                        "goal": {"type": "string"},
                        "target_files": {"type": "array", "items": {"type": "string"}},
                        "context": {"type": "object"},
                    },
                },
                output_schema={"type": "object", "properties": {"plan": {"type": "string"}, "code": {"type": "string"}}},
                risk_level=ActionRisk.LOW,
                permissions=["ai:generate"],
                execution_backend="coding_backend",
                is_live=True,
                availability="online",
                tags=["antigravity", "agy", "generation"],
            ),
            # 4. Atomic File Editing with Physical Rollback (Live)
            Capability(
                name="code.edit",
                domain=self.DOMAIN,
                description="Apply precise file edits guarded by WorkspacePolicy with atomic byte-for-byte physical rollback.",
                category="editor",
                input_schema={
                    "type": "object",
                    "required": ["file_path"],
                    "properties": {
                        "file_path": {"type": "string"},
                        "instruction": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}, "backup_id": {"type": "string"}}},
                risk_level=ActionRisk.HIGH,
                permissions=["filesystem:write"],
                is_destructive=False,
                requires_confirmation=False,
                execution_backend="coding_backend",
                supports_undo=True,
                rollback_description="Restore original file bytes from .aura_backup state",
                is_live=True,
                availability="online",
                requires=["workspace.walk"],
                verifies=["code.analyze"],
                rollback_capabilities=["code.rollback"],
                tags=["editor", "filesystem", "backup"],
            ),
            # 5. Automated Test Engine (Scaffolded Contract)
            Capability(
                name="code.test",
                domain=self.DOMAIN,
                description="Execute repository pytest/unittest test suites with exit-code classification.",
                category="verification",
                input_schema={
                    "type": "object",
                    "properties": {
                        "test_paths": {"type": "array", "items": {"type": "string"}},
                        "timeout": {"type": "integer", "default": 60},
                    },
                },
                output_schema={"type": "object", "properties": {"exit_code": {"type": "integer"}, "passed": {"type": "boolean"}}},
                risk_level=ActionRisk.MEDIUM,
                permissions=["process:execute"],
                execution_backend="coding_backend",
                is_live=False,
                availability="scaffolded",
                tags=["tests", "pytest", "scaffolded"],
            ),
            # 6. Bug Repair Loop (Scaffolded Contract)
            Capability(
                name="code.repair",
                domain=self.DOMAIN,
                description="Automated iterative syntax and regression repair loop with backup restoration on exhaustion.",
                category="repair",
                input_schema={
                    "type": "object",
                    "required": ["target_file", "error_message"],
                    "properties": {
                        "target_file": {"type": "string"},
                        "error_message": {"type": "string"},
                        "max_retries": {"type": "integer", "default": 3},
                    },
                },
                output_schema={"type": "object", "properties": {"repaired": {"type": "boolean"}}},
                risk_level=ActionRisk.HIGH,
                permissions=["filesystem:write", "process:execute"],
                execution_backend="coding_backend",
                supports_undo=True,
                is_live=False,
                availability="scaffolded",
                requires=["code.edit", "code.test"],
                verifies=["code.test"],
                tags=["repair", "loop", "scaffolded"],
            ),
            # 7. General Coding Capability (Live Catch-All Fallback)
            # Retained defensively for unclassified natural-language coding intents emitted by
            # TaskDecomposer when a goal does not match specific code.analyze/edit/generate/debug keywords.
            Capability(
                name="coding",
                domain=self.DOMAIN,
                description="General coding intelligence, planning, editing, and execution dispatch.",
                category="general",
                risk_level=ActionRisk.MEDIUM,
                permissions=["filesystem:read", "filesystem:write"],
                execution_backend="coding_backend",
                is_live=True,
                availability="online",
                tags=["coding", "general", "catch_all"],
            ),
        ]
        return {cap.name: cap for cap in caps}

    def list_capabilities(self) -> list[Capability]:
        return list(self._capabilities.values())

    def get_capability(self, name: str) -> Capability | None:
        return self._capabilities.get(name)
