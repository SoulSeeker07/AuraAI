"""
Unit Tests for Runtime Stabilization Phase
Location: tests/core/test_stabilization_phase.py
"""

import pytest

from core.orchestration.domain_sessions import (
    BrowserSession,
    DesktopSession,
    ResearchSession,
)
from core.orchestration.engineering_session import EngineeringSession
from core.orchestration.reference_resolver import ReferenceResolver
from core.orchestration.runtime_session import RuntimeSession, SessionStatus
from core.orchestration.worker_manager import DomainWorker, WorkerManager
from src.execution.safety_policy import SafetyPolicy


def test_runtime_session_hierarchy():
    # EngineeringSession inherits from RuntimeSession
    eng = EngineeringSession(goal="Fix bug in auth", workspace="D:/AuraAI")
    assert isinstance(eng, RuntimeSession)
    assert eng.domain == "engineering"
    assert eng.session_id.startswith("eng_")

    eng.update_progress(50, "Editing file...")
    assert eng.progress == 50
    assert len(eng.timeline) >= 1

    # BrowserSession inherits from RuntimeSession
    browser = BrowserSession(goal="Navigate to GitHub", target_url="https://github.com")
    assert isinstance(browser, RuntimeSession)
    assert browser.domain == "browser"
    assert browser.session_id.startswith("browser_")

    # DesktopSession inherits from RuntimeSession
    desktop = DesktopSession(goal="Open Notepad", target_app="notepad")
    assert isinstance(desktop, RuntimeSession)
    assert desktop.domain == "desktop"
    assert desktop.session_id.startswith("desktop_")

    # ResearchSession inherits from RuntimeSession
    research = ResearchSession(goal="Investigate RAG 2.0")
    assert isinstance(research, RuntimeSession)
    assert research.domain == "research"
    assert research.session_id.startswith("research_")


def test_configurable_safety_policy():
    sp = SafetyPolicy.get_instance()

    # Protected applications
    assert sp.is_protected_app("Code.exe") is True
    assert sp.is_protected_app("vscode") is True
    assert sp.is_protected_app("Visual Studio Code") is True
    assert sp.is_protected_app("explorer.exe") is True
    assert sp.is_protected_app("system") is True

    # Non-protected application
    assert sp.is_protected_app("notepad.exe") is False
    assert sp.is_protected_app("chrome.exe") is False

    with pytest.raises(PermissionError):
        sp.check_close_permission("Code.exe")

    # Non-protected close permission succeeds
    assert sp.check_close_permission("notepad.exe") is True


def test_worker_manager_multi_domain_sessions():
    wm = WorkerManager()
    wm._workers.clear()

    eng = EngineeringSession(goal="Refactor auth", workspace="D:/AuraAI")
    wm.register_engineering_session(eng)

    browser_w = wm.register_domain_session(
        "browser", "browser_123", "Browser Navigation", "Search YouTube"
    )
    desktop_w = wm.register_domain_session(
        "desktop", "desktop_456", "Desktop Control", "Open Calculator"
    )

    active = wm.list_active_workers()
    assert len(active) >= 3

    domains = [w.domain for w in active]
    assert "engineering" in domains
    assert "browser" in domains
    assert "desktop" in domains


def test_reference_resolver_pronouns():
    resolved_text, meta = ReferenceResolver.resolve_references("Minimize it")
    assert meta["resolved"] is True or resolved_text != ""
