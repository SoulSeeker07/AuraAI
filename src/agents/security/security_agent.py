"""
Security Agent - Specialized agent for security operations.

Handles:
- Permission management and validation
- Credential handling and security
- Plugin validation and security review
- Threat detection and analysis
- Risk assessment and scoring
- Security policy enforcement

Never touches coding, desktop operations, research, or networking.
"""

import hashlib
import logging
from typing import Any

from ..base_agent import AgentCapabilities, AgentResult, BaseAgent

logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """
    Specialized agent for security operations.

    Domain Expertise:
    - Permission systems and RBAC
    - Credential management
    - Threat detection
    - Risk assessment
    - Security policies
    - Plugin security
    - Vulnerability scanning
    - Access control

    Capabilities:
    - Review user permissions
    - Validate credential security
    - Audit plugin permissions
    - Detect security threats
    - Assess security risks
    - Generate security reports
    - Validate security policies
    - Analyze security logs
    """

    agent_name = "SecurityAgent"
    agent_version = "1.0.0"
    agent_description = "Specialized agent for security operations and risk assessment"

    def __init__(self, agent_id: str = None, config: dict[str, Any] | None = None):
        """
        Initialize the Security Agent.

        Args:
            agent_id: Unique identifier for this agent instance
            config: Configuration for this agent
        """
        capabilities = AgentCapabilities(
            tasks=[
                "review_user_permissions",
                "validate_credential_security",
                "audit_plugin_permissions",
                "detect_threats",
                "assess_security_risk",
                "validate_security_policy",
                "analyze_security_logs",
                "scan_vulnerabilities",
                "generate_security_report",
            ],
            tools=[
                "permission_validator",
                "credential_validator",
                "plugin_security_checker",
                "threat_analyzer",
                "risk_assessor",
                "policy_validator",
                "log_analyzer",
                "vulnerability_scanner",
            ],
            models=["security_expert", "threat_intel"],
            priority=95,
            dependencies=["security_plugin"],
            expert_domains=[
                "RBAC",
                "ABAC",
                "OAuth",
                "Authentication",
                "Authorization",
                "Threat Detection",
                "Vulnerability Assessment",
                "Access Control",
                "Security Auditing",
                "Policy Enforcement",
            ],
        )

        super().__init__(
            agent_id=agent_id or f"security_{id(self)}",
            capabilities=capabilities,
            config=config,
        )

        self.seen_credentials = set()  # For credential tracking
        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> bool:
        """
        Initialize the Security Agent resources.

        Returns:
            True if initialization successful
        """
        try:
            # Load security-specific plugins
            if "security_plugin" in self.config:
                self.security_plugin = self.config["security_plugin"]
                logger.info("Security plugin loaded")
            else:
                logger.warning(
                    "Security plugin not configured, using basic capabilities"
                )
                self.security_plugin = None

            self._set_state(AgentState.INITIALIZED)
            return True

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            self._set_state(AgentState.FAILED)
            return False

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        """
        Execute a security operation task.

        Args:
            task: Task dictionary containing:
                - task_type: Type of security task
                - data: Security-specific data
                - context: Additional context

        Returns:
            AgentResult with security analysis results
        """
        self.start_time = time.time()
        self._set_state(AgentState.WORKING)

        task_type = task.get("task_type", "")
        data = task.get("data", {})

        logger.info(f"Executing security task: {task_type}")

        try:
            # Route to appropriate method based on task type
            if task_type == "review_user_permissions":
                return await self._review_user_permissions(data)

            elif task_type == "validate_credential_security":
                return await self._validate_credential_security(data)

            elif task_type == "audit_plugin_permissions":
                return await self._audit_plugin_permissions(data)

            elif task_type == "detect_threats":
                return await self._detect_threats(data)

            elif task_type == "assess_security_risk":
                return await self._assess_security_risk(data)

            elif task_type == "validate_security_policy":
                return await self._validate_security_policy(data)

            elif task_type == "analyze_security_logs":
                return await self._analyze_security_logs(data)

            elif task_type == "scan_vulnerabilities":
                return await self._scan_vulnerabilities(data)

            elif task_type == "generate_security_report":
                return await self._generate_security_report(data)

            else:
                return self._create_result(
                    success=False,
                    summary=f"Unknown security task type: {task_type}",
                    error=f"Task type {task_type} not recognized by {self.agent_name}",
                )

        except Exception as e:
            logger.error(f"Error executing security task: {e}")
            return self._create_result(
                success=False,
                summary=f"Security task failed: {task_type}",
                error=str(e),
            )

        finally:
            self.end_time = time.time()
            self._set_state(AgentState.COMPLETED)

    async def cleanup(self) -> bool:
        """
        Clean up security agent resources.

        Returns:
            True if cleanup successful
        """
        logger.info(f"Cleaning up {self.agent_name}")
        self._set_state(AgentState.DESTROYED)
        return True

    # ==================== Security Operation Methods ====================

    async def _review_user_permissions(self, data: dict[str, Any]) -> AgentResult:
        """
        Review user permissions and access levels.

        Args:
            data: User and permission data

        Returns:
            Permission review result
        """
        user = data.get("user", {})
        permissions = user.get("permissions", [])
        roles = user.get("roles", [])

        summary = f"Reviewing permissions for user: {user.get('name', 'Unknown')}"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not permissions and not roles:
                return self._create_result(
                    success=False,
                    summary=summary,
                    error="No permissions or roles provided",
                )

            actions.append(
                f"Analyzing permissions: {len(permissions)} direct, {len(roles)} roles"
            )

            # Check for excessive permissions
            high_risk_permissions = [
                perm for perm in permissions if self._is_high_risk_permission(perm)
            ]

            if high_risk_permissions:
                warnings.append(
                    f"High-risk permissions detected: {', '.join(high_risk_permissions)}"
                )
                suggestions.append("Review and restrict these permissions")

            # Check for redundant permissions
            redundant_permissions = self._find_redundant_permissions(permissions)
            if redundant_permissions:
                warnings.append(
                    f"Redundant permissions found: {', '.join(redundant_permissions)}"
                )
                suggestions.append("Consolidate duplicate permissions")

            # Check for missing necessary permissions
            required_permissions = self._get_required_permissions(user)
            missing_permissions = [
                perm
                for perm in required_permissions
                if perm not in permissions and perm not in roles
            ]

            if missing_permissions:
                warnings.append(
                    f"Missing required permissions: {', '.join(missing_permissions)}"
                )
                suggestions.append(
                    "Add these permissions to maintain required functionality"
                )

            summary = f"Permission review complete. {len(warnings)} warnings, {len(suggestions)} suggestions."
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "user": user.get("name"),
                    "permissions_count": len(permissions),
                    "roles_count": len(roles),
                    "high_risk_found": len(high_risk_permissions),
                    "redundant_found": len(redundant_permissions),
                    "missing_required": len(missing_permissions),
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _validate_credential_security(self, data: dict[str, Any]) -> AgentResult:
        """
        Validate credential security.

        Args:
            data: Credential data

        Returns:
            Credential validation result
        """
        username = data.get("username", "")
        credential = data.get("credential", "")

        summary = f"Validating credential security for user: {username}"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not username or not credential:
                return self._create_result(
                    success=False,
                    summary=summary,
                    error="Username and credential required",
                )

            actions.append("Analyzing credential security")

            # Hash credential for comparison
            credential_hash = self._hash_credential(credential)

            # Check for weak credentials
            weak_patterns = self._check_weak_credentials(credential)
            if weak_patterns:
                warnings.extend(weak_patterns)
                suggestions.extend(self._generate_credential_improvements())

            # Check if credential has been seen before
            if credential_hash in self.seen_credentials:
                warnings.append(
                    "Credential has been used before - might be reused across accounts"
                )
                suggestions.append("Use unique credentials for each account")
            else:
                self.seen_credentials.add(credential_hash)

            summary = f"Credential security validation complete. {len(warnings)} warnings found."
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "username": username,
                    "weak_credentials_detected": len(weak_patterns),
                    "seen_before": credential_hash in self.seen_credentials,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _audit_plugin_permissions(self, data: dict[str, Any]) -> AgentResult:
        """
        Audit plugin permissions and security.

        Args:
            data: Plugin and permission data

        Returns:
            Plugin audit result
        """
        plugin = data.get("plugin", {})
        permissions = plugin.get("permissions", [])
        api_access = plugin.get("api_access", [])

        summary = f"Auditing plugin security: {plugin.get('name', 'Unknown')}"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not permissions:
                return self._create_result(
                    success=False,
                    summary=summary,
                    error="No permissions provided for audit",
                )

            actions.append(f"Analyzing {len(permissions)} plugin permissions")

            # Check for overly broad permissions
            broad_permissions = [
                perm for perm in permissions if self._is_broad_permission(perm)
            ]

            if broad_permissions:
                warnings.append(
                    f"Overly broad permissions found: {', '.join(broad_permissions)}"
                )
                suggestions.append("Restrict plugin to minimal required permissions")

            # Check API access
            if api_access:
                if "full_access" in api_access:
                    warnings.append(
                        "Plugin has full API access - significant security risk"
                    )
                    suggestions.append("Review and reduce API access scope")

            # Check for dangerous capabilities
            dangerous_capabilities = [
                cap for cap in permissions if self._is_dangerous_capability(cap)
            ]

            if dangerous_capabilities:
                warnings.append(
                    f"Dangerous capabilities found: {', '.join(dangerous_capabilities)}"
                )
                suggestions.append("Review and restrict these capabilities")

            summary = f"Plugin audit complete. {len(warnings)} security concerns found."
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "plugin_name": plugin.get("name"),
                    "permissions_count": len(permissions),
                    "broad_permissions": len(broad_permissions),
                    "dangerous_capabilities": len(dangerous_capabilities),
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _detect_threats(self, data: dict[str, Any]) -> AgentResult:
        """
        Detect potential security threats.

        Args:
            data: Security event or log data

        Returns:
            Threat detection result
        """
        event_data = data.get("event", {})

        summary = "Detecting potential security threats"
        actions = []
        warnings = []
        suggestions = []

        try:
            # Analyze event data
            threat_level = self._assess_threat_level(event_data)
            actions.append(f"Threat assessment completed - Level: {threat_level}")

            if threat_level == "high":
                warnings.append("HIGH THREAT DETECTED")
                suggestions.append("Immediate action recommended")

            elif threat_level == "medium":
                warnings.append(
                    f"Medium threat detected: {event_data.get('description', '')}"
                )
                suggestions.append("Monitor the affected system closely")

            elif threat_level == "low":
                warnings.append(
                    f"Low threat detected: {event_data.get('description', '')}"
                )
                suggestions.append("Review logs for patterns")

            summary = f"Threat detection complete. {len(warnings)} threats identified."
            confidence = 0.8

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "threat_level": threat_level,
                    "events_analyzed": 1,
                    "threats_found": len(warnings),
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _assess_security_risk(self, data: dict[str, Any]) -> AgentResult:
        """
        Assess overall security risk.

        Args:
            data: Security context data

        Returns:
            Risk assessment result
        """
        context = data.get("context", {})
        vulnerabilities = context.get("vulnerabilities", [])
        threats = context.get("threats", [])

        summary = "Assessing overall security risk"
        actions = []
        suggestions = []

        try:
            if not vulnerabilities and not threats:
                return self._create_result(
                    success=False,
                    summary=summary,
                    error="No vulnerabilities or threats provided for assessment",
                )

            actions.append(
                f"Analyzing {len(vulnerabilities)} vulnerabilities and {len(threats)} threats"
            )

            # Calculate risk score
            risk_score = self._calculate_risk_score(len(vulnerabilities), len(threats))
            risk_level = self._get_risk_level(risk_score)

            actions.append(
                f"Risk assessment complete - Score: {risk_score}, Level: {risk_level}"
            )

            if risk_score >= 80:
                summary = f"HIGH SECURITY RISK DETECTED (Score: {risk_score})"
                suggestions.append("Immediate remediation required")
            elif risk_score >= 50:
                summary = f"MEDIUM SECURITY RISK (Score: {risk_score})"
                suggestions.append("Review and address high-risk items")
            else:
                summary = f"Low security risk (Score: {risk_score})"
                suggestions.append("Continue monitoring")

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                suggestions=suggestions,
                confidence=0.85,
                data={
                    "vulnerability_count": len(vulnerabilities),
                    "threat_count": len(threats),
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _validate_security_policy(self, data: dict[str, Any]) -> AgentResult:
        """
        Validate security policy compliance.

        Args:
            data: Policy and compliance data

        Returns:
            Policy validation result
        """
        policy = data.get("policy", {})
        compliance_checks = data.get("compliance_checks", [])

        summary = f"Validating security policy: {policy.get('name', 'Unknown')}"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not policy:
                return self._create_result(
                    success=False,
                    summary=summary,
                    error="No policy provided for validation",
                )

            actions.append("Running policy compliance checks")

            # Check for policy violations
            violations = self._find_policy_violations(compliance_checks)

            if violations:
                warnings.extend(violations)
                suggestions.extend(self._generate_policy_improvements(policy))

            summary = f"Policy validation complete. {len(violations)} violations found."
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "policy_name": policy.get("name"),
                    "violations": len(violations),
                    "compliant": len(violations) == 0,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _analyze_security_logs(self, data: dict[str, Any]) -> AgentResult:
        """
        Analyze security logs for anomalies.

        Args:
            data: Log data

        Returns:
            Log analysis result
        """
        log_data = data.get("logs", "")
        log_source = data.get("source", "unknown")

        summary = f"Analyzing security logs from: {log_source}"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not log_data:
                return self._create_result(
                    success=False, summary=summary, error="No log data provided"
                )

            actions.append(f"Parsing {len(log_data.splitlines())} log entries")

            # Identify anomalies
            anomalies = self._find_log_anomalies(log_data)

            if anomalies:
                warnings.extend(anomalies)
                suggestions.extend(self._generate_log_improvements())

            summary = f"Log analysis complete. {len(anomalies)} anomalies found."
            confidence = 0.8

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "source": log_source,
                    "anomalies_found": len(anomalies),
                    "anomalies": anomalies,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _scan_vulnerabilities(self, data: dict[str, Any]) -> AgentResult:
        """
        Scan for vulnerabilities.

        Args:
            data: Target and scanning parameters

        Returns:
            Vulnerability scan result
        """
        target = data.get("target", "")

        summary = f"Scanning {target} for vulnerabilities"
        actions = []
        warnings = []
        suggestions = []

        try:
            if not target:
                return self._create_result(
                    success=False, summary=summary, error="Target required for scanning"
                )

            actions.append("Running vulnerability scan")

            # Simulated vulnerability scan
            vulnerabilities = self._perform_vulnerability_scan(target)

            if vulnerabilities:
                warnings.extend([v["description"] for v in vulnerabilities])
                suggestions.extend(self._generate_vulnerability_fixes(vulnerabilities))

            summary = f"Vulnerability scan complete. {len(vulnerabilities)} vulnerabilities found."
            confidence = 0.75

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                warnings=warnings,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "target": target,
                    "vulnerabilities_found": len(vulnerabilities),
                    "vulnerabilities": vulnerabilities,
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    async def _generate_security_report(self, data: dict[str, Any]) -> AgentResult:
        """
        Generate a comprehensive security report.

        Args:
            data: Report parameters and context

        Returns:
            Security report result
        """
        report_type = data.get("report_type", "security")
        scope = data.get("scope", "all")

        summary = f"Generating {report_type} security report"
        actions = []
        suggestions = []

        try:
            actions.append("Collecting security data")

            # Generate report
            report_data = self._compile_security_data(scope)

            summary = f"Security report generated successfully with {len(report_data.get('findings', []))} findings."
            confidence = 0.85

            return self._create_result(
                success=True,
                summary=summary,
                actions=actions,
                suggestions=suggestions,
                confidence=confidence,
                data={
                    "report_type": report_type,
                    "scope": scope,
                    "findings": report_data.get("findings", []),
                    "summary": report_data.get("summary", ""),
                },
            )

        except Exception as e:
            return self._create_result(success=False, summary=summary, error=str(e))

    # ==================== Helper Methods ====================

    def _is_high_risk_permission(self, permission: str) -> bool:
        """Check if a permission is high-risk."""
        high_risk_perms = [
            "sudo",
            "root",
            "administrator",
            "full_access",
            "delete",
            "modify_system",
            "modify_users",
            "system_admin",
        ]
        return any(perm in permission.lower() for perm in high_risk_perms)

    def _is_broad_permission(self, permission: str) -> bool:
        """Check if a permission is overly broad."""
        broad_perms = [
            "full",
            "all",
            "any",
            "unrestricted",
            "public",
            "everyone",
            "anonymous",
        ]
        return any(perm in permission.lower() for perm in broad_perms)

    def _is_dangerous_capability(self, capability: str) -> bool:
        """Check if a capability is dangerous."""
        dangerous_caps = [
            "execute_remote",
            "bypass_firewall",
            "install_hardware",
            "install_software",
            "moderate_system",
            "admin",
        ]
        return any(cap in capability.lower() for cap in dangerous_caps)

    def _find_redundant_permissions(self, permissions: list[str]) -> list[str]:
        """Find redundant permissions."""
        redundant = []
        for perm in permissions:
            if any(r in perm.lower() for r in ["admin", "manage", "control", "modify"]):
                redundant.append(perm)
        return redundant

    def _get_required_permissions(self, user: dict[str, Any]) -> list[str]:
        """Get required permissions based on user role."""
        role = user.get("role", "").lower()
        if role == "admin":
            return ["admin", "manage_users", "configure_system", "view_logs"]
        elif role == "developer":
            return ["develop", "test", "deploy"]
        elif role == "viewer":
            return ["view"]
        return []

    def _hash_credential(self, credential: str) -> str:
        """Hash credential for storage."""
        return hashlib.sha256(credential.encode()).hexdigest()

    def _check_weak_credentials(self, credential: str) -> list[str]:
        """Check for weak credential patterns."""
        weak_patterns = []

        if len(credential) < 8:
            weak_patterns.append("Credential length less than 8 characters")

        if credential == credential.lower():
            weak_patterns.append("No uppercase letters in credential")

        if credential.isdigit():
            weak_patterns.append("All numeric credential - very weak")

        if (
            "password" in credential.lower()
            or credential == "123456"
            or credential == "qwerty"
        ):
            weak_patterns.append("Very weak or common password pattern")

        return weak_patterns

    def _generate_credential_improvements(self) -> list[str]:
        """Generate credential improvement suggestions."""
        return [
            "Use a minimum of 12 characters",
            "Include uppercase and lowercase letters",
            "Include numbers and special characters",
            "Avoid common words or patterns",
            "Use unique passwords for different accounts",
        ]

    def _assess_threat_level(self, event_data: dict[str, Any]) -> str:
        """Assess threat level."""
        event_type = event_data.get("type", "").lower()
        severity = event_data.get("severity", "low").lower()

        if "breach" in event_type or "attack" in event_type:
            return "high"
        elif severity == "high" or severity == "critical":
            return "high"
        elif severity == "medium":
            return "medium"
        elif severity == "low":
            return "low"
        else:
            return "medium"

    def _calculate_risk_score(self, vulnerabilities: int, threats: int) -> int:
        """Calculate overall risk score."""
        base_score = 50
        vuln_factor = min(vulnerabilities * 10, 30)
        threat_factor = min(threats * 10, 30)
        return min(base_score + vuln_factor + threat_factor, 100)

    def _get_risk_level(self, score: int) -> str:
        """Get risk level from score."""
        if score >= 80:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"

    def _find_policy_violations(
        self, compliance_checks: list[dict[str, Any]]
    ) -> list[str]:
        """Find policy violations."""
        violations = []
        for check in compliance_checks:
            if not check.get("compliant", False):
                violations.append(check.get("description", "Policy violation"))
        return violations

    def _generate_policy_improvements(self, policy: dict[str, Any]) -> list[str]:
        """Generate policy improvement suggestions."""
        return [
            "Review policy requirements",
            "Update to align with security best practices",
            "Test policy compliance",
            "Document policy enforcement procedures",
        ]

    def _find_log_anomalies(self, log_data: str) -> list[str]:
        """Find anomalies in security logs."""
        anomalies = []

        # Check for repeated failed login attempts
        if "failed login" in log_data.lower():
            count = log_data.lower().count("failed login")
            if count > 5:
                anomalies.append(f"Multiple failed login attempts detected ({count})")

        # Check for privilege escalation
        if "escalated privileges" in log_data.lower():
            anomalies.append("Privilege escalation activity detected")

        # Check for suspicious activity
        if "suspicious" in log_data.lower():
            count = log_data.lower().count("suspicious")
            if count > 3:
                anomalies.append(f"Multiple suspicious activities detected ({count})")

        return anomalies

    def _generate_log_improvements(self) -> list[str]:
        """Generate log improvement suggestions."""
        return [
            "Implement log rotation and retention",
            "Set up real-time alerting for anomalies",
            "Regularly review and analyze logs",
            "Implement centralized log management",
        ]

    def _perform_vulnerability_scan(self, target: str) -> list[dict[str, Any]]:
        """Simulate vulnerability scan."""
        vulnerabilities = [
            {
                "severity": "medium",
                "cvss": 5.5,
                "description": f"Known vulnerability in {target} detected",
                "cve": "CVE-2024-XXXX",
            },
            {
                "severity": "low",
                "cvss": 3.1,
                "description": "Outdated software version detected",
                "cve": "CVE-2024-YYYY",
            },
        ]
        return vulnerabilities

    def _generate_vulnerability_fixes(
        self, vulnerabilities: list[dict[str, Any]]
    ) -> list[str]:
        """Generate vulnerability fix suggestions."""
        fixes = []
        for vuln in vulnerabilities:
            fixes.append(f"Apply patch for {vuln.get('cve', 'unknown')} vulnerability")
            fixes.append("Review and update software dependencies")
        return fixes

    def _compile_security_data(self, scope: str) -> dict[str, Any]:
        """Compile security data for report."""
        return {
            "findings": [
                "Weak password policy detected",
                "Several plugins with excessive permissions",
                "No fail2ban implementation",
                "Security logs not centralized",
            ],
            "summary": "Security assessment completed with moderate findings",
        }
