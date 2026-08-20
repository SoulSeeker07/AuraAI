"""
Network Manager for Native Windows Layer

Manages network intelligence, diagnostics, and control operations via NetworkAdapter abstraction.
All cross-cutting concerns (permissions, verification, rollback, metrics, context updates) are
handled by the execution engine and pipeline.

This manager ONLY contains pure network operations via NetworkAdapters.
"""

import logging
from typing import Any

from ..adapters.network_adapter import NetworkAdapter, NetworkAdapterFactory
from ..desktop_result import DesktopResult
from ..security.approval_authority import CryptographicApprovalAuthority
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class NetworkManager(BaseNativeManager):
    """
    Manages network operations using NetworkAdapter abstraction.

    Capabilities:
    - Information: network.interfaces, list_network_interfaces, network.default_interface,
      network.public_ip, network.local_ip, network.gateway, network.dns, network.mac,
      network.hostname, network.connection_type, network.wifi_name, network.signal_strength
    - Diagnostics: network.ping, network.traceroute, network.lookup, network.port_check,
      network.internet, network.speed, network.latency, network.packet_loss
    - Control (HMAC-Gated): network.enable_adapter, network.disable_adapter, network.release_ip,
      network.renew_ip, network.flush_dns, network.disconnect_wifi, network.connect_wifi
    """

    NAME = "network"
    VERSION = "1.0"
    PRIORITY = 20
    DEPENDENCIES = ["wmi", "netsh", "psutil"]

    MUTATING_CAPABILITIES = {
        "network.enable_adapter",
        "network.disable_adapter",
        "network.release_ip",
        "network.renew_ip",
        "network.flush_dns",
        "network.disconnect_wifi",
        "network.connect_wifi",
    }

    def __init__(
        self,
        adapter: NetworkAdapter | None = None,
        auth: CryptographicApprovalAuthority | None = None,
    ):
        """Initialize NetworkManager with optional injected adapter and approval authority."""
        super().__init__()
        self._adapter = adapter
        self._auth: CryptographicApprovalAuthority = auth or CryptographicApprovalAuthority.get_instance()

    @property
    def adapter(self) -> NetworkAdapter:
        """Get or initialize active network adapter."""
        if self._adapter is None:
            self._adapter = NetworkAdapterFactory.get_adapter()
        return self._adapter

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by NetworkManager."""
        return [
            # Information
            "list_network_interfaces",
            "network.interfaces",
            "network.interface_list",
            "network.default_interface",
            "network.public_ip",
            "network.local_ip",
            "network.gateway",
            "network.dns",
            "network.dns_query",
            "network.mac",
            "network.hostname",
            "network.connection_type",
            "network.wifi_name",
            "network.signal_strength",
            # Diagnostics
            "network.ping",
            "network.traceroute",
            "network.lookup",
            "network.port_check",
            "network.socket_probe",
            "network.internet",
            "network.speed",
            "network.latency",
            "network.packet_loss",
            # Control
            "network.enable_adapter",
            "network.disable_adapter",
            "network.release_ip",
            "network.renew_ip",
            "network.flush_dns",
            "network.disconnect_wifi",
            "network.connect_wifi",
            "network.route_inspect",
            "network.remediate",
        ]

    def health_check(self) -> HealthCheckResult:
        """
        Perform health check on NetworkManager and active adapter.

        Returns:
            HealthCheckResult with detailed network telemetry status.
        """
        active_adapter = self.adapter
        missing = []
        if active_adapter.name == "dummy":
            missing.append("wmi")
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        try:
            internet_info = active_adapter.check_internet()
            wifi_info = active_adapter.get_wifi_name()
            latency_info = active_adapter.measure_latency("8.8.8.8")
            dns_info = active_adapter.get_dns()
            gw_info = active_adapter.get_gateway()

            details = {
                "active_adapter": active_adapter.name,
                "internet": (
                    "Connected" if internet_info.get("connected") else "Disconnected"
                ),
                "wifi": "Connected" if wifi_info.get("connected") else "Disconnected",
                "gateway": "Reachable" if gw_info.get("gateway") else "Unreachable",
                "dns": "Working" if dns_info.get("dns_servers") else "Failed",
                "latency_ms": latency_info.get("latency_ms", 0),
            }
        except Exception as e:
            details = {"error": str(e)}
            status = HealthStatus.DEGRADED

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=[active_adapter.name],
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details=details,
        )

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute native network operation for the given capability.

        Returns:
            DesktopResult with execution data or failure message.
        """
        arguments = arguments or {}
        arguments.update(kwargs)

        try:
            logger.info(f"NetworkManager executing capability: {capability}")
            cap_clean = capability.lower()

            # Information Handlers
            if cap_clean in ("list_network_interfaces", "network.interfaces", "network.interface_list"):
                return self._handle_get_interfaces(goal=goal, capability=capability)
            elif cap_clean == "network.default_interface":
                return self._handle_get_default_interface(
                    goal=goal, capability=capability
                )
            elif cap_clean == "network.public_ip":
                return self._handle_get_public_ip(goal=goal, capability=capability)
            elif cap_clean == "network.local_ip":
                return self._handle_get_local_ip(goal=goal, capability=capability)
            elif cap_clean == "network.gateway":
                return self._handle_get_gateway(goal=goal, capability=capability)
            elif cap_clean in ("network.dns", "network.dns_query"):
                return self._handle_get_dns(goal=goal, capability=capability)
            elif cap_clean == "network.mac":
                return self._handle_get_mac(goal=goal, capability=capability)
            elif cap_clean == "network.hostname":
                return self._handle_get_hostname(goal=goal, capability=capability)
            elif cap_clean == "network.connection_type":
                return self._handle_get_connection_type(
                    goal=goal, capability=capability
                )
            elif cap_clean == "network.wifi_name":
                return self._handle_get_wifi_name(goal=goal, capability=capability)
            elif cap_clean == "network.signal_strength":
                return self._handle_get_signal_strength(
                    goal=goal, capability=capability
                )

            # Diagnostic Handlers
            elif cap_clean == "network.ping":
                return self._handle_ping(
                    goal=goal, capability=capability, arguments=arguments
                )
            elif cap_clean == "network.traceroute":
                return self._handle_traceroute(
                    goal=goal, capability=capability, arguments=arguments
                )
            elif cap_clean == "network.lookup":
                return self._handle_lookup(
                    goal=goal, capability=capability, arguments=arguments
                )
            elif cap_clean in ("network.port_check", "network.socket_probe"):
                return self._handle_port_check(
                    goal=goal, capability=capability, arguments=arguments
                )
            elif cap_clean == "network.internet":
                return self._handle_check_internet(goal=goal, capability=capability)
            elif cap_clean == "network.speed":
                return self._handle_test_speed(goal=goal, capability=capability)
            elif cap_clean == "network.latency":
                return self._handle_measure_latency(
                    goal=goal, capability=capability, arguments=arguments
                )
            elif cap_clean == "network.packet_loss":
                return self._handle_measure_packet_loss(
                    goal=goal, capability=capability, arguments=arguments
                )
            elif cap_clean in ("network.route_inspect", "route_inspect"):
                import subprocess
                proc = subprocess.run(["route", "print"], capture_output=True, text=True, timeout=10)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"routing_table": proc.stdout, "exit_code": proc.returncode},
                    events=["network_route_inspected"],
                )
            elif cap_clean in ("network.remediate", "remediate"):
                ok = self.adapter.flush_dns()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"remediation_applied": True, "dns_flushed": ok},
                    events=["network_remediated"],
                )

            # Control Handlers (HMAC Human Approval Gate Enforced)
            if cap_clean in self.MUTATING_CAPABILITIES:
                target = str(arguments.get("adapter_name") or arguments.get("ssid") or arguments.get("target") or "host_network_stack").strip()
                action_params = {"capability": cap_clean, "target": target}
                ticket_id = arguments.get("approval_ticket_id")
                signature = arguments.get("approval_signature")

                if not ticket_id or not signature:
                    issued_ticket_id = self._auth.create_ticket(
                        action_type=cap_clean,
                        target=target,
                        parameters=action_params,
                        description=f"Human authorization required to execute {cap_clean} on '{target}'",
                    )
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Network control operation '{cap_clean}' requires cryptographic human approval.",
                        data={
                            "requires_confirmation": True,
                            "approval_ticket_id": issued_ticket_id,
                            "action_type": cap_clean,
                            "target": target,
                            "risk_tier": "confirmation_required",
                        },
                    )

                valid_sig, auth_err = self._auth.verify_and_redeem(
                    ticket_id, signature, action_type=cap_clean, target=target, parameters=action_params
                )
                if not valid_sig:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Human authorization failed: {auth_err}",
                        data={"security_alert": "unauthorized_or_forged_approval"},
                    )

                if cap_clean == "network.enable_adapter":
                    return self._handle_enable_adapter(
                        goal=goal, capability=capability, arguments=arguments
                    )
                elif cap_clean == "network.disable_adapter":
                    return self._handle_disable_adapter(
                        goal=goal, capability=capability, arguments=arguments
                    )
                elif cap_clean == "network.release_ip":
                    return self._handle_release_ip(
                        goal=goal, capability=capability, arguments=arguments
                    )
                elif cap_clean == "network.renew_ip":
                    return self._handle_renew_ip(
                        goal=goal, capability=capability, arguments=arguments
                    )
                elif cap_clean == "network.flush_dns":
                    return self._handle_flush_dns(goal=goal, capability=capability)
                elif cap_clean == "network.disconnect_wifi":
                    return self._handle_disconnect_wifi(goal=goal, capability=capability)
                elif cap_clean == "network.connect_wifi":
                    return self._handle_connect_wifi(
                        goal=goal, capability=capability, arguments=arguments
                    )

            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Capability '{capability}' not supported by NetworkManager",
                )

        except Exception as e:
            logger.error(f"NetworkManager execution failed: {e}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=str(e)
            )

    # ==================== Information Handlers ====================

    def _handle_get_interfaces(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_interfaces()
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={"interfaces": data},
        )

    def _handle_get_default_interface(
        self, goal: str, capability: str
    ) -> DesktopResult:
        data = self.adapter.get_default_interface()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_public_ip(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_public_ip()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_local_ip(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_local_ip()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_gateway(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_gateway()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_dns(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_dns()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_mac(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_mac()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_hostname(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_hostname()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_connection_type(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_connection_type()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_wifi_name(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_wifi_name()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_get_signal_strength(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.get_signal_strength()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    # ==================== Diagnostic Handlers ====================

    def _handle_ping(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        host = arguments.get("host", "8.8.8.8")
        count = int(arguments.get("count", 4))
        timeout = float(arguments.get("timeout", 2.0))
        data = self.adapter.ping(host=host, count=count, timeout_sec=timeout)
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_traceroute(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        host = arguments.get("host", "8.8.8.8")
        max_hops = int(arguments.get("max_hops", 15))
        data = self.adapter.traceroute(host=host, max_hops=max_hops)
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_lookup(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        domain = arguments.get("domain", "google.com")
        data = self.adapter.lookup(domain=domain)
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_port_check(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        host = arguments.get("host", "8.8.8.8")
        port = int(arguments.get("port", 80))
        timeout = float(arguments.get("timeout", 2.0))
        data = self.adapter.port_check(host=host, port=port, timeout_sec=timeout)
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_check_internet(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.check_internet()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_test_speed(self, goal: str, capability: str) -> DesktopResult:
        data = self.adapter.test_speed()
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_measure_latency(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        host = arguments.get("host", "8.8.8.8")
        data = self.adapter.measure_latency(host=host)
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    def _handle_measure_packet_loss(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        host = arguments.get("host", "8.8.8.8")
        count = int(arguments.get("count", 5))
        data = self.adapter.measure_packet_loss(host=host, count=count)
        return DesktopResult.create_success(
            goal=goal, capability=capability, manager=self.name, data=data
        )

    # ==================== Control Handlers ====================

    def _handle_enable_adapter(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        adapter_name = arguments.get("adapter_name", "Wi-Fi")
        ok = self.adapter.enable_adapter(adapter_name)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "enabled",
                    "adapter": adapter_name,
                    "backend": self.adapter.name,
                },
                events=["network_adapter_enabled"],
            )
        return DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.name,
            error=f"Failed to enable network adapter '{adapter_name}'",
        )

    def _handle_disable_adapter(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        adapter_name = arguments.get("adapter_name", "Wi-Fi")
        ok = self.adapter.disable_adapter(adapter_name)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "disabled",
                    "adapter": adapter_name,
                    "backend": self.adapter.name,
                },
                events=["network_adapter_disabled"],
            )
        return DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.name,
            error=f"Failed to disable network adapter '{adapter_name}'",
        )

    def _handle_release_ip(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        adapter_name = arguments.get("adapter_name", "")
        ok = self.adapter.release_ip(adapter_name)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "ip_released",
                    "adapter": adapter_name,
                    "backend": self.adapter.name,
                },
                events=["ip_released"],
            )
        return DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.name,
            error="Failed to release IP lease",
        )

    def _handle_renew_ip(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        adapter_name = arguments.get("adapter_name", "")
        ok = self.adapter.renew_ip(adapter_name)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "ip_renewed",
                    "adapter": adapter_name,
                    "backend": self.adapter.name,
                },
                events=["ip_renewed"],
            )
        return DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.name,
            error="Failed to renew IP lease",
        )

    def _handle_flush_dns(self, goal: str, capability: str) -> DesktopResult:
        ok = self.adapter.flush_dns()
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"status": "dns_flushed", "backend": self.adapter.name},
                events=["dns_flushed"],
            )
        return DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.name,
            error="Failed to flush DNS cache",
        )

    def _handle_disconnect_wifi(self, goal: str, capability: str) -> DesktopResult:
        ok = self.adapter.disconnect_wifi()
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={"status": "wifi_disconnected", "backend": self.adapter.name},
                events=["wifi_disconnected"],
            )
        return DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.name,
            error="Failed to disconnect Wi-Fi",
        )

    def _handle_connect_wifi(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        ssid = arguments.get("ssid", "")
        key = arguments.get("key")
        ok = self.adapter.connect_wifi(ssid, key)
        if ok:
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data={
                    "status": "wifi_connected",
                    "ssid": ssid,
                    "backend": self.adapter.name,
                },
                events=["wifi_connected"],
            )
        return DesktopResult.create_failure(
            goal=goal,
            capability=capability,
            manager=self.name,
            error=f"Failed to connect to Wi-Fi SSID '{ssid}'",
        )
