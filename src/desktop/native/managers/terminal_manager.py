"""
Terminal / Shell Execution Manager
Location: src/desktop/native/managers/terminal_manager.py

Provides synchronous and asynchronous command-line execution, session management,
working directory tracking, and environment control for agentic CLI workflows.

Security Architecture:
1. De-obfuscation Pipeline: Normalizes backticks, string concatenations, and token-split quotes.
2. Dynamic System Root Protection: Resolves %SystemDrive%, %WINDIR%, %ProgramFiles% dynamically.
3. Strict Executable Allowlist: Scopes autonomous CLI execution to developer tools (git, pytest, python, etc.).
4. Cryptographic Human-in-the-Loop Gate (HMAC-SHA256):
   - High-risk commands return an un-signed ticket_id and halt autonomous execution.
   - Only the out-of-band Human UI/CLI channel possessing the internal HMAC secret can generate a valid signature.
   - LLM self-supplied tokens or replay attacks fail constant-time comparison (hmac.compare_digest).
5. Stdin Guardrails: Applies full evaluation to `terminal.send_input`.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import re
import secrets
import subprocess
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ..desktop_result import DesktopResult
from ..sandbox import IsolationLevel, SandboxManager
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class CommandRiskTier(Enum):
    """Classification tiers for terminal command execution risk."""
    SAFE_ALLOWLIST = "safe_allowlist"
    WORKSPACE_DEV = "workspace_dev"
    CONFIRMATION_REQUIRED = "confirmation_required"
    HARD_BLOCKED = "hard_blocked"


# Dynamic system root detection (resolves system drive, windows dir, user profile at runtime)
_SYSTEM_DRIVE = os.environ.get("SystemDrive", "C:").lower()
_WINDIR = os.environ.get("WINDIR", f"{_SYSTEM_DRIVE}\\windows").lower()
_PROGFILES = os.environ.get("ProgramFiles", f"{_SYSTEM_DRIVE}\\program files").lower()
_PROGFILES86 = os.environ.get("ProgramFiles(x86)", f"{_SYSTEM_DRIVE}\\program files (x86)").lower()
_USERPROFILE = os.environ.get("USERPROFILE", f"{_SYSTEM_DRIVE}\\users").lower()

PROTECTED_SYSTEM_PATHS: set[str] = {
    _SYSTEM_DRIVE,
    f"{_SYSTEM_DRIVE}\\",
    f"{_SYSTEM_DRIVE}/",
    _WINDIR,
    f"{_WINDIR}\\system32",
    _PROGFILES,
    _PROGFILES86,
    _USERPROFILE,
    "\\",
    "/",
}

# Strict Developer Executable Allowlist for autonomous execution in workspace
# Note: Shell interpreters (powershell, pwsh, cmd, bash, sh) are strictly EXCLUDED
# to prevent nested-shell bypasses of the allowlist boundary.
ALLOWED_CLI_EXECUTABLES: set[str] = {
    "git", "pytest", "python", "py", "node", "npm", "npx", "cargo",
    "go", "ruff", "black", "mypy", "dotnet", "rustc", "tsc", "pip",
    "pipenv", "poetry", "uv", "pnpm", "yarn", "deno", "bun", "gh",
}



# Tier 3: Hard Blocked Exploits, Tampering, Obfuscation & System Destruction
HARD_BLOCKED_PATTERNS: list[re.Pattern] = [
    # 1. Remote Download & Execute / Code Injection
    re.compile(r"\b(invoke-expression|iex)\b", re.I),
    re.compile(r"\b(iwr|invoke-webrequest|curl|wget)\b.*\|\s*(iex|invoke-expression|powershell|pwsh|cmd|sh|bash)", re.I),
    re.compile(r"\b(downloadstring|downloaddata|downloadfile)\b", re.I),
    re.compile(r"\[System\.Convert\]::FromBase64String", re.I),
    re.compile(r"-encodedcommand|-e\s+[A-Za-z0-9+/=]{10,}", re.I),
    re.compile(r"\[ScriptBlock\]::Create", re.I),
    re.compile(r"&\s*\$[A-Za-z0-9_]+", re.I),  # Obfuscated call via variable: & $var

    # 2. Antivirus & Security Tampering
    re.compile(r"\b(set-mppreference|add-mppreference)\b.*-(disablerealtime|exclusionpath|disablebehavior)", re.I),
    re.compile(r"\bset-executionpolicy\b.*(unrestricted|bypass)", re.I),
    re.compile(r"\b(fltmc|vssadmin|wbadmin)\b", re.I),

    # 3. Credential Harvesting & Sensitive Store Access
    re.compile(r"(\.ssh[/\\]id_|id_rsa|id_ed25519|credentials\.json|\.aws[/\\]credentials)", re.I),
    re.compile(r"\b(mimikatz|procdump|sekurlsa|lsass|sam\.save|ntds\.dit)\b", re.I),

    # 4. System Shutdown / Reboot / Bricking
    re.compile(r"\b(stop-computer|restart-computer)\b", re.I),
    re.compile(r"\bshutdown\s+[/|-][srfa]", re.I),
    re.compile(r"\bbcdedit\b", re.I),

    # 5. Disk Formatting & Partition Wiping
    re.compile(r"\b(format-volume|clear-disk|initialize-disk|diskpart|mkfs|fdisk)\b", re.I),
    re.compile(r"\bformat\s+[a-z]:", re.I),

    # 6. Recursive Root / System Drive Deletion
    re.compile(r"\b(remove-item|ri|rni|rm|del|erase|rd|rmdir)\b.*(-r|-recurse).*(-f|-force)?.*(\b[c-z]:\\?|\$env:systemdrive|\b\\|\b/\b)", re.I),
    re.compile(r"\b(remove-item|ri|rni|rm|del|erase|rd|rmdir)\b.*(-f|-force).*(-r|-recurse)?.*(\b[c-z]:\\?|\$env:systemdrive|\b\\|\b/\b)", re.I),
    re.compile(r"\b(rmdir|rd)\s+/(s|q)\s+/(s|q)?\s*[a-z]:\\?", re.I),
    re.compile(r"\bdel\s+/[fsq]+\s*[a-z]:\\?", re.I),

    # 7. Registry System Destruction
    re.compile(r"\breg\s+delete\s+(hklm|hkey_local_machine)", re.I),
    re.compile(r"\bremove-item\s+(hklm:|registry::hkey_local_machine)", re.I),

    # 8. Fork Bombs
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.I),
    re.compile(r"%\s*0\s*\|\s*%\s*0", re.I),
]

# Tier 1: Known Safe Read-Only / Diagnostic Prefix Allowlist
SAFE_INSPECTION_PREFIXES: list[str] = [
    "git status", "git log", "git diff", "git branch", "git show", "git tag",
    "Get-ChildItem", "dir", "ls", "Get-Content", "cat", "type", "Get-Process",
    "Get-Service", "Get-Command", "Get-Help", "Get-Date", "Get-Location", "pwd",
    "Select-String", "findstr", "grep", "echo", "Write-Output", "Write-Host",
    "python --version", "node --version", "npm --version", "git --version",
    "pytest --version", "ruff --version", "black --version", "ipconfig", "ping",
]


from ..security.approval_authority import ApprovalTicket, CryptographicApprovalAuthority
from ..security.network_policy import EgressDecision, NetworkPolicyEngine


class TerminalSession:
    """Represents a background terminal execution session."""

    def __init__(self, session_id: str, command: str, process: subprocess.Popen, cwd: str):
        self.session_id = session_id
        self.command = command
        self.process = process
        self.cwd = cwd
        self.output_buffer: list[str] = []

    def is_running(self) -> bool:
        return self.process.poll() is None

    def read_available_output(self) -> str:
        if not self.process.stdout:
            return ""
        try:
            lines = []
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                lines.append(line)
                self.output_buffer.append(line)
            return "".join(lines)
        except Exception:
            return ""

    def kill(self) -> None:
        try:
            self.process.terminate()
            self.process.wait(timeout=2.0)
        except Exception:
            self.process.kill()


class TerminalManager(BaseNativeManager):
    """
    Manages command-line execution (PowerShell / CMD), background sessions,
    working directories, environment variables, and multi-tier OS process sandboxes.
    """

    NAME = "terminal"
    VERSION = "1.0"
    PRIORITY = 10
    DEPENDENCIES: list[str] = []

    def __init__(
        self,
        auth: CryptographicApprovalAuthority | None = None,
        network_policy: NetworkPolicyEngine | None = None,
    ):
        super().__init__()
        self._cwd: str = os.getcwd()
        self._sessions: dict[str, TerminalSession] = {}
        self._auth: CryptographicApprovalAuthority = auth or CryptographicApprovalAuthority.get_instance()
        self._network_policy: NetworkPolicyEngine = network_policy or NetworkPolicyEngine.get_instance()
        self._sandbox: SandboxManager = SandboxManager.get_instance(workspace_root=self._cwd)
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        return self._auth

    @property
    def sandbox(self) -> SandboxManager:
        return self._sandbox

    @property
    def capabilities(self) -> list[str]:
        return [
            "terminal.execute",
            "terminal.execute_async",
            "terminal.send_input",
            "terminal.kill_session",
            "terminal.get_output",
            "terminal.list_sessions",
            "terminal.get_cwd",
            "terminal.set_cwd",
            "terminal.get_env",
            "terminal.set_env",
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
                "cwd": self._cwd,
                "active_sessions": len(self._sessions),
                "security_model": "cryptographic_hmac_human_approval_gate",
                "sandbox_tier": sandbox_hc.get("isolation_level"),
                "sandbox_provider": sandbox_hc.get("active_provider"),
            },
        )

    def shutdown(self) -> None:
        for session in list(self._sessions.values()):
            session.kill()
        self._sessions.clear()
        self._initialized = False

    def _normalize_command(self, command: str) -> str:
        """
        De-obfuscate command strings by stripping backtick escaping,
        string concatenation, format strings, and token split quotes.
        """
        norm = command.strip()
        # 1. Remove PowerShell backtick escape characters: e.g. i`e`x -> iex
        norm = norm.replace("`", "")
        # 2. Collapse string concatenations: e.g. 'Rem'+'ove' -> Remove
        norm = re.sub(r"['\"]\s*\+\s*['\"]", "", norm)
        # 3. Strip internal quotes inside words: e.g. i'e'x -> iex
        norm = re.sub(r"(?<=[A-Za-z0-9_])['\"](?=[A-Za-z0-9_])", "", norm)
        # 4. Collapse multiple spaces
        norm = re.sub(r"\s+", " ", norm)
        return norm

    def evaluate_command_risk(self, command: str, cwd: str | None = None) -> tuple[CommandRiskTier, str]:
        """
        Evaluate risk level of a command using tiered security rules,
        de-obfuscation normalization, executable allowlists, and CWD-aware path protection.
        
        Caller Tier-Awareness:
        - If active sandbox is host-level JobObject: Full allowlists, path jails, and HMAC gates are enforced.
        - If active sandbox is container/microVM: Filesystem detachment is guaranteed by container namespace.
        """
        raw_cmd = command.strip()
        normalized_cmd = self._normalize_command(raw_cmd)
        active_cwd = (cwd or self._cwd).lower().strip()

        # Check Tier 3: Hard blocked patterns (evaluated against both raw and normalized commands)
        for pattern in HARD_BLOCKED_PATTERNS:
            if pattern.search(raw_cmd) or pattern.search(normalized_cmd):
                return CommandRiskTier.HARD_BLOCKED, f"Matched hard-blocked security rule: {pattern.pattern}"

        # CWD-Aware Relative/Wildcard Deletion Protection
        if any(active_cwd == p or active_cwd.startswith(p + "\\") or active_cwd.startswith(p + "/") for p in PROTECTED_SYSTEM_PATHS):
            if re.search(r"\b(remove-item|ri|rni|rm|del|erase|rd|rmdir)\b.*(-r|-recurse)?.*(\*|\.\*|\*\.\*)", normalized_cmd, re.I):
                return CommandRiskTier.HARD_BLOCKED, f"Dangerous relative wildcard deletion attempted in protected CWD: {active_cwd}"

        # Mandatory Workspace Jail Check on Host Tiers (JobObject & RestrictedUser)
        if self._sandbox.isolation_level in (IsolationLevel.JOB_OBJECT, IsolationLevel.RESTRICTED_USER):
            jail = getattr(self._sandbox.active_provider, "workspace_jail", None)
            if not jail and hasattr(self._sandbox.active_provider, "_job_sandbox"):
                jail = getattr(self._sandbox.active_provider._job_sandbox, "workspace_jail", None)
            if jail:
                valid_paths, jail_err = jail.validate_command_paths(raw_cmd, active_cwd)
                if not valid_paths:
                    return CommandRiskTier.HARD_BLOCKED, f"Workspace Jail security violation: {jail_err}"

        # Network Egress & SSRF / DNS Rebinding Interception
        urls = re.findall(r"https?://[^\s\"'`<>]+", raw_cmd + " " + normalized_cmd)
        ips_and_hosts = re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::[0-9]+)?\b|metadata\.google\.internal|metadata\.azure\.com|instance-data", raw_cmd + " " + normalized_cmd)
        git_targets = re.findall(r"git@[a-zA-Z0-9.\-]+:[^\s\"'`<>]+", raw_cmd + " " + normalized_cmd)
        all_targets = set(urls + ips_and_hosts + git_targets)

        has_unlisted_network_egress = False
        unlisted_reason = ""
        for target in all_targets:
            decision, reason, _ = self._network_policy.evaluate_destination(target)
            if decision == EgressDecision.HARD_BLOCKED:
                return CommandRiskTier.HARD_BLOCKED, f"Network Policy Violation: {reason}"
            elif decision == EgressDecision.CONFIRMATION_REQUIRED:
                has_unlisted_network_egress = True
                unlisted_reason = reason

        # Check Tier 1: Safe read-only inspection prefixes
        for prefix in SAFE_INSPECTION_PREFIXES:
            if normalized_cmd.lower().startswith(prefix.lower()):
                return CommandRiskTier.SAFE_ALLOWLIST, "Matched safe inspection allowlist"

        # Check Tier 2: Scoped Developer Tool Allowlist
        first_token = normalized_cmd.split()[0].lower() if normalized_cmd.split() else ""
        first_token_clean = Path(first_token).stem.lower()
        if first_token_clean in ALLOWED_CLI_EXECUTABLES:
            if has_unlisted_network_egress:
                return (
                    CommandRiskTier.CONFIRMATION_REQUIRED,
                    f"Developer tool '{first_token_clean}' targets unlisted network destination: {unlisted_reason}",
                )
            return CommandRiskTier.WORKSPACE_DEV, f"Matched approved developer tool allowlist: {first_token_clean}"

        # Tier 4: Any non-allowlisted executable or high-risk verb requires Cryptographic Human Approval
        return CommandRiskTier.CONFIRMATION_REQUIRED, f"Command '{first_token_clean}' is outside safe developer allowlist and requires human approval."

    def _run_sync(
        self, command: str, cwd: str | None = None, timeout: float = 60.0
    ) -> tuple[int, str, str]:
        """Execute command synchronously through the active SandboxManager provider."""
        exec_cwd = cwd or self._cwd
        return self._sandbox.execute(command, cwd=exec_cwd, timeout=timeout)

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
            if cap == "terminal.get_cwd":
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"cwd": self._cwd},
                )

            elif cap == "terminal.set_cwd":
                new_path = args.get("path") or args.get("cwd") or ""
                target = Path(new_path).resolve()
                if not target.exists() or not target.is_dir():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Directory does not exist: {new_path}",
                    )
                self._cwd = str(target)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"cwd": self._cwd},
                    events=["cwd_changed"],
                )

            elif cap == "terminal.get_env":
                key = args.get("key")
                if key:
                    val = os.environ.get(key, "")
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"key": key, "value": val},
                    )
                else:
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"env": dict(os.environ)},
                    )

            elif cap == "terminal.set_env":
                key = args.get("key")
                value = args.get("value", "")
                if not key:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error="Missing 'key' argument for set_env",
                    )
                os.environ[key] = str(value)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"key": key, "value": str(value)},
                )

            elif cap == "terminal.list_sessions":
                active = []
                for sid, sess in list(self._sessions.items()):
                    active.append({
                        "session_id": sid,
                        "command": sess.command,
                        "is_running": sess.is_running(),
                        "cwd": sess.cwd,
                    })
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"sessions": active},
                )

            elif cap in ("terminal.execute", "execute_command", "run_command"):
                cmd = args.get("command") or args.get("cmd") or ""
                if not cmd and goal:
                    m = re.search(r"['\"](.*?)['\"]", goal)
                    cmd = m.group(1) if m else goal

                if not cmd.strip():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error="No command provided to execute.",
                    )

                exec_cwd = args.get("cwd") or self._cwd
                tier, reason = self.evaluate_command_risk(cmd, cwd=exec_cwd)

                if tier == CommandRiskTier.HARD_BLOCKED:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Command blocked by security policy: {reason}",
                    )

                if tier == CommandRiskTier.CONFIRMATION_REQUIRED:
                    ticket_id = args.get("approval_ticket_id")
                    signature = args.get("approval_signature")

                    if not ticket_id or not signature:
                        # Issue new un-signed approval ticket
                        issued_ticket_id = self._auth.create_ticket(cmd, exec_cwd)
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error=f"Command requires human authorization: {reason}",
                            data={
                                "requires_confirmation": True,
                                "approval_ticket_id": issued_ticket_id,
                                "command": cmd,
                                "cwd": exec_cwd,
                                "risk_tier": tier.value,
                            },
                        )

                    # Verify cryptographic signature
                    valid, auth_err = self._auth.verify_and_redeem(ticket_id, signature, cmd, exec_cwd)
                    if not valid:
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error=f"Human authorization failed: {auth_err}",
                            data={"security_alert": "unauthorized_or_forged_approval"},
                        )

                timeout = float(args.get("timeout", 60.0))
                code, stdout, stderr = self._run_sync(cmd, cwd=exec_cwd, timeout=timeout)

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "command": cmd,
                        "exit_code": code,
                        "stdout": stdout,
                        "stderr": stderr,
                        "cwd": exec_cwd,
                        "risk_tier": tier.value,
                    },
                    events=["command_executed"],
                )

            elif cap == "terminal.execute_async":
                cmd = args.get("command") or args.get("cmd") or ""
                if not cmd.strip():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error="No command provided for async execution.",
                    )

                exec_cwd = args.get("cwd") or self._cwd
                tier, reason = self.evaluate_command_risk(cmd, cwd=exec_cwd)

                if tier == CommandRiskTier.HARD_BLOCKED:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Command blocked by security policy: {reason}",
                    )

                if tier == CommandRiskTier.CONFIRMATION_REQUIRED:
                    ticket_id = args.get("approval_ticket_id")
                    signature = args.get("approval_signature")

                    if not ticket_id or not signature:
                        issued_ticket_id = self._auth.create_ticket(cmd, exec_cwd)
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error=f"Command requires human authorization: {reason}",
                            data={
                                "requires_confirmation": True,
                                "approval_ticket_id": issued_ticket_id,
                                "command": cmd,
                                "cwd": exec_cwd,
                                "risk_tier": tier.value,
                            },
                        )

                    valid, auth_err = self._auth.verify_and_redeem(ticket_id, signature, cmd, exec_cwd)
                    if not valid:
                        return DesktopResult.create_failure(
                            goal=goal,
                            capability=capability,
                            manager=self.name,
                            error=f"Human authorization failed: {auth_err}",
                            data={"security_alert": "unauthorized_or_forged_approval"},
                        )

                proc = subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
                    cwd=exec_cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                session_id = f"term_{uuid.uuid4().hex[:8]}"
                session = TerminalSession(session_id, cmd, proc, exec_cwd)
                self._sessions[session_id] = session

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"session_id": session_id, "command": cmd, "cwd": exec_cwd},
                    events=["session_started"],
                )

            elif cap == "terminal.get_output":
                sid = args.get("session_id", "")
                sess = self._sessions.get(sid)
                if not sess:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Session not found: {sid}",
                    )
                out = sess.read_available_output()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={
                        "session_id": sid,
                        "output": out,
                        "is_running": sess.is_running(),
                        "exit_code": sess.process.poll(),
                    },
                )

            elif cap == "terminal.send_input":
                sid = args.get("session_id", "")
                text = args.get("text", "")
                sess = self._sessions.get(sid)
                if not sess or not sess.is_running():
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Session not running or not found: {sid}",
                    )

                tier, reason = self.evaluate_command_risk(text, cwd=sess.cwd)
                if tier == CommandRiskTier.HARD_BLOCKED:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Input rejected by security policy: {reason}",
                    )

                if sess.process.stdin:
                    sess.process.stdin.write(text + "\n")
                    sess.process.stdin.flush()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"session_id": sid, "sent": text, "risk_tier": tier.value},
                    events=["input_sent"],
                )

            elif cap == "terminal.kill_session":
                sid = args.get("session_id", "")
                sess = self._sessions.get(sid)
                if not sess:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Session not found: {sid}",
                    )
                sess.kill()
                self._sessions.pop(sid, None)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"session_id": sid, "killed": True},
                    events=["session_killed"],
                )

            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported terminal capability: {capability}",
                )

        except Exception as exc:
            logger.error(f"TerminalManager.{cap} failed: {exc}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Terminal execution error: {exc}",
            )
