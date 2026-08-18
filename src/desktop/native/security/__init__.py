"""
Security & Cryptographic Authorization Subsystem for Native Desktop Operations
Location: src/desktop/native/security/__init__.py
"""

from .approval_authority import ApprovalTicket, CryptographicApprovalAuthority
from .audit_logger import SecurityAuditLogger
from .audit_ipc import AuditIPCClient, AuditIPCServer
from .audit_writer_service import AuditWriterService
from .dpapi_key_manager import DPAPIKeyManager, KeyEnvelopeMetadata
from .windows_event_sink import CanonicalAuditRecord, WindowsEventAuditSink
from .governance import (
    DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST,
    HARD_BLOCKED_HOSTNAMES,
    HARD_BLOCKED_IP_NETWORKS,
    HOST_CONTEXT_MUTATION_EXCEPTIONS,
    UNCONDITIONAL_HARD_BLOCKED_CAPABILITIES,
    is_host_context_exception,
    is_unconditionally_hard_blocked,
)
from .network_policy import EgressDecision, NetworkPolicyEngine

__all__ = [
    "ApprovalTicket",
    "CryptographicApprovalAuthority",
    "SecurityAuditLogger",
    "AuditIPCClient",
    "AuditIPCServer",
    "AuditWriterService",
    "DPAPIKeyManager",
    "KeyEnvelopeMetadata",
    "CanonicalAuditRecord",
    "WindowsEventAuditSink",
    "HOST_CONTEXT_MUTATION_EXCEPTIONS",
    "UNCONDITIONAL_HARD_BLOCKED_CAPABILITIES",
    "HARD_BLOCKED_IP_NETWORKS",
    "HARD_BLOCKED_HOSTNAMES",
    "DEFAULT_DEVELOPER_DOMAIN_ALLOWLIST",
    "is_host_context_exception",
    "is_unconditionally_hard_blocked",
    "EgressDecision",
    "NetworkPolicyEngine",
]
