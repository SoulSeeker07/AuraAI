# Ensure the src/ directory is on sys.path so tests can import src-based packages
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
EXAMPLES = os.path.join(ROOT, "examples")

if SRC not in sys.path:
    sys.path.insert(0, SRC)
if ROOT not in sys.path:
    sys.path.insert(1, ROOT)
if EXAMPLES not in sys.path:
    sys.path.insert(2, EXAMPLES)

import pytest

@pytest.fixture(autouse=True)
def cleanup_singletons():
    """
    Ensure singleton registries and thread pools are cleanly shut down and reset
    after every test to prevent cross-test pollution and leaked background state.
    """
    yield
    try:
        from brain.world_model import WorldModel
        WorldModel.reset_instance()
    except ImportError:
        pass
    try:
        from desktop.native.managers.native_manager_registry import NativeManagerRegistry
        NativeManagerRegistry.reset_instance()
    except ImportError:
        pass
    try:
        from desktop.native.desktop_execution_engine import reset_desktop_execution_engine
        reset_desktop_execution_engine()
    except ImportError:
        pass
    try:
        from desktop.native.security.approval_authority import CryptographicApprovalAuthority
        CryptographicApprovalAuthority.reset_instance()
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def isolate_approval_tickets(tmp_path):
    """
    Ensure CryptographicApprovalAuthority singletons are scoped to an isolated
    temporary file during testing, preventing any test tickets from polluting
    production storage/approval_tickets.json.
    """
    try:
        from desktop.native.security.approval_authority import CryptographicApprovalAuthority
        CryptographicApprovalAuthority.DEFAULT_STORAGE_PATH = tmp_path / "test_approval_tickets.json"
        CryptographicApprovalAuthority.reset_instance()
        CryptographicApprovalAuthority.get_instance(storage_path=tmp_path / "test_approval_tickets.json")
    except ImportError:
        pass
    yield
    try:
        from desktop.native.security.approval_authority import CryptographicApprovalAuthority
        CryptographicApprovalAuthority.reset_instance()
        CryptographicApprovalAuthority.DEFAULT_STORAGE_PATH = None
    except ImportError:
        pass


@pytest.fixture
def universal_dispatch_spy(monkeypatch):
    """
    Shared test fixture enforcing Invariant 3 (Dispatch-Level Idempotency)
    across all backends (Desktop, CodeAct, Browser, Research, Terminal, etc.).
    Instruments both async DAG level execution (MasterOrchestrator._dispatch_to_backend)
    and synchronous plan execution (MasterOrchestrator._dispatch_plan).
    """
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from tests.helpers.suspend_resume_invariants import UniversalDispatchSpy

    spy = UniversalDispatchSpy()
    orig_dispatch_async = MasterOrchestrator._dispatch_to_backend
    orig_dispatch_plan = MasterOrchestrator._dispatch_plan

    async def spied_dispatch_async(self, backend, task_id, subtask, context):
        spy.record(
            task_id=task_id,
            capability=subtask.capability,
            backend_name=getattr(backend, "name", str(backend)),
            parameters=subtask.parameters or {},
        )
        return await orig_dispatch_async(self, backend, task_id, subtask, context)

    def spied_dispatch_plan(self, backend, action_plan, task_id="", _from_async_dispatch=False):
        if not _from_async_dispatch:
            spy.record(
                task_id=task_id or getattr(action_plan, "plan_id", getattr(action_plan, "capability", "")),
                capability=getattr(action_plan, "capability", ""),
                backend_name=getattr(backend, "name", str(backend)),
                parameters=getattr(action_plan, "arguments", {}) or {},
            )
        return orig_dispatch_plan(self, backend, action_plan, task_id=task_id, _from_async_dispatch=_from_async_dispatch)

    monkeypatch.setattr(MasterOrchestrator, "_dispatch_to_backend", spied_dispatch_async)
    monkeypatch.setattr(MasterOrchestrator, "_dispatch_plan", spied_dispatch_plan)
    return spy


