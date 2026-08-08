"""
FileManager Native Desktop Manager
Manages native OS file creation, writing, reading, and deletion operations.
"""

import os
from pathlib import Path
from typing import Any

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus


class FileManager(BaseNativeManager):
    """
    Manages native desktop filesystem operations.

    Capabilities:
    - file.create: Create a new file or directory
    - file.write: Write content to a file
    - file.read: Read content from a file
    - file.delete: Delete a file
    """

    NAME = "file"
    VERSION = "1.0"
    PRIORITY = 20
    DEPENDENCIES = []

    def __init__(self):
        super().__init__()
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        return [
            "file.create",
            "file.write",
            "file.read",
            "file.delete",
            "create_file",
            "write_file",
        ]

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            manager_name=self.name,
            status=HealthStatus.HEALTHY,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={"initialized": self._initialized},
        )

    def shutdown(self) -> None:
        self._initialized = False

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        args = arguments or {}
        file_path_str = (
            args.get("file_path")
            or args.get("path")
            or args.get("target_file")
            or args.get("file")
        )
        content = args.get("content") or args.get("text") or ""

        import re

        if not file_path_str:
            m_path = re.search(r"['\"]([^'\"]+\.[a-zA-Z0-9]+)['\"]", goal)
            if m_path:
                file_path_str = m_path.group(1)

        if not content:
            matches = re.findall(r"['\"]([^'\"]+)['\"]", goal)
            for text in matches:
                if text != file_path_str:
                    content = text
                    break

        # No silent fallback — if content is still empty, fail loudly.
        # This surfaces upstream pipeline failures (e.g. research backend
        # produced no output) instead of silently writing placeholder text.
        if not content:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="No content provided for file creation. "
                "The upstream artifact may have failed to produce a payload.",
            )

        if not file_path_str:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="No target file path provided in arguments or goal",
            )

        target_path = Path(file_path_str).resolve()

        try:
            cap_clean = capability.lower().replace("_", ".")
            if cap_clean in ["file.create", "file.write", "create.file", "write.file"]:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "path": str(target_path),
                        "bytes_written": len(content.encode("utf-8")),
                    },
                    events=["file_created"],
                )
            elif cap_clean == "file.read":
                if not target_path.exists():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"File not found: {target_path}",
                    )
                with open(target_path, encoding="utf-8") as f:
                    data = f.read()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "content": data},
                )
            elif cap_clean == "file.delete":
                if target_path.exists():
                    target_path.unlink()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "deleted": True},
                    events=["file_deleted"],
                )
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported file capability: {capability}",
                )
        except Exception as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"File operation failed: {exc}",
            )
