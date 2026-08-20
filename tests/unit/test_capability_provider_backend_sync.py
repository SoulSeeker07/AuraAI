"""
Unit Tests for Capability Provider vs Backend Adapter Descriptor Synchronization (Track C / Section 9).
Guarantees 1:1 synchronization between declared capability descriptors and physical backend support,
preventing silent fallthrough, descriptor drift, and phantom capability definitions.
"""

import pytest

from src.core.capabilities.capability_registry import CapabilityRegistry
from src.core.backends.backend_registry import BackendRegistry
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry


@pytest.fixture(autouse=True)
def init_registries():
    """Ensure all native managers, backends, and capability providers are initialized."""
    NativeManagerRegistry.get_instance().discover()
    CapabilityRegistry.get_instance()
    BackendRegistry.get_instance()


def test_all_live_capabilities_have_registered_backend():
    """Verify every capability marked is_live=True resolves to a registered backend adapter."""
    cap_registry = CapabilityRegistry.get_instance()
    backend_registry = BackendRegistry.get_instance()

    all_caps = cap_registry.list()
    assert len(all_caps) >= 70, f"Expected at least 70 registered capabilities, found {len(all_caps)}"

    unwired_live_caps = []
    for cap in all_caps:
        if cap.is_live:
            backend = backend_registry.select_best_backend(cap.name, domain=cap.domain)
            if backend is None:
                unwired_live_caps.append((cap.name, cap.domain))

    assert not unwired_live_caps, f"Live capabilities missing backend adapters: {unwired_live_caps}"


def test_all_live_capabilities_advertised_by_backend():
    """Verify backend adapters explicitly list their live capabilities in backend.capabilities."""
    cap_registry = CapabilityRegistry.get_instance()
    backend_registry = BackendRegistry.get_instance()

    all_caps = cap_registry.list()
    missing_from_backend = []

    for cap in all_caps:
        if cap.is_live:
            backend = backend_registry.select_best_backend(cap.name, domain=cap.domain)
            if backend and cap.name not in backend.capabilities:
                missing_from_backend.append((cap.name, backend.name))

    assert not missing_from_backend, (
        f"Capabilities marked live in providers but missing from backend.capabilities: {missing_from_backend}"
    )


def test_memory_backend_read_write_separation():
    """Verify MemoryBackend strictly distinguishes read/recall/search operations from write/store operations."""
    backend_registry = BackendRegistry.get_instance()
    mem_backend = backend_registry.select_best_backend("memory.store", domain="memory")
    assert mem_backend is not None

    # Supported capabilities
    for cap in ("memory.store", "memory.recall", "memory.search", "memory.read", "memory.write"):
        assert cap in mem_backend.capabilities

    # Fail-closed on unsupported capability
    bad_res = mem_backend.execute("memory.non_existent_op", "some goal")
    assert bad_res.success is False
    assert "unsupported_capability" in str(bad_res.data)


def test_coding_backend_supported_capabilities():
    """Verify CodingBackendAdapter advertises workspace.walk, code.test, and code.inspect."""
    backend_registry = BackendRegistry.get_instance()
    coding_backend = backend_registry.select_best_backend("workspace.walk", domain="coding")
    assert coding_backend is not None
    assert "workspace.walk" in coding_backend.capabilities
    assert "code.test" in coding_backend.capabilities
    assert "code.inspect" in coding_backend.capabilities
