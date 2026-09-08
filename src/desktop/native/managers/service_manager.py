"""
Service Manager — Windows Service Enumeration and Control
Location: src/desktop/native/managers/service_manager.py

Provides Windows service inspection and lifecycle management (listing, status query,
starting, stopping, restarting) using psutil and Windows Service Controller (sc.exe).
Enforces process-wide HMAC-SHA256 human authorization gates on all mutating operations.
"""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

from ..desktop_result import DesktopResult
from ..security.approval_authority import CryptographicApprovalAuthority
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)


class ServiceManager(BaseNativeManager):
    """
    Manages Windows service enumeration and lifecycle operations.

    Capabilities:
    - service.list: Enumerate all Windows services (name, display_name, status, start_type, pid)
    - service.status: Query detailed status of a specific Windows service
    - service.start: Start a Windows service (HMAC-Gated)
    - service.stop: Stop a Windows service (HMAC-Gated)
    - service.restart: Restart a Windows service (HMAC-Gated)
    """

    NAME = "service"
    VERSION = "1.0"
    PRIORITY = 35
    DEPENDENCIES: list[str] = ["psutil"]

    MUTATING_CAPABILITIES = {
        "service.start",
        "service.stop",
        "service.restart",
    }

    def __init__(
        self,
        auth: CryptographicApprovalAuthority | None = None,
    ):
        """Initialize ServiceManager with optional injected approval authority."""
        super().__init__()
        self._auth: CryptographicApprovalAuthority = (
            auth or CryptographicApprovalAuthority.get_instance()
        )
        self._initialized = False

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        """Get cryptographic approval authority."""
        return self._auth

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by ServiceManager."""
        return [
            "service.list",
            "service.status",
            "service.start",
            "service.stop",
            "service.restart",
        ]

    def initialize(self) -> bool:
        """Initialize the ServiceManager."""
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        """Perform health check on ServiceManager and dependencies."""
        missing: list[str] = []
        if not HAS_PSUTIL or psutil is None:
            missing.append("psutil")
            status = HealthStatus.UNAVAILABLE
        else:
            status = HealthStatus.HEALTHY

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=[],
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities) if status == HealthStatus.HEALTHY else 0,
            details={
                "initialized": self._initialized,
                "psutil_available": HAS_PSUTIL,
                "security_model": "cryptographic_hmac_human_approval_gate",
                "mutating_capabilities": list(self.MUTATING_CAPABILITIES),
            },
        )

    def shutdown(self) -> None:
        """Shutdown the ServiceManager and clean up resources."""
        self._initialized = False

    def _validate_service_name(self, name: str) -> tuple[bool, str]:
        """
        Validate service name against command injection, path traversal, or formatting errors.

        Args:
            name: Candidate service name.

        Returns:
            Tuple of (is_valid, sanitized_name_or_error_message).
        """
        clean = name.strip()
        if not clean:
            return False, "Service name cannot be empty."
        if len(clean) > 256:
            return False, f"Service name exceeds maximum length of 256 characters: '{clean[:32]}...'"
        if any(ch in clean for ch in ("\x00", "\n", "\r", '"', ";", "&", "|", "<", ">")):
            return False, f"Service name contains invalid or forbidden characters: '{clean}'"
        if "/" in clean or "\\" in clean:
            return False, f"Service name cannot contain path separators ('/' or '\\'): '{clean}'"
        return True, clean

    def _audit_execution(
        self,
        action_type: str,
        target: str,
        exit_code: int,
        cmd: list[str],
        ticket_id: str | None = None,
    ) -> None:
        """Log service control operations to process-wide SecurityAuditLogger."""
        try:
            from ..security.audit_logger import SecurityAuditLogger

            SecurityAuditLogger.get_instance().log_event(
                event_type="SERVICE_CONTROL_EXECUTED",
                action_type=action_type,
                target=target,
                status="SUCCESS" if exit_code == 0 else "FAILURE",
                details={"exit_code": exit_code, "cmd": cmd},
                ticket_id=ticket_id,
            )
        except Exception as audit_err:
            logger.warning(f"Audit log failed on service control execution: {audit_err}")

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        """
        Execute native Windows service operation for the given capability.

        Args:
            capability: Capability string to execute.
            goal: Original user goal or task description.
            arguments: Dictionary of arguments for the capability.
            **kwargs: Extra arguments.

        Returns:
            DesktopResult with execution data or failure message.
        """
        args = dict(arguments or {})
        if kwargs:
            args.update(kwargs)
        cap = capability.lower().strip()

        try:
            logger.info(f"ServiceManager executing capability: '{cap}'")

            # 1. Read-only: List all Windows services
            if cap == "service.list":
                return self._handle_list(goal=goal, capability=capability, arguments=args)

            # 2. Read-only: Get status of a specific service
            elif cap == "service.status":
                return self._handle_status(goal=goal, capability=capability, arguments=args)

            # 3. Mutating operations: HMAC Human Approval Gate Enforced
            elif cap in self.MUTATING_CAPABILITIES:
                raw_name = (
                    args.get("name")
                    or args.get("service")
                    or args.get("service_name")
                    or goal
                )
                valid, sanitized_name = self._validate_service_name(str(raw_name))
                if not valid:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=sanitized_name,
                    )

                target = sanitized_name
                action_params = {"capability": cap, "name": sanitized_name}
                ticket_id = args.get("approval_ticket_id")
                signature = args.get("approval_signature")

                if not ticket_id or not signature:
                    issued_ticket_id = self._auth.create_ticket(
                        action_type=cap,
                        target=target,
                        parameters=action_params,
                        description=f"Human authorization required to execute {cap} on service '{target}'",
                    )
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Service control operation '{cap}' requires cryptographic human approval.",
                        data={
                            "requires_confirmation": True,
                            "approval_ticket_id": issued_ticket_id,
                            "action_type": cap,
                            "target": target,
                            "risk_tier": "confirmation_required",
                        },
                    )

                valid_sig, auth_err = self._auth.verify_and_redeem(
                    ticket_id,
                    signature,
                    action_type=cap,
                    target=target,
                    parameters=action_params,
                )
                if not valid_sig:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Human authorization failed: {auth_err}",
                        data={"security_alert": "unauthorized_or_forged_approval"},
                    )

                if cap == "service.start":
                    return self._handle_start(
                        goal=goal,
                        capability=capability,
                        service_name=sanitized_name,
                        ticket_id=ticket_id,
                    )
                elif cap == "service.stop":
                    return self._handle_stop(
                        goal=goal,
                        capability=capability,
                        service_name=sanitized_name,
                        ticket_id=ticket_id,
                    )
                elif cap == "service.restart":
                    return self._handle_restart(
                        goal=goal,
                        capability=capability,
                        service_name=sanitized_name,
                        ticket_id=ticket_id,
                    )

            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Unsupported capability: {capability}",
            )

        except Exception as exc:
            logger.error(f"ServiceManager.{cap} failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Operation failed: {exc}",
            )

    def _handle_list(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        List all Windows services using psutil.win_service_iter().

        Handles psutil.AccessDenied and psutil.NoSuchProcess gracefully per-service.
        """
        if not HAS_PSUTIL or psutil is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="psutil dependency is not installed or available.",
            )

        services: list[dict[str, Any]] = []
        status_filter = str(arguments.get("status") or "").strip().lower()
        search_filter = str(
            arguments.get("filter") or arguments.get("search") or ""
        ).strip().lower()

        try:
            for s in psutil.win_service_iter():
                try:
                    name = s.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

                try:
                    display_name = s.display_name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    display_name = name

                try:
                    status = s.status()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    status = "access_denied"

                try:
                    start_type = s.start_type()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    start_type = "access_denied"

                try:
                    pid = s.pid()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pid = None

                if status_filter and status.lower() != status_filter:
                    continue
                if search_filter and (
                    search_filter not in name.lower()
                    and search_filter not in display_name.lower()
                ):
                    continue

                services.append({
                    "name": name,
                    "display_name": display_name,
                    "status": status,
                    "start_type": start_type,
                    "pid": pid,
                })
        except Exception as exc:
            logger.error(f"Failed iterating Windows services: {exc}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to list Windows services: {exc}",
            )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={"services": services, "count": len(services)},
            events=["services_listed"],
        )

    def _handle_status(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """
        Get detailed status of a specific Windows service using psutil.win_service_get().
        """
        if not HAS_PSUTIL or psutil is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="psutil dependency is not installed or available.",
            )

        raw_name = (
            arguments.get("name")
            or arguments.get("service")
            or arguments.get("service_name")
            or goal
        )
        valid, sanitized = self._validate_service_name(str(raw_name))
        if not valid:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=sanitized,
            )

        try:
            svc = psutil.win_service_get(sanitized)
            svc_dict = svc.as_dict()
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data=svc_dict,
                events=["service_status_queried"],
            )
        except psutil.NoSuchProcess:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Service '{sanitized}' does not exist as an installed service.",
                data={"service_name": sanitized, "exists": False},
            )
        except psutil.AccessDenied:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Access denied querying service '{sanitized}'. Administrative privileges may be required.",
                data={"service_name": sanitized, "access_denied": True},
            )
        except Exception as exc:
            logger.error(f"Failed getting status for service '{sanitized}': {exc}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to get status for service '{sanitized}': {exc}",
                data={"service_name": sanitized},
            )

    def _handle_start(
        self,
        goal: str,
        capability: str,
        service_name: str,
        ticket_id: str | None = None,
    ) -> DesktopResult:
        """
        Start a Windows service using 'sc.exe start <service_name>'.
        """
        cmd = ["sc.exe", "start", service_name]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30.0,
            )
        except subprocess.TimeoutExpired:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Timed out starting service '{service_name}'.",
                data={"service_name": service_name, "timeout": 30.0},
            )
        except OSError as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to execute sc.exe: {exc}",
                data={"service_name": service_name},
            )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        output = stdout or stderr

        self._audit_execution(
            action_type="service.start",
            target=service_name,
            exit_code=proc.returncode,
            cmd=cmd,
            ticket_id=ticket_id,
        )

        if proc.returncode != 0:
            logger.warning(
                f"sc.exe start '{service_name}' failed with exit code {proc.returncode}: {output}"
            )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to start service '{service_name}': {output}",
                data={
                    "service_name": service_name,
                    "exit_code": proc.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                },
            )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "service_name": service_name,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "message": f"Service '{service_name}' started successfully.",
            },
            events=["service_started"],
        )

    def _handle_stop(
        self,
        goal: str,
        capability: str,
        service_name: str,
        ticket_id: str | None = None,
    ) -> DesktopResult:
        """
        Stop a Windows service using 'sc.exe stop <service_name>'.
        """
        cmd = ["sc.exe", "stop", service_name]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30.0,
            )
        except subprocess.TimeoutExpired:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Timed out stopping service '{service_name}'.",
                data={"service_name": service_name, "timeout": 30.0},
            )
        except OSError as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to execute sc.exe: {exc}",
                data={"service_name": service_name},
            )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        output = stdout or stderr

        self._audit_execution(
            action_type="service.stop",
            target=service_name,
            exit_code=proc.returncode,
            cmd=cmd,
            ticket_id=ticket_id,
        )

        if proc.returncode != 0:
            logger.warning(
                f"sc.exe stop '{service_name}' failed with exit code {proc.returncode}: {output}"
            )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to stop service '{service_name}': {output}",
                data={
                    "service_name": service_name,
                    "exit_code": proc.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                },
            )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "service_name": service_name,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "message": f"Service '{service_name}' stopped successfully.",
            },
            events=["service_stopped"],
        )

    def _handle_restart(
        self,
        goal: str,
        capability: str,
        service_name: str,
        ticket_id: str | None = None,
    ) -> DesktopResult:
        """
        Restart a Windows service (stop, wait briefly, then start).
        """
        stop_cmd = ["sc.exe", "stop", service_name]
        try:
            stop_proc = subprocess.run(
                stop_cmd,
                capture_output=True,
                text=True,
                timeout=30.0,
            )
        except subprocess.TimeoutExpired:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Timed out stopping service '{service_name}' during restart.",
                data={"service_name": service_name, "timeout": 30.0},
            )
        except OSError as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to execute sc.exe stop: {exc}",
                data={"service_name": service_name},
            )

        stop_stdout = stop_proc.stdout.strip()
        stop_stderr = stop_proc.stderr.strip()
        stop_output = stop_stdout or stop_stderr

        # Brief pause between stop and start
        time.sleep(1.5)

        start_cmd = ["sc.exe", "start", service_name]
        try:
            start_proc = subprocess.run(
                start_cmd,
                capture_output=True,
                text=True,
                timeout=30.0,
            )
        except subprocess.TimeoutExpired:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Timed out starting service '{service_name}' during restart.",
                data={
                    "service_name": service_name,
                    "stop_exit_code": stop_proc.returncode,
                    "stop_output": stop_output,
                    "timeout": 30.0,
                },
            )
        except OSError as exc:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to execute sc.exe start: {exc}",
                data={
                    "service_name": service_name,
                    "stop_exit_code": stop_proc.returncode,
                    "stop_output": stop_output,
                },
            )

        start_stdout = start_proc.stdout.strip()
        start_stderr = start_proc.stderr.strip()
        start_output = start_stdout or start_stderr

        self._audit_execution(
            action_type="service.restart",
            target=service_name,
            exit_code=start_proc.returncode,
            cmd=["sc.exe", "stop/start", service_name],
            ticket_id=ticket_id,
        )

        if start_proc.returncode != 0:
            logger.warning(
                f"sc.exe start '{service_name}' failed during restart with exit code {start_proc.returncode}: {start_output}"
            )
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Failed to restart service '{service_name}': start command failed: {start_output}",
                data={
                    "service_name": service_name,
                    "stop_exit_code": stop_proc.returncode,
                    "stop_output": stop_output,
                    "start_exit_code": start_proc.returncode,
                    "start_output": start_output,
                },
            )

        warnings: list[str] = []
        if stop_proc.returncode != 0:
            warnings.append(
                f"Stop command returned code {stop_proc.returncode}: {stop_output}"
            )

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "service_name": service_name,
                "stop_exit_code": stop_proc.returncode,
                "stop_output": stop_stdout,
                "start_exit_code": start_proc.returncode,
                "start_output": start_stdout,
                "message": f"Service '{service_name}' restarted successfully.",
            },
            warnings=warnings if warnings else None,
            events=["service_stopped", "service_started", "service_restarted"],
        )
