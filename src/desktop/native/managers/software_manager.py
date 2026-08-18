"""
Software & Package Manager
Location: src/desktop/native/managers/software_manager.py

Manages system applications (winget, choco, scoop), Python packages (pip),
and Node.js modules (npm) with mandatory HMAC-SHA256 human approval gates.

CRITICAL SECURITY INVARIANT & ARCHITECTURAL MODEL:
1. Autonomous Mutation: 100% HARD-BLOCKED. Autonomous agents cannot install, uninstall, or update packages.
2. Single-Layer Host Boundary: Once a ticket is redeemed, installers execute in the host user context
   with full host permissions (necessary for winget to write to %ProgramFiles%/HKLM and pip to modify .venv).
   Consequently, for software mutations, the HMAC-SHA256 approval ticket is NOT defense-in-depth;
   it is the SOLE and ULTIMATE security boundary (no DACL or sandbox fallback exists post-redemption).
3. Cryptographic Target Binding: Every approval ticket is deterministically bound via HMAC-SHA256
   to the EXACT package identifier (e.g. 'requests' vs 'malicious-pkg') and capability name.
   Any parameter substitution or token reuse across packages immediately triggers a cryptographic
   signature mismatch and aborts execution before any host process can spawn.
4. Read-Only Operations: Search and enumeration execute safely via winreg and sandboxed query runners.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import winreg
from typing import Any

from ..desktop_result import DesktopResult
from ..sandbox.sandbox_manager import SandboxManager
from ..security.approval_authority import CryptographicApprovalAuthority
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# Safe package identifier regex (disallow flags, pipes, semicolons, shell redirection)
SAFE_PACKAGE_REGEX = re.compile(r"^[A-Za-z0-9_.\-@/:\s=<>~^]+$")


class SoftwareManager(BaseNativeManager):
    """
    Manages package installations, software updates, search, and pip/npm packages.

    Security Invariant:
    All mutating actions are cryptographically gated by HMAC-SHA256 tickets bound to the exact
    package target. Post-redemption execution runs in host context; ticket verification is the
    exclusive gate preventing unauthorized system mutations.
    """

    NAME = "software"
    VERSION = "1.0"
    PRIORITY = 35
    DEPENDENCIES: list[str] = ["terminal"]

    MUTATING_CAPABILITIES = {
        "software.install",
        "software.uninstall",
        "software.update",
        "software.update_all",
        "pip.install",
        "npm.install",
        "npm.install_with_scripts",
    }

    FORBIDDEN_INSTALLER_KEYWORDS = {
        "--extra-index-url",
        "--index-url",
        "--find-links",
        "--trusted-host",
        "--registry",
        "--source",
    }

    def __init__(
        self,
        auth: CryptographicApprovalAuthority | None = None,
        sandbox: SandboxManager | None = None,
    ):
        super().__init__()
        self._auth: CryptographicApprovalAuthority = auth or CryptographicApprovalAuthority.get_instance()
        self._sandbox: SandboxManager = sandbox or SandboxManager.get_instance()
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        return self._auth

    @property
    def capabilities(self) -> list[str]:
        return [
            "software.list_installed",
            "software.search",
            "software.install",
            "software.uninstall",
            "software.update",
            "software.update_all",
            "pip.install",
            "npm.install",
            "npm.install_with_scripts",
        ]

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        sandbox_hc = self._sandbox.health_check()
        return HealthCheckResult(
            manager_name=self.name,
            status=HealthStatus.HEALTHY,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={
                "initialized": self._initialized,
                "security_model": "cryptographic_hmac_human_approval_gate",
                "sandbox_provider": sandbox_hc.get("active_provider"),
            },
        )

    def shutdown(self) -> None:
        self._initialized = False

    def _validate_package_name(self, name: str) -> tuple[bool, str]:
        """Validate that package name does not contain shell injection metacharacters or flags."""
        clean = name.strip()
        if not clean:
            return False, "Package name cannot be empty."
        if clean.startswith("-"):
            return False, f"Package name cannot start with flag argument: {clean}"
        if any(bad in clean.lower() for bad in self.FORBIDDEN_INSTALLER_KEYWORDS):
            return False, f"Forbidden installer flag injection detected: {clean}"
        if not SAFE_PACKAGE_REGEX.match(clean):
            return False, f"Package name contains illegal characters or metacharacters: {clean}"
        return True, clean

    def _list_installed_apps(self) -> list[dict[str, str]]:
        """
        Safely inspect Windows Registry for installed applications
        without invoking PowerShell subprocesses.
        """
        apps: list[dict[str, str]] = []
        seen_names: set[str] = set()

        registry_roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_READ | getattr(winreg, "KEY_WOW64_32KEY", 0)),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_READ),
        ]

        for hkey, subkey, access in registry_roots:
            try:
                with winreg.OpenKey(hkey, subkey, 0, access) as root_key:
                    num_subkeys, _, _ = winreg.QueryInfoKey(root_key)
                    for i in range(num_subkeys):
                        try:
                            key_name = winreg.EnumKey(root_key, i)
                            with winreg.OpenKey(root_key, key_name, 0, access) as item_key:
                                display_name = ""
                                try:
                                    display_name, _ = winreg.QueryValueEx(item_key, "DisplayName")
                                except OSError:
                                    continue

                                if not display_name or display_name in seen_names:
                                    continue

                                display_version = ""
                                try:
                                    display_version, _ = winreg.QueryValueEx(item_key, "DisplayVersion")
                                except OSError:
                                    pass

                                publisher = ""
                                try:
                                    publisher, _ = winreg.QueryValueEx(item_key, "Publisher")
                                except OSError:
                                    pass

                                seen_names.add(display_name)
                                apps.append({
                                    "name": str(display_name),
                                    "version": str(display_version),
                                    "publisher": str(publisher),
                                })
                        except OSError:
                            continue
            except OSError:
                continue

        apps.sort(key=lambda x: x["name"].lower())
        return apps

    def _run_approved_installer(self, cmd: list[str], timeout: float = 180.0) -> tuple[int, str, str]:
        """
        Execute an approved software installer command in the host execution context
        after human HMAC authorization has been verified and redeemed.
        Cleans and sanitizes environment variables to prevent index URL or hook tampering.
        """
        clean_env = dict(os.environ)
        for var in [
            "PIP_INDEX_URL",
            "PIP_EXTRA_INDEX_URL",
            "PIP_FIND_LINKS",
            "PIP_TRUSTED_HOST",
            "npm_config_registry",
            "npm_config_scripts_prepend_node_path",
            "NODE_OPTIONS",
            "PYTHONPATH",
        ]:
            clean_env.pop(var, None)

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=clean_env,
        )

        try:
            from ..security.audit_logger import SecurityAuditLogger
            SecurityAuditLogger.get_instance().log_event(
                event_type="INSTALLER_EXECUTED",
                action_type="host_installer",
                target=" ".join(cmd),
                status="SUCCESS" if proc.returncode == 0 else "FAILURE",
                details={"exit_code": proc.returncode, "cmd": cmd},
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failed on installer execution: {audit_err}")

        return proc.returncode, proc.stdout, proc.stderr

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        args = arguments or {}
        cap = capability.lower()

        try:
            # 1. Read-only: List installed applications
            if cap == "software.list_installed":
                apps = self._list_installed_apps()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"installed": apps, "count": len(apps)},
                )

            # 2. Read-only: Search software
            elif cap == "software.search":
                raw_name = args.get("name") or args.get("package") or args.get("query") or goal
                valid, sanitized = self._validate_package_name(str(raw_name))
                if not valid:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name, error=sanitized
                    )
                code, out, err = self._sandbox.execute(f'winget search "{sanitized}"')
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"search_query": sanitized, "results": out, "exit_code": code},
                )

            # 3. Mutating / High-Risk Operations: Require HMAC Human Approval Gate
            elif cap in self.MUTATING_CAPABILITIES:
                target_pkg = args.get("package") or args.get("name") or args.get("id") or goal
                if cap == "software.update_all":
                    target_pkg = "all_installed_packages"

                valid, sanitized_pkg = self._validate_package_name(str(target_pkg))
                if not valid:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name, error=sanitized_pkg
                    )

                action_params = {"capability": cap, "target": sanitized_pkg}

                ticket_id = args.get("approval_ticket_id")
                signature = args.get("approval_signature")

                if not ticket_id or not signature:
                    # Issue new un-signed approval ticket
                    issued_ticket_id = self._auth.create_ticket(
                        action_type=cap,
                        target=sanitized_pkg,
                        parameters=action_params,
                        description=f"Human authorization required to execute {cap} on '{sanitized_pkg}'",
                    )
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Software management operation '{cap}' requires cryptographic human approval.",
                        data={
                            "requires_confirmation": True,
                            "approval_ticket_id": issued_ticket_id,
                            "action_type": cap,
                            "target": sanitized_pkg,
                            "risk_tier": "confirmation_required",
                        },
                    )

                # Verify cryptographic signature
                valid_sig, auth_err = self._auth.verify_and_redeem(
                    ticket_id, signature, action_type=cap, target=sanitized_pkg, parameters=action_params
                )
                if not valid_sig:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Human authorization failed: {auth_err}",
                        data={"security_alert": "unauthorized_or_forged_approval"},
                    )

                # Signature verified: Dispatch installer in authorized host context with pinned registries
                if cap == "software.install":
                    cmd = ["winget", "install", "--id", sanitized_pkg, "-e", "--source", "winget", "--accept-source-agreements", "--accept-package-agreements"]
                    code, out, err = self._run_approved_installer(cmd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"package": sanitized_pkg, "exit_code": code, "output": out, "error": err},
                        events=["software_installed"],
                    )

                elif cap == "software.uninstall":
                    cmd = ["winget", "uninstall", "--id", sanitized_pkg]
                    code, out, err = self._run_approved_installer(cmd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"package": sanitized_pkg, "exit_code": code, "output": out, "error": err},
                        events=["software_uninstalled"],
                    )

                elif cap == "software.update":
                    cmd = ["winget", "upgrade", "--id", sanitized_pkg]
                    code, out, err = self._run_approved_installer(cmd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"package": sanitized_pkg, "exit_code": code, "output": out, "error": err},
                        events=["software_updated"],
                    )

                elif cap == "software.update_all":
                    cmd = ["winget", "upgrade", "--all", "--accept-source-agreements"]
                    code, out, err = self._run_approved_installer(cmd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"exit_code": code, "output": out, "error": err},
                        events=["all_software_updated"],
                    )

                elif cap == "pip.install":
                    cmd = [sys.executable, "-m", "pip", "install", "--index-url", "https://pypi.org/simple", sanitized_pkg]
                    code, out, err = self._run_approved_installer(cmd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"package": sanitized_pkg, "exit_code": code, "output": out, "error": err},
                        events=["pip_installed"],
                    )

                elif cap == "npm.install":
                    cmd = ["npm.cmd", "install", "--registry=https://registry.npmjs.org", "--ignore-scripts", sanitized_pkg]
                    code, out, err = self._run_approved_installer(cmd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"package": sanitized_pkg, "exit_code": code, "output": out, "error": err},
                        events=["npm_installed"],
                    )

                elif cap == "npm.install_with_scripts":
                    cmd = ["npm.cmd", "install", "--registry=https://registry.npmjs.org", sanitized_pkg]
                    code, out, err = self._run_approved_installer(cmd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"package": sanitized_pkg, "exit_code": code, "output": out, "error": err},
                        events=["npm_installed_with_scripts"],
                    )

            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported software capability: {capability}",
                )

        except Exception as exc:
            logger.error(f"SoftwareManager.{cap} failed: {exc}")
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=f"Software management failed: {exc}"
            )
