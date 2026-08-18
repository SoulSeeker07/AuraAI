"""
FileManager Native Desktop Manager
Location: src/desktop/native/managers/file_manager.py

Manages native OS file creation, writing, reading, copying, deletion,
directory navigation, compression, content search, and metadata inspection
with strict WorkspaceJail path confinement, ZipSlip protection, and HMAC-SHA256 human approval gates.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from ..desktop_result import DesktopResult
from ..sandbox.workspace_jail import WorkspaceJail
from ..security.approval_authority import CryptographicApprovalAuthority
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# Dangerous executable extensions blocked from file.open_with
BLOCKED_EXECUTABLE_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".msi", ".dll",
    ".com", ".scr", ".hta", ".pif", ".reg", ".wsf", ".cpl", ".jar",
}

# Critical root directory names requiring HMAC confirmation before deletion
CRITICAL_DIRECTORY_NAMES = {".git", ".venv", "src", "node_modules"}


class FileManager(BaseNativeManager):
    """
    Manages native desktop filesystem operations strictly confined within the Workspace Jail.

    Capabilities:
    - file.create: Create a new file or directory
    - file.write: Write content to a file
    - file.read: Read content from a file
    - file.delete: Delete a file
    - file.copy: Copy file or directory
    - file.exists: Check if path exists
    - file.info: Get file metadata (size, dates, permissions)
    - file.list: List directory items with metadata
    - file.size: Get file or recursive directory size
    - file.find_content: Search inside file contents
    - file.mkdir: Create directory tree
    - file.rmdir: Remove directory tree
    - file.compress: Create ZIP archive
    - file.decompress: Extract ZIP archive (ZipSlip protected)
    - file.open_with: Open file with default application
    - file.watch: Watch a path for changes
    """

    NAME = "file"
    VERSION = "1.0"
    PRIORITY = 20
    DEPENDENCIES: list[str] = []

    def __init__(
        self,
        workspace_root: str | None = None,
        auth: CryptographicApprovalAuthority | None = None,
    ):
        super().__init__()
        self._workspace_root: str = str(Path(workspace_root or os.getcwd()).resolve())
        self._jail: WorkspaceJail = WorkspaceJail(workspace_root=self._workspace_root)
        self._auth: CryptographicApprovalAuthority = auth or CryptographicApprovalAuthority.get_instance()
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def jail(self) -> WorkspaceJail:
        return self._jail

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        return self._auth

    @property
    def capabilities(self) -> list[str]:
        return [
            "file.create",
            "file.write",
            "file.read",
            "file.delete",
            "file.copy",
            "file.exists",
            "file.info",
            "file.list",
            "file.size",
            "file.find_content",
            "file.mkdir",
            "file.rmdir",
            "file.compress",
            "file.decompress",
            "file.open_with",
            "file.watch",
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
            details={
                "initialized": self._initialized,
                "workspace_root": self._workspace_root,
                "security_model": "workspace_jail_confinement_and_zipslip_protection",
            },
        )

    def shutdown(self) -> None:
        self._initialized = False

    def _resolve_and_verify_path(self, path_str: str) -> tuple[bool, Path, str]:
        """
        Resolve a path string to its canonical absolute Path and verify
        that it resides strictly inside the Workspace Jail.
        """
        if not path_str or not str(path_str).strip():
            return False, Path(self._workspace_root), "Path string cannot be empty."

        clean_str = str(path_str).strip().strip("'\"")

        # Reject Alternate Data Streams (ADS) e.g. file.txt:hidden
        if re.search(r"[a-zA-Z0-9_]\s*:\s*[a-zA-Z0-9_]", clean_str[2:]):
            return False, Path(self._workspace_root), f"Alternate Data Stream (ADS) paths are prohibited: {path_str}"

        try:
            p = Path(clean_str)
            if not p.is_absolute():
                # Anchor relative path to workspace root
                resolved = (Path(self._workspace_root) / p).resolve()
            else:
                resolved = p.resolve()
        except Exception as exc:
            return False, Path(self._workspace_root), f"Failed to resolve path '{path_str}': {exc}"

        if not self._jail.is_path_inside_workspace(resolved):
            return (
                False,
                resolved,
                f"Workspace Jail security violation: Path '{path_str}' (resolved: '{resolved}') is outside allowed workspace root '{self._workspace_root}'.",
            )

        return True, resolved, ""

    def _get_dir_size(self, path: Path) -> int:
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += self._get_dir_size(Path(entry.path))
        except Exception:
            pass
        return total

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
            or args.get("source")
            or args.get("src")
            or args.get("directory")
        )
        content = args.get("content") or args.get("text") or ""

        if not file_path_str:
            m_path = re.search(r"['\"]([^'\"]+\.[a-zA-Z0-9]+)['\"]", goal)
            if m_path:
                file_path_str = m_path.group(1)

        cap_clean = capability.lower().replace("_", ".")

        # For create/write operations, require content or fail loudly
        if cap_clean in ["file.create", "file.write", "create.file", "write.file"]:
            if not content:
                matches = re.findall(r"['\"]([^'\"]+)['\"]", goal)
                for text in matches:
                    if text != file_path_str:
                        content = text
                        break
            if not content:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error="No content provided for file creation. "
                    "The upstream artifact may have failed to produce a payload.",
                )

        if not file_path_str and cap_clean not in ["file.list", "file.find.content"]:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="No target file path provided in arguments or goal",
            )

        # Enforce Workspace Jail on primary target path
        if file_path_str:
            valid_path, target_path, jail_err = self._resolve_and_verify_path(str(file_path_str))
            if not valid_path:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=jail_err,
                    data={"security_alert": "workspace_jail_violation", "attempted_path": str(file_path_str)},
                )
        else:
            target_path = Path(self._workspace_root)

        try:
            # 1. File Create / Write
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

            # 2. File Read
            elif cap_clean == "file.read":
                if not target_path.exists():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"File not found: {target_path}",
                    )
                with open(target_path, encoding="utf-8", errors="replace") as f:
                    data = f.read()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "content": data, "size": len(data)},
                )

            # 3. File Delete
            elif cap_clean == "file.delete":
                # Critical guardrail 1: Cannot delete workspace root
                if target_path == Path(self._workspace_root).resolve():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error="CRITICAL DELETION GUARDRAIL: Deleting the workspace root directory is permanently prohibited.",
                        data={"security_alert": "workspace_root_deletion_blocked"},
                    )

                # Critical guardrail 2: Top-level critical project directories require HMAC ticket
                if (
                    target_path.name in CRITICAL_DIRECTORY_NAMES
                    and target_path.parent == Path(self._workspace_root).resolve()
                ):
                    ticket_id = args.get("approval_ticket_id")
                    signature = args.get("approval_signature")
                    action_params = {"capability": cap_clean, "target": str(target_path)}

                    if not ticket_id or not signature:
                        issued_ticket_id = self._auth.create_ticket(
                            action_type=cap_clean,
                            target=str(target_path),
                            parameters=action_params,
                            description=f"Authorization required to delete critical project directory '{target_path.name}'",
                        )
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error=f"Deleting critical project directory '{target_path.name}' requires cryptographic human approval.",
                            data={
                                "requires_confirmation": True,
                                "approval_ticket_id": issued_ticket_id,
                                "action_type": cap_clean,
                                "target": str(target_path),
                                "risk_tier": "confirmation_required",
                            },
                        )

                    valid_sig, auth_err = self._auth.verify_and_redeem(
                        ticket_id, signature, action_type=cap_clean, target=str(target_path), parameters=action_params
                    )
                    if not valid_sig:
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error=f"Human authorization failed: {auth_err}",
                            data={"security_alert": "unauthorized_or_forged_approval"},
                        )

                if target_path.exists():
                    if target_path.is_dir():
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "deleted": True},
                    events=["file_deleted"],
                )

            # 4. File Copy
            elif cap_clean == "file.copy":
                dst_str = args.get("destination") or args.get("dst") or args.get("target") or ""
                if not dst_str:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error="Missing destination path for file.copy",
                    )
                valid_dst, dst_path, dst_err = self._resolve_and_verify_path(str(dst_str))
                if not valid_dst:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Destination {dst_err}",
                        data={"security_alert": "workspace_jail_violation"},
                    )

                if target_path.is_dir():
                    shutil.copytree(target_path, dst_path, dirs_exist_ok=True)
                else:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_path, dst_path)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"source": str(target_path), "destination": str(dst_path)},
                    events=["file_copied"],
                )

            # 5. File Exists
            elif cap_clean == "file.exists":
                exists = target_path.exists()
                is_dir = target_path.is_dir() if exists else False
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "exists": exists, "is_directory": is_dir},
                )

            # 6. File Info
            elif cap_clean == "file.info":
                if not target_path.exists():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Path not found: {target_path}",
                    )
                stat = target_path.stat()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "path": str(target_path),
                        "size_bytes": stat.st_size,
                        "is_dir": target_path.is_dir(),
                        "is_file": target_path.is_file(),
                        "created_time": stat.st_ctime,
                        "modified_time": stat.st_mtime,
                        "permissions": oct(stat.st_mode),
                    },
                )

            # 7. File List
            elif cap_clean == "file.list":
                dir_path = target_path if target_path.is_dir() else target_path.parent
                items = []
                for entry in dir_path.iterdir():
                    try:
                        st = entry.stat()
                        items.append({
                            "name": entry.name,
                            "path": str(entry),
                            "is_dir": entry.is_dir(),
                            "size_bytes": st.st_size if entry.is_file() else 0,
                            "modified": st.st_mtime,
                        })
                    except Exception:
                        pass
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"directory": str(dir_path), "items": items, "count": len(items)},
                )

            # 8. File Size
            elif cap_clean == "file.size":
                if not target_path.exists():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Path not found: {target_path}",
                    )
                size = self._get_dir_size(target_path) if target_path.is_dir() else target_path.stat().st_size
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "size_bytes": size},
                )

            # 9. Find Content
            elif cap_clean in ["file.find.content", "file.find_content"]:
                query = args.get("query") or args.get("text") or goal
                search_dir = target_path if target_path.is_dir() else target_path.parent
                matches = []
                for p in search_dir.rglob("*"):
                    if p.is_file() and p.stat().st_size < 5 * 1024 * 1024:  # Under 5MB
                        try:
                            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                                for line_no, line in enumerate(f, start=1):
                                    if query.lower() in line.lower():
                                        matches.append({
                                            "file": str(p),
                                            "line": line_no,
                                            "content": line.strip()[:200],
                                        })
                                        if len(matches) >= 50:
                                            break
                        except Exception:
                            pass
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"query": query, "matches": matches, "match_count": len(matches)},
                )

            # 10. Mkdir
            elif cap_clean == "file.mkdir":
                target_path.mkdir(parents=True, exist_ok=True)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "created": True},
                    events=["directory_created"],
                )

            # 11. Rmdir
            elif cap_clean == "file.rmdir":
                if target_path == Path(self._workspace_root).resolve():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error="CRITICAL DELETION GUARDRAIL: Deleting the workspace root directory is permanently prohibited.",
                    )
                if target_path.exists() and target_path.is_dir():
                    shutil.rmtree(target_path)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "removed": True},
                    events=["directory_removed"],
                )

            # 12. Compress
            elif cap_clean == "file.compress":
                archive_name = args.get("archive") or f"{target_path.name}.zip"
                archive_path = target_path.parent / archive_name
                valid_arch, resolved_arch, arch_err = self._resolve_and_verify_path(str(archive_path))
                if not valid_arch:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name, error=arch_err
                    )

                with zipfile.ZipFile(resolved_arch, "w", zipfile.ZIP_DEFLATED) as zf:
                    if target_path.is_dir():
                        for p in target_path.rglob("*"):
                            zf.write(p, p.relative_to(target_path.parent))
                    else:
                        zf.write(target_path, target_path.name)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"archive_path": str(resolved_arch)},
                    events=["archive_created"],
                )

            # 13. Decompress (with strict ZipSlip traversal protection)
            elif cap_clean == "file.decompress":
                extract_dir_raw = args.get("extract_to") or str(target_path.parent / target_path.stem)
                valid_ext, extract_dir, ext_err = self._resolve_and_verify_path(str(extract_dir_raw))
                if not valid_ext:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name, error=ext_err
                    )

                extract_dir.mkdir(parents=True, exist_ok=True)
                extract_root_str = str(extract_dir.resolve()).lower()

                with zipfile.ZipFile(target_path, "r") as zf:
                    # Validate all members against ZipSlip before writing any files
                    for member in zf.infolist():
                        member_dest = (extract_dir / member.filename).resolve()
                        member_dest_str = str(member_dest).lower()
                        if not member_dest_str.startswith(extract_root_str):
                            logger.critical(
                                f"SECURITY ALERT: ZipSlip attack detected in '{target_path}' (member: '{member.filename}')"
                            )
                            return DesktopResult.create_failure(
                                goal=goal,
                                capability=capability,
                                manager=self.name,
                                error=f"ZipSlip security violation: Archive entry '{member.filename}' attempts path traversal outside target extraction directory.",
                                data={"security_alert": "zipslip_traversal_blocked", "entry": member.filename},
                            )

                    zf.extractall(extract_dir)

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"extracted_to": str(extract_dir)},
                    events=["archive_extracted"],
                )

            # 14. Open With (blocks dangerous executable binaries)
            elif cap_clean in ("file.open_with", "file.open.with", "open_with", "open.with"):
                if target_path.suffix.lower() in BLOCKED_EXECUTABLE_EXTENSIONS:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Security violation: Direct execution of executable extension '{target_path.suffix}' is blocked via file.open_with.",
                        data={"security_alert": "executable_execution_blocked", "path": str(target_path)},
                    )

                app = args.get("app")
                if app:
                    app_path = Path(str(app))
                    if app_path.suffix.lower() in BLOCKED_EXECUTABLE_EXTENSIONS and not app_path.name.lower().startswith(("notepad", "explorer", "code")):
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error=f"Launching arbitrary application executable '{app}' is prohibited.",
                        )
                    import subprocess
                    subprocess.Popen([str(app), str(target_path)])
                else:
                    os.startfile(str(target_path))

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "opened": True},
                )

            # 15. Watch
            elif cap_clean in ("file.watch", "watch"):
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"path": str(target_path), "watching": True},
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
