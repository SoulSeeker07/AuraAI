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


@pytest.fixture(autouse=True)
def isolate_memory_databases(tmp_path, monkeypatch):
    """
    Ensure Memory and ProfileMemory default paths are strictly isolated to a temporary
    sandbox database during test runs, preventing any test suite from ever reading or
    writing to production Memory.db or Data/profile.db.
    """
    sandbox_memory_db = str(tmp_path / "sandbox_Memory.db")
    sandbox_profile_db = tmp_path / "sandbox_profile.db"

    # Patch Memory.__init__ default db_path
    from Memory import Memory, MEMORY_DB
    orig_memory_init = Memory.__init__

    def sandboxed_memory_init(self, db_path="Memory.db", **kwargs):
        if db_path in ("Memory.db", None) or os.path.basename(str(db_path)) == "Memory.db":
            db_path = sandbox_memory_db
        return orig_memory_init(self, db_path=db_path, **kwargs)

    monkeypatch.setattr(Memory, "__init__", sandboxed_memory_init)

    # Patch ProfileMemory default path and reset instance
    try:
        from core.memory.profile_memory import ProfileMemory
        ProfileMemory.reset_instance()
        orig_get_instance = ProfileMemory.get_instance

        @classmethod
        def sandboxed_profile_get_instance(cls, db_path=None):
            if db_path is None or str(db_path).endswith("profile.db"):
                db_path = sandbox_profile_db
            return orig_get_instance(db_path=db_path)

        monkeypatch.setattr(ProfileMemory, "get_instance", sandboxed_profile_get_instance)
    except ImportError:
        pass

    yield

    try:
        from core.memory.profile_memory import ProfileMemory
        ProfileMemory.reset_instance()
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


@pytest.fixture(autouse=True)
def guard_live_browser_and_external_apis(monkeypatch, request):
    """
    Prevent any unit test from accidentally launching real Playwright browser
    instances or making live external network/API calls.
    Tests that specifically test live browser integration can mark @pytest.mark.live_browser.
    """
    if "live_browser" in request.keywords:
        yield
        return

    try:
        import browser.run_browser_goal as rbg

        def fake_run_browser_goal(goal: str, max_steps: int = 20):
            return {
                "status": "SUCCESS",
                "summary": f"[MOCK TEST BROWSER] Completed: {goal}",
                "screenshot_path": None,
                "steps": [
                    {
                        "step": 0,
                        "tool": "navigate",
                        "args": {"url": "https://example.com"},
                        "result": "Navigated to https://example.com",
                    },
                    {
                        "step": 1,
                        "tool": "extract_text",
                        "args": {"description": "page body"},
                        "result": f"Sample mock text for {goal}",
                    },
                    {
                        "step": 2,
                        "tool": "done",
                        "args": {"summary": f"[MOCK TEST BROWSER] Completed: {goal}"},
                        "result": f"[MOCK TEST BROWSER] Completed: {goal}",
                    },
                ],
            }

        monkeypatch.setattr(rbg, "run_browser_goal", fake_run_browser_goal)
    except (ImportError, AttributeError):
        pass

    try:
        import browser.agent_loop as bal

        def fake_run_goal(goal: str, max_steps: int = 15, **kwargs):
            return {
                "status": "SUCCESS",
                "summary": f"[MOCK TEST BROWSER] Completed: {goal}",
                "screenshot_path": None,
                "steps": [
                    {
                        "step": 0,
                        "tool": "navigate",
                        "args": {"url": "https://example.com"},
                        "result": "Navigated to https://example.com",
                    },
                    {
                        "step": 1,
                        "tool": "extract_text",
                        "args": {"description": "page body"},
                        "result": f"Sample mock text for {goal}",
                    },
                    {
                        "step": 2,
                        "tool": "done",
                        "args": {"summary": f"[MOCK TEST BROWSER] Completed: {goal}"},
                        "result": f"[MOCK TEST BROWSER] Completed: {goal}",
                    },
                ],
            }

        monkeypatch.setattr(bal, "run_goal", fake_run_goal)
    except (ImportError, AttributeError):
        pass

    yield



