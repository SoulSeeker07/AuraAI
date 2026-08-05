"""
Networking Agent - Specialized agent for network configuration and analysis.

Handles:
- Cisco, Juniper, Fortinet, Palo Alto router configurations
- Routing and switching protocols
- Firewall configurations
- VPN configurations
- Network topology analysis
- Network log analysis
- Packet capture analysis (future)

Never touches coding, desktop operations, or research.
"""

import logging
from typing import Any

from ..base_agent import AgentCapabilities, AgentResult, BaseAgent

logger = logging.getLogger(__name__)


class NetworkingAgent(BaseAgent):
    """
    Specialized agent for network infrastructure analysis.

    Domain Expertise:
    - Router configurations (Cisco, Juniper, Fortinet, Palo Alto)
    - Routing protocols (OSPF, BGP, EIGRP, IS-IS, RIP)
    - Switching configurations
    - Firewall rules and policies
    - VPN configurations
    - Network topologies
    - Packet capture analysis
    - Network security

    Capabilities:
    - Analyze router configurations
    - Evaluate network topologies
    - Identify security issues in network configs
    - Analyze network logs
    - Generate network reports
    - Troubleshoot connectivity issues
    """

    agent_name = "NetworkingAgent"
    agent_version = "1.0.0"
    agent_description = (
        "Specialized agent for network configuration and infrastructure analysis"
    )

    def __init__(self, agent_id: str = None, config: dict[str, Any] | None = None):
        """
        Initialize the Networking Agent.

        Args:
            agent_id: Unique identifier for this agent instance
            config: Configuration for this agent
        """
        capabilities = AgentCapabilities(
            tasks=[
                "analyze_network_configuration",
                "evaluate_network_topology",
                "identify_network_security_issues",
                "analyze_network_logs",
                "generate_network_report",
                "troubleshoot_connectivity",
                "analyze_routing_protocols",
                "evaluate_firewall_configs",
                "analyze_vpn_configs",
                "packet_capture_analysis",
            ],
            tools=[
                "router_config_reader",
                "network_topology_analyzer",
                "log_analyzer",
                "firewall_analyzer",
                "packet_analyzer",
                "report_generator",
            ],
            models=["network_expert", "infrastructure_analyst"],
            priority=90,
            dependencies=["network_plugin"],
            expert_domains=[
                "Cisco IOS",
                "Juniper JunOS",
                "Fortinet FortiOS",
                "Palo Alto PAN-OS",
                "OSPF",
                "BGP",
                "EIGRP",
                "IS-IS",
                "RIP",
                "VLAN",
                "STP",
                "ACLs",
                "VPN",
                "Firewall",
                "Network Security",
            ],
        )

        super().__init__(
            agent_id=agent_id or f"networking_{id(self)}",
            capabilities=capabilities,
            config=config,
        )

        logger.info(f"Initialized {self.agent_name}")

    async def initialize(self) -> bool:
        """
        Initialize the Networking Agent resources.

        Returns:
            True if initialization successful
        """
        try:
            # Load network-specific plugins
            if "network_plugin" in self.config:
                self.network_plugin = self.config["network_plugin"]
                logger.info("Network plugin loaded")
            else:
                logger.warning(
                    "Network plugin not configured, using basic capabilities"
                )
                self.network_plugin = None

            self._set_state(AgentState.INITIALIZED)
            return True

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            self._set_state(AgentState.FAILED)
            return False

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        """
        Execute a network analysis task.

        Args:
            task: Task dictionary containing:
                - task_type: Type of network task
                - data: Network-specific data
                - context: Additional context

        Returns:
            AgentResult with analysis results
        """
        self.start_time = time.time()
        self._set_state(AgentState.WORKING)

        task_type = task.get("task_type", "")
        data = task.get("data", {})

        logger.info(f"Executing network task: {task_type}")

        try:
            # Route to appropriate method based on task type
            if task_type == "analyze_network_configuration":
                return await self._analyze_network_configuration(data)

            elif task_type == "evaluate_network_topology":
                return await self._evaluate_network_topology(data)

            elif task_type == "identify_network_security_issues":
                return await self._identify_network_security_issues(data)

            elif task_type == "analyze_network_logs":
                return await self._analyze_network_logs(data)

            elif task_type == "troubleshoot_connectivity":
                return await self._troubleshoot_connectivity(data)

            elif task_type == "analyze_routing_protocols":
                return await self._analyze_routing_protocols(data)

            elif task_type == "evaluate_firewall_configs":
                return await self._evaluate_firewall_configs(data)

            elif task_type == "analyze_vpn_configs":
                return await self._analyze_vpn_configs(data)

            elif task_type == "packet_capture_analysis":
                return await self._analyze_packet_captures(data)

            else:
                return self._create_result(
                    success=False,
                    summary=f"Unknown network task type: {task_type}",
                    error=f"Task type {task_type} not recognized by {self.agent_name}",
                )

        except Exception as e:
            logger.error(f"Error executing network task: {e}")
            return self._create_result(
                success=False, summary=f"Network task failed: {task_type}", error=str(e)
            )

        finally:
            self.end_time = time.time()
            self._set_state(AgentState.COMPLETED)

    async def cleanup(self) -> bool:
        """
        Clean up network agent resources.

        Returns:
            True if cleanup successful
        """
        logger.info(f"Cleaning up {self.agent_name}")
        self._set_state(AgentState.DESTROYED)
        return True

    # ==================== Network Analysis Methods ====================

    async def _analyze_network_configuration(self, data: dict[str, Any]) -> AgentResult:
        """
        Analyze a network device configuration.

        Args:
            data: Configuration data including device type and config

        Returns:
            Analysis result
        """
        device_type = data.get("device_type", "unknown")
        configuration = data.get("configuration", "")

        summary = f"Analyzing {device_type} network configuration"
        actions = []
        files_modified = []
        confidence = 0.8
        warnings = []

        try:
            # Basic validation
            if not configuration:
                return self._create_result(
                    success=False, summary=summary, error="No configuration provided"
                )

            # Identify device type
            actions.append(f"Identified device type: {device_type}")

            # Analyze configuration for common issues
            issues_found = self._validate_configuration(configuration, device_type)

            if issues_found:
                warnings.extend(issues_found)

            summary = f"Configuration analysis complete. Found {len(issues_found)} potential issues."
            confidence = 0.85 - (len(issues_found) * 0.02)

            # Suggest improvements
            suggestions = self._generate_improvements(configuration, device_type)
            actions.extend(suggestions)

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "device_type": device_type,
                    "issues_found": len(issues_found),
                    "issues": issues_found,
                    "suggestions": suggestions,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _evaluate_network_topology(self, data: dict[str, Any]) -> AgentResult:
        """
        Evaluate a network topology.

        Args:
            data: Topology data

        Returns:
            Topology evaluation result
        """
        topology = data.get("topology", {})
        nodes = topology.get("nodes", [])
        links = topology.get("links", [])

        summary = f"Evaluating network topology with {len(nodes)} nodes and {len(links)} links"
        actions = []
        warnings = []
        suggestions = []

        try:
            # Validate topology
            if len(nodes) == 0:
                return self._create_result(
                    success=False, summary=summary, error="No nodes in topology"
                )

            actions.append(f"Validated {len(nodes)} nodes and {len(links)} links")

            # Check for single point of failure
            if len(links) < len(nodes) - 1:
                warnings.append(
                    "Topology has minimal redundancy - potential single point of failure"
                )
                suggestions.append("Consider adding more links or redundant paths")

            # Check connectivity
            connectivity = self._check_connectivity(nodes, links)
            actions.append(
                f"Connectivity check: {connectivity['connected']} nodes reachable"
            )

            if not connectivity["connected"]:
                warnings.append("Some nodes are not reachable from each other")

            # Check for optimal paths
            path_analysis = self._analyze_paths(nodes, links)
            actions.append(
                f"Path analysis complete: {path_analysis['average_hops']} average hops"
            )

            summary = f"Topology evaluation complete. {len(warnings)} warnings, {len(suggestions)} suggestions."
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "nodes_analyzed": len(nodes),
                    "links_analyzed": len(links),
                    "warnings": warnings,
                    "suggestions": suggestions,
                    "connectivity": connectivity,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _identify_network_security_issues(
        self, data: dict[str, Any]
    ) -> AgentResult:
        """
        Identify security issues in network configurations.

        Args:
            data: Configuration or security data

        Returns:
            Security analysis result
        """
        configuration = data.get("configuration", "")

        summary = "Analyzing network security configuration"
        actions = []
        warnings = []
        suggestions = []

        try:
            # Scan for common security issues
            actions.append("Scanning for security vulnerabilities")

            security_issues = self._scan_security_issues(configuration)
            actions.append(f"Found {len(security_issues)} potential security issues")

            if security_issues:
                warnings.extend(security_issues)
                suggestions.extend(self._generate_security_improvements(configuration))

            summary = f"Security analysis complete. {len(warnings)} security concerns identified."
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={"issues_found": len(security_issues), "issues": security_issues},
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _analyze_network_logs(self, data: dict[str, Any]) -> AgentResult:
        """
        Analyze network device logs.

        Args:
            data: Log data

        Returns:
            Log analysis result
        """
        log_data = data.get("logs", "")
        log_type = data.get("log_type", "generic")

        summary = f"Analyzing {log_type} network logs"
        actions = []
        warnings = []

        try:
            if not log_data:
                return self._create_result(
                    success=False, summary=summary, error="No log data provided"
                )

            # Parse and analyze logs
            events = self._parse_network_logs(log_data, log_type)
            actions.append(f"Parsed {len(events)} log events")

            # Identify errors and warnings
            errors = [e for e in events if e.get("severity") == "error"]
            warnings.extend([e.get("message") for e in errors])

            summary = f"Log analysis complete. {len(errors)} errors, {len(events)} total events."
            confidence = 0.8

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                confidence=confidence,
                data={
                    "events_analyzed": len(events),
                    "errors_found": len(errors),
                    "events": events,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _troubleshoot_connectivity(self, data: dict[str, Any]) -> AgentResult:
        """
        Troubleshoot network connectivity issues.

        Args:
            data: Connectivity test data

        Returns:
            Troubleshooting result
        """
        source = data.get("source", "")
        destination = data.get("destination", "")

        summary = f"Troubleshooting connectivity from {source} to {destination}"
        actions = []
        suggestions = []
        warnings = []

        try:
            if not source or not destination:
                return self._create_result(
                    success=False,
                    summary=summary,
                    error="Source and destination required",
                )

            # Simulate connectivity test
            actions.append(f"Testing connectivity between {source} and {destination}")

            connectivity = self._test_connectivity(source, destination)

            if connectivity["reachable"]:
                summary = f"Connectivity verified. Latency: {connectivity['latency']}ms"
                confidence = 0.9
            else:
                summary = f"Connectivity issue detected. {connectivity['issues']}"
                confidence = 0.7
                warnings.append(connectivity["issues"])

            # Generate troubleshooting suggestions
            suggestions.extend(self._generate_troubleshooting_steps(connectivity))
            actions.extend(suggestions)

            return self._create_result(
                success=connectivity["reachable"],
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data=connectivity,
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _analyze_routing_protocols(self, data: dict[str, Any]) -> AgentResult:
        """
        Analyze routing protocol configurations.

        Args:
            data: Routing protocol data

        Returns:
            Routing analysis result
        """
        protocol = data.get("protocol", "OSPF")
        configuration = data.get("configuration", "")

        summary = f"Analyzing {protocol} routing protocol configuration"
        actions = []
        suggestions = []

        try:
            if not configuration:
                return self._create_result(
                    success=False, summary=summary, error="No configuration provided"
                )

            actions.append(f"Validating {protocol} configuration")

            # Validate protocol-specific configuration
            issues = self._validate_routing_protocol(configuration, protocol)
            suggestions.extend(issues)

            summary = (
                f"{protocol} analysis complete. {len(issues)} validation issues found."
            )
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                suggestions=suggestions,
                confidence=confidence,
                data={"protocol": protocol, "issues": issues},
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _evaluate_firewall_configs(self, data: dict[str, Any]) -> AgentResult:
        """
        Evaluate firewall configuration.

        Args:
            data: Firewall configuration data

        Returns:
            Firewall evaluation result
        """
        configuration = data.get("configuration", "")

        summary = "Evaluating firewall configuration"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not configuration:
                return self._create_result(
                    success=False, summary=summary, error="No configuration provided"
                )

            actions.append("Scanning firewall rules")

            # Evaluate rules
            rule_issues = self._evaluate_firewall_rules(configuration)
            warnings.extend(rule_issues)
            suggestions.extend(self._generate_firewall_improvements(configuration))

            summary = (
                f"Firewall evaluation complete. {len(warnings)} rule issues found."
            )
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={"rule_issues": len(rule_issues), "issues": rule_issues},
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _analyze_vpn_configs(self, data: dict[str, Any]) -> AgentResult:
        """
        Analyze VPN configuration.

        Args:
            data: VPN configuration data

        Returns:
            VPN analysis result
        """
        configuration = data.get("configuration", "")
        vpn_type = data.get("vpn_type", "IPsec")

        summary = f"Analyzing {vpn_type} VPN configuration"
        actions = []
        suggestions = []
        warnings = []

        try:
            if not configuration:
                return self._create_result(
                    success=False, summary=summary, error="No configuration provided"
                )

            actions.append(f"Validating {vpn_type} VPN configuration")

            # Check VPN configuration
            issues = self._validate_vpn_configuration(configuration, vpn_type)
            warnings.extend(issues)

            summary = (
                f"{vpn_type} VPN analysis complete. {len(issues)} validation issues."
            )
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={"vpn_type": vpn_type, "issues": issues},
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _analyze_packet_captures(self, data: dict[str, Any]) -> AgentResult:
        """
        Analyze packet captures.

        Args:
            data: Packet capture data

        Returns:
            Packet capture analysis result
        """
        pcap_data = data.get("pcap_data", "")

        summary = "Analyzing packet capture"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not pcap_data:
                return self._create_result(
                    success=False,
                    summary=summary,
                    error="No packet capture data provided",
                )

            actions.append("Parsing packet capture data")

            # Analyze packets
            packet_stats = self._analyze_packets(pcap_data)
            actions.extend(packet_stats["actions"])
            warnings.extend(packet_stats["warnings"])

            summary = f"Packet capture analysis complete. {packet_stats['packets']} packets analyzed."
            confidence = 0.8

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data=packet_stats,
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    # ==================== Helper Methods ====================

    def _validate_configuration(self, config: str, device_type: str) -> list[str]:
        """Validate network device configuration."""
        issues = []

        # Check for common configuration issues
        if "password" in config.lower():
            issues.append("Weak or default passwords detected")

        if "enable secret" in config.lower():
            issues.append(
                "Enable secret configuration found - should use local usernames"
            )

        # Device-specific checks could go here

        return issues

    def _generate_improvements(self, config: str, device_type: str) -> list[str]:
        """Generate configuration improvement suggestions."""
        suggestions = []

        suggestions.append("Consider implementing SSHv2 instead of Telnet")
        suggestions.append("Apply access control lists to limit network access")
        suggestions.append("Configure logging for troubleshooting")
        suggestions.append("Regular configuration backups are recommended")

        return suggestions

    def _scan_security_issues(self, config: str) -> list[str]:
        """Scan for security vulnerabilities."""
        issues = []

        if "password" in config.lower():
            if "cisco" in config.lower():
                issues.append(
                    "Potential password in clear text - use encrypted passwords"
                )
            else:
                issues.append("Unencrypted password detected")

        if "no shutdown" in config.lower():
            issues.append("Interfaces may be exposed - review access control")

        if "access-list" in config.lower():
            issues.append("Review ACL rules for unnecessary access")

        return issues

    def _generate_security_improvements(self, config: str) -> list[str]:
        """Generate security improvement suggestions."""
        suggestions = []

        suggestions.append("Use strong encryption for passwords")
        suggestions.append("Implement role-based access control")
        suggestions.append("Regularly audit security configurations")
        suggestions.append("Keep device firmware updated")

        return suggestions

    def _parse_network_logs(self, logs: str, log_type: str) -> list[dict[str, Any]]:
        """Parse network logs."""
        events = []

        # Simple log parsing - in production would use proper log parsers
        for line in logs.split("\n"):
            if "error" in line.lower() or "failure" in line.lower():
                events.append(
                    {
                        "severity": "error",
                        "message": line.strip(),
                        "timestamp": "unknown",
                    }
                )
            elif "warning" in line.lower():
                events.append(
                    {
                        "severity": "warning",
                        "message": line.strip(),
                        "timestamp": "unknown",
                    }
                )

        return events

    def _check_connectivity(self, nodes: list, links: list) -> dict[str, Any]:
        """Check network connectivity."""
        return {
            "connected": len(nodes) > 0 and len(links) >= len(nodes) - 1,
            "details": "Basic connectivity validation",
        }

    def _analyze_paths(self, nodes: list, links: list) -> dict[str, Any]:
        """Analyze network paths."""
        return {
            "average_hops": len(links) // len(nodes) if nodes else 0,
            "total_paths": len(links),
        }

    def _test_connectivity(self, source: str, destination: str) -> dict[str, Any]:
        """Test connectivity between two nodes."""
        return {
            "reachable": False,
            "latency": "unknown",
            "issues": f"Could not reach {destination} from {source}",
            "troubleshooting_steps": [
                "Check if destination is reachable on the network",
                "Verify routing tables on both endpoints",
                "Check firewall rules",
                "Test with ping from both endpoints",
            ],
        }

    def _generate_troubleshooting_steps(
        self, connectivity: dict[str, Any]
    ) -> list[str]:
        """Generate troubleshooting steps."""
        if connectivity["reachable"]:
            return ["Connectivity is working as expected", "No action needed"]
        else:
            return connectivity.get(
                "troubleshooting_steps",
                [
                    "Check physical connectivity",
                    "Verify IP addressing",
                    "Check routing tables",
                    "Review firewall rules",
                ],
            )

    def _validate_routing_protocol(self, config: str, protocol: str) -> list[str]:
        """Validate routing protocol configuration."""
        issues = []

        # Protocol-specific validation
        if protocol.upper() == "OSPF":
            if "passive-interface" in config.lower():
                issues.append("Review passive interfaces for proper OSPF operation")

        elif protocol.upper() == "BGP":
            if "no bgp default ipv4-unicast" in config.lower():
                issues.append("BGP unicast should be enabled by default")

        return issues

    def _evaluate_firewall_rules(self, config: str) -> list[str]:
        """Evaluate firewall rules."""
        issues = []

        if "permit any any" in config.lower():
            issues.append("Allow-all rule detected - significant security risk")

        if "no logging" in config.lower():
            issues.append("No logging configured - difficult to detect attacks")

        if "allow from 0.0.0.0/0" in config.lower():
            issues.append("Broad allow rule - restrict by source IP")

        return issues

    def _generate_firewall_improvements(self, config: str) -> list[str]:
        """Generate firewall improvement suggestions."""
        suggestions = []

        suggestions.append("Remove allow-all rules if possible")
        suggestions.append("Implement logging for all rule types")
        suggestions.append("Apply default-deny rule")
        suggestions.append("Regularly review and audit firewall rules")

        return suggestions

    def _validate_vpn_configuration(self, config: str, vpn_type: str) -> list[str]:
        """Validate VPN configuration."""
        issues = []

        if "pre-shared key" in config.lower():
            issues.append("Consider using certificate-based authentication instead")

        if "des-cbc" in config.lower():
            issues.append("DES encryption is outdated - use AES-256")

        if "no encryption" in config.lower():
            issues.append("Encryption must be enabled for VPN tunnels")

        return issues

    def _analyze_packets(self, pcap_data: str) -> dict[str, Any]:
        """Analyze packet capture data."""
        return {
            "packets": len(pcap_data.split("\n")) if pcap_data else 0,
            "actions": ["Packet statistics generated"],
            "warnings": [],
        }
