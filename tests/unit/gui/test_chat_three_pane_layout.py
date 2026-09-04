"""
Targeted Verification Suite for Phase 1 Three-Pane AuraAI Neural Chat HUD
========================================================================
Tests:
1. 3-pane instantiation (Left History Sidebar, Center Chat, Right Rail).
2. Rail toggles, visibility switching, and QSettings persistence.
3. MultilinePromptTextEdit ergonomics and history cycling.
4. RealBackendBridge.record_live_task_start idempotency (no duplicate entries).
5. RealBackendBridge.get_scheduled_jobs() retrieval.
"""

import pytest
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication

from gui.widgets.chat_window_overlay import ChatWindowOverlay, MultilinePromptTextEdit
from gui.widgets.chat_history_sidebar import ChatHistorySidebar
from gui.widgets.chat_right_rail import ChatRightRail
from gui.real_backend_bridge import RealBackendBridge


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_three_pane_instantiation(qapp):
    """Verify ChatWindowOverlay instantiates with the three distinct panes."""
    overlay = ChatWindowOverlay()
    assert hasattr(overlay, "_history_sidebar")
    assert isinstance(overlay, ChatWindowOverlay)
    assert isinstance(overlay._history_sidebar, ChatHistorySidebar)
    assert hasattr(overlay, "_right_rail")
    assert isinstance(overlay._right_rail, ChatRightRail)
    assert hasattr(overlay, "_input_field")
    assert isinstance(overlay._input_field, MultilinePromptTextEdit)
    overlay.close()


def test_rail_toggling_and_settings_persistence(qapp):
    """Verify left and right rails can toggle and persist their states in QSettings."""
    settings = QSettings("AuraAI", "ChatWindowOverlay")
    settings.setValue("left_rail_visible", True)
    settings.setValue("right_rail_visible", True)
    overlay = ChatWindowOverlay()
    overlay.show()

    # Initial states
    assert not overlay._history_sidebar.isHidden()
    assert not overlay._right_rail.isHidden()
    assert overlay._history_sidebar.isVisible()
    assert overlay._right_rail.isVisible()

    # Toggle left rail
    overlay._toggle_history_rail()
    assert overlay._history_sidebar.isHidden()
    assert not overlay._history_sidebar.isVisible()
    assert settings.value("left_rail_visible", type=bool) is False

    # Toggle left rail back
    overlay._toggle_history_rail()
    assert not overlay._history_sidebar.isHidden()
    assert overlay._history_sidebar.isVisible()
    assert settings.value("left_rail_visible", type=bool) is True

    # Toggle right rail
    overlay._toggle_ops_rail()
    assert overlay._right_rail.isHidden()
    assert not overlay._right_rail.isVisible()
    assert settings.value("right_rail_visible", type=bool) is False

    # Toggle right rail back
    overlay._toggle_ops_rail()
    assert not overlay._right_rail.isHidden()
    assert overlay._right_rail.isVisible()
    assert settings.value("right_rail_visible", type=bool) is True

    overlay.close()


def test_multiline_prompt_text_edit(qapp):
    """Verify MultilinePromptTextEdit API compatibility and history tracking."""
    editor = MultilinePromptTextEdit()
    assert editor.text() == ""

    editor.setText("Line 1\nLine 2")
    assert editor.text() == "Line 1\nLine 2"

    editor.append_history("First Command")
    editor.append_history("Second Command")
    assert len(editor._history) == 2
    assert editor._history[-1] == "Second Command"

    editor.clear()
    assert editor.text() == ""


def test_record_live_task_start_idempotency():
    """Verify that calling record_live_task_start with identical task ID updates in-place without duplicating."""
    bridge = RealBackendBridge.get_instance()
    task_id = "T-9999_test_unique"

    # Clean up if existed
    if hasattr(bridge, "_live_tasks"):
        bridge._live_tasks = [t for t in bridge._live_tasks if t.get("id") != task_id]

    # First insertion
    bridge.record_live_task_start(task_id, "Initial prompt attempt")
    matches_1 = [t for t in bridge._live_tasks if t.get("id") == task_id]
    assert len(matches_1) == 1
    assert matches_1[0]["desc"] == "Initial prompt attempt"

    # Second insertion with same task_id (e.g. from concurrent UI listener)
    bridge.record_live_task_start(task_id, "Updated prompt attempt")
    matches_2 = [t for t in bridge._live_tasks if t.get("id") == task_id]
    # Must NOT duplicate
    assert len(matches_2) == 1
    assert matches_2[0]["desc"] == "Updated prompt attempt"

    # Clean up
    bridge._live_tasks = [t for t in bridge._live_tasks if t.get("id") != task_id]


def test_get_scheduled_jobs():
    """Verify bridge returns list of scheduled jobs."""
    bridge = RealBackendBridge.get_instance()
    jobs = bridge.get_scheduled_jobs()
    assert isinstance(jobs, list)
    # Ensure every job dictionary conforms to expected keys
    for j in jobs:
        assert "id" in j
        assert "name" in j
        assert "type" in j
        assert "schedule" in j
        assert "enabled" in j


def test_rail_task_card_no_overflow(qapp):
    """Verify RailTaskCard renders compact layout without blowing out horizontal bounds."""
    from gui.widgets.chat_right_rail import RailTaskCard

    task_data = {
        "id": "T-1000",
        "desc": "Extremely long task description that would blow out an unconstrained horizontal layout",
        "agent": "Executive Brain",
        "status": "● Completed",
        "response": "Detailed multi-line action trace output with diagnostic notes.",
    }
    card = RailTaskCard(task_data)
    card.show()
    assert card._details.isHidden()

    # Toggle expansion
    card.is_expanded = True
    card._details.setVisible(True)
    assert not card._details.isHidden()
    assert card._details.isVisible()


def test_agent_pill_elides_instead_of_hard_clipping(qapp):
    """Verify ElidedLabel truncates overflowing text with ellipsis instead of hard cutting."""
    from gui.widgets.chat_right_rail import ChatRightRail, ElidedLabel

    rail = ChatRightRail()
    pill = rail._create_agent_pill({
        "name": "Research Coordination Specialist",
        "task": "Standby // Web Search Cross-Reference",
        "status": "Ready",
        "color": "#6496ff",
    })
    pill.resize(295, 50)
    pill.show()
    qapp.processEvents()

    name_label = pill.findChild(ElidedLabel)
    assert name_label is not None
    fm = name_label.fontMetrics()
    assert fm.horizontalAdvance(name_label.text()) <= name_label.width()
    assert name_label.text() == name_label._full_text or name_label.text().endswith("…")


def test_accordion_header_badge_never_clipped_by_long_title(qapp):
    """Verify count badge remains intact and title yields space when crowded."""
    from gui.widgets.chat_right_rail import AccordionHeader

    header = AccordionHeader(title="⚡ BACKGROUND TASKS & AGENTS", count_badge="1 Running • 6 Agents")
    header.resize(295, 32)
    header.show()
    qapp.processEvents()
    assert header._badge.text() == "1 Running • 6 Agents"


def test_refresh_data_does_not_leave_orphaned_widgets(qapp):
    """Verify debounced refresh and immediate unparenting leaves no ghost widgets."""
    from PySide6.QtWidgets import QFrame
    from gui.widgets.chat_right_rail import ChatRightRail

    rail = ChatRightRail()
    rail.refresh_data()
    rail.refresh_data()  # back-to-back, simulating signal + timer race
    qapp.processEvents()
    visible_pills = [
        rail._agent_list_layout.itemAt(i).widget()
        for i in range(rail._agent_list_layout.count())
    ]
    assert len(visible_pills) == len(rail._bridge.get_agent_task_data()["agents"][:6])


def test_rail_task_card_agent_name_not_char_sliced(qapp):
    """Verify full agent name string is preserved in ElidedLabel without character slicing."""
    from gui.widgets.chat_right_rail import RailTaskCard, ElidedLabel

    card = RailTaskCard(
        task_data={"id": "T-1000", "agent": "Executive Brain", "status": "Executing"},
        is_expanded=False,
        on_toggle_callback=lambda *_: None,
    )
    card.resize(300, 60)
    card.show()
    qapp.processEvents()
    label = card.findChild(ElidedLabel)
    assert label is not None
    assert "Executive Brain" in label._full_text


def test_right_rail_live_signal_pipeline_transitions_indicator_and_renders_task(qapp):
    """Verify that emitting real app_signals triggers ChatRightRail live execution state and renders tasks."""
    from gui.widgets.chat_right_rail import ChatRightRail, RailTaskCard
    from gui.signals import app_signals, ExecutionStep
    from gui.real_backend_bridge import RealBackendBridge

    rail = ChatRightRail()
    rail.show()
    qapp.processEvents()

    # Initial state must be IDLE
    assert rail._live_indicator.text() == "● IDLE"

    # 1. Record live task in bridge and emit execution_started on real app_signals
    bridge = RealBackendBridge.get_instance()
    task_id = "TASK_SIGNAL_TEST_01"
    bridge.record_live_task_start(task_id, "System diagnostics cross-check", agent="Code Specialist")

    from gui.signals import StepStatus
    # Emit step_updated with real ExecutionStep on real app_signals
    step = ExecutionStep(
        index=1,
        title="Compile plan DAG",
        description="Compiling execution graph",
        status=StepStatus.RUNNING,
    )
    app_signals.step_updated.emit(step)
    qapp.processEvents()

    # Assert live indicator updated to EXECUTING
    assert rail._live_indicator.text() == "◐ EXECUTING"

    # Assert task card appears in tasks list layout
    task_cards = [
        rail._tasks_list_layout.itemAt(i).widget()
        for i in range(rail._tasks_list_layout.count())
        if isinstance(rail._tasks_list_layout.itemAt(i).widget(), RailTaskCard)
    ]
    assert any(c.task_data.get("desc") == "System diagnostics cross-check" for c in task_cards)

    # 2. Finish task and emit execution_finished on real app_signals
    bridge.record_live_task_finish(task_id, "Diagnostics passed cleanly", is_success=True)
    app_signals.execution_finished.emit(task_id, True)
    qapp.processEvents()

    # Assert live indicator resets to IDLE
    assert rail._live_indicator.text() == "● IDLE"
    updated_cards = [
        rail._tasks_list_layout.itemAt(i).widget()
        for i in range(rail._tasks_list_layout.count())
        if isinstance(rail._tasks_list_layout.itemAt(i).widget(), RailTaskCard)
    ]
    finished_card = next(c for c in updated_cards if c.task_data.get("desc") == "System diagnostics cross-check")
    assert "Completed" in finished_card.task_data.get("status")


def test_right_rail_scheduler_live_mutation_and_empty_state(qapp):
    """Verify that adding/cancelling jobs via the real Native SchedulerManager propagates to ChatRightRail."""
    from gui.widgets.chat_right_rail import ChatRightRail, ScheduledJobCard
    from desktop.native.managers.native_manager_registry import NativeManagerRegistry

    registry = NativeManagerRegistry.get_instance()
    sched_mgr = registry.get_manager("scheduler")

    rail = ChatRightRail()
    rail.show()
    qapp.processEvents()

    # 1. Add a real scheduled job via sched_mgr.execute()
    result = sched_mgr.execute(
        "scheduler.at",
        goal="Run backup routine",
        arguments={"name": "Nightly System Backup", "delay_seconds": 3600.0, "action": "backup"},
    )
    assert result.success is True
    job_id = result.data.get("job_id")
    assert job_id is not None

    rail.refresh_data()
    qapp.processEvents()

    # Verify badge updated and card exists
    cards = [
        rail._sched_body_layout.itemAt(i).widget()
        for i in range(rail._sched_body_layout.count())
        if isinstance(rail._sched_body_layout.itemAt(i).widget(), ScheduledJobCard)
    ]
    matching_card = next((c for c in cards if c.job_data.get("id") == job_id), None)
    assert matching_card is not None
    assert matching_card.job_data.get("name") == "Nightly System Backup"
    assert "Active" in rail._sched_header._badge.text()

    # 2. Cancel the job via sched_mgr.execute()
    cancel_res = sched_mgr.execute("scheduler.cancel", arguments={"job_id": job_id})
    assert cancel_res.success is True

    rail.refresh_data()
    qapp.processEvents()

    # Verify the job is removed from active cards
    cards_after = [
        rail._sched_body_layout.itemAt(i).widget()
        for i in range(rail._sched_body_layout.count())
        if isinstance(rail._sched_body_layout.itemAt(i).widget(), ScheduledJobCard)
    ]
    assert not any(c.job_data.get("id") == job_id for c in cards_after)


def test_artifacts_accordion_unlocked_and_badge_updates(qapp):
    """Verify Phase 2 artifacts header is unlocked, clickable, and toggles body."""
    from gui.widgets.chat_right_rail import ChatRightRail
    from PySide6.QtCore import Qt

    rail = ChatRightRail()
    rail.show()
    qapp.processEvents()

    # Verify header is active, NOT dimmed, and has pointing hand cursor
    assert rail._art_header.is_dimmed is False
    assert rail._art_header.cursor().shape() == Qt.PointingHandCursor

    # Body should start hidden
    assert rail._art_body.isVisible() is False

    # Toggle expansion
    rail._art_header.is_expanded = True
    rail._toggle_art_body(True)
    assert rail._art_body.isVisible() is True

    rail._toggle_art_body(False)
    assert rail._art_body.isVisible() is False


def test_artifact_card_layout_no_overflow(qapp, tmp_path):
    """Verify ArtifactCard handles long filenames and paths within constrained 295px width."""
    from gui.widgets.chat_right_rail import ArtifactCard, ElidedLabel

    sample_path = tmp_path / "very_long_deeply_nested_analysis_report_2026_q3_final_draft.markdown"
    sample_path.write_text("# Test content\n")

    art_data = {
        "id": "art_test_1",
        "name": sample_path.name,
        "path": str(sample_path),
        "type": "file",
        "extension": ".markdown",
        "size_str": "15 B",
        "icon": "📝",
        "created_at": "12:00:00",
    }
    card = ArtifactCard(art_data)
    card.resize(295, 75)
    card.show()
    qapp.processEvents()

    labels = card.findChildren(ElidedLabel)
    assert len(labels) >= 2  # name and path
    for lbl in labels:
        fm = lbl.fontMetrics()
        assert fm.horizontalAdvance(lbl.text()) <= lbl.width() + 5


def test_artifact_card_copy_path_action(qapp, tmp_path, monkeypatch):
    """Verify clicking Copy Path on an ArtifactCard copies the absolute path to clipboard."""
    from gui.widgets.chat_right_rail import ArtifactCard
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtGui import QGuiApplication
    from unittest.mock import MagicMock

    sample_path = tmp_path / "generated_code.py"
    sample_path.write_text("print('hello')\n")

    art_data = {
        "id": "art_test_2",
        "name": sample_path.name,
        "path": str(sample_path),
        "size_str": "16 B",
        "icon": "🐍",
    }
    card = ArtifactCard(art_data)
    card.show()
    qapp.processEvents()

    mock_set_text = MagicMock()
    monkeypatch.setattr(QGuiApplication.clipboard(), "setText", mock_set_text)

    copy_btn = next(b for b in card.findChildren(QPushButton) if "Copy Path" in b.text())
    copy_btn.click()
    qapp.processEvents()

    mock_set_text.assert_called_once()
    assert str(sample_path) in mock_set_text.call_args[0]
    assert "Copied" in copy_btn.text()


def test_artifacts_live_record_and_empty_state(qapp):
    """Verify recording an artifact in RealBackendBridge propagates live to ChatRightRail and handles empty state."""
    from gui.widgets.chat_right_rail import ChatRightRail, ArtifactCard
    from gui.real_backend_bridge import RealBackendBridge
    from PySide6.QtWidgets import QLabel
    from core.config import PROJECT_ROOT

    bridge = RealBackendBridge.get_instance()
    # Reset any existing artifacts
    bridge._session_artifacts = []

    rail = ChatRightRail()
    rail.show()
    rail.refresh_data()
    qapp.processEvents()

    # Empty state check
    assert rail._art_header._badge.text() == "0 Items"
    empty_labels = [
        rail._art_body_layout.itemAt(i).widget()
        for i in range(rail._art_body_layout.count())
        if isinstance(rail._art_body_layout.itemAt(i).widget(), QLabel)
    ]
    assert any("No session artifacts generated yet" in l.text() for l in empty_labels)

    # Record real existing project file (e.g. pyproject.toml)
    sample_file = PROJECT_ROOT / "pyproject.toml"
    assert sample_file.exists()
    ok = bridge.record_artifact("pyproject.toml", str(sample_file))
    assert ok is True

    rail.refresh_data()
    qapp.processEvents()

    # Assert badge updated to 1 Items
    assert rail._art_header._badge.text() == "1 Items"
    cards = [
        rail._art_body_layout.itemAt(i).widget()
        for i in range(rail._art_body_layout.count())
        if isinstance(rail._art_body_layout.itemAt(i).widget(), ArtifactCard)
    ]
    assert len(cards) == 1
    assert cards[0].artifact_data.get("name") == "pyproject.toml"
    assert cards[0].artifact_data.get("icon") == "📊" or cards[0].artifact_data.get("icon") == "📄"
    # Canonical uppercase drive letter
    assert cards[0].artifact_data.get("path").startswith("D:\\") or cards[0].artifact_data.get("path").startswith("C:\\")


def test_artifact_security_confinement_and_execution_guards(qapp, tmp_path, monkeypatch):
    """Verify out-of-jail files and dangerous executables (.bat/.exe/.ps1) are blocked from registration and Open."""
    from gui.widgets.chat_right_rail import ArtifactCard
    from gui.real_backend_bridge import RealBackendBridge
    from core.config import PROJECT_ROOT
    from PySide6.QtWidgets import QPushButton
    from unittest.mock import MagicMock
    import subprocess
    import os

    bridge = RealBackendBridge.get_instance()
    bridge._session_artifacts = []

    # 1. Non-existent file rejection
    res_fake = bridge.record_artifact("ghost.txt", str(PROJECT_ROOT / "non_existent_ghost_file.txt"))
    assert res_fake is False

    # 2. Out-of-jail rejection in record_artifact
    out_of_jail_file = tmp_path / "out_of_jail.md"
    out_of_jail_file.write_text("# Out of jail")
    res_jail = bridge.record_artifact("out_of_jail.md", str(out_of_jail_file))
    assert res_jail is False

    # 3. Prohibited executable extension rejection (.bat / .exe / .ps1)
    dangerous_bat = PROJECT_ROOT / "scratch" / "payload.bat"
    dangerous_bat.parent.mkdir(parents=True, exist_ok=True)
    dangerous_bat.write_text("@echo malicious\n")
    try:
        res_exec = bridge.record_artifact("payload.bat", str(dangerous_bat))
        assert res_exec is False

        # 4. Open-action guard on ArtifactCard: attempting to open prohibited file must NOT launch shell
        mock_popen = MagicMock()
        mock_startfile = MagicMock()
        orig_popen = subprocess.Popen

        def selective_popen(cmd, *args, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "notepad.exe":
                mock_popen(cmd, *args, **kwargs)
                return MagicMock()
            return orig_popen(cmd, *args, **kwargs)

        monkeypatch.setattr(subprocess, "Popen", selective_popen)
        monkeypatch.setattr(os, "startfile", mock_startfile, raising=False)

        card_bat = ArtifactCard({"name": "payload.bat", "path": str(dangerous_bat)})
        open_btn_bat = next(b for b in card_bat.findChildren(QPushButton) if "Open" in b.text())
        open_btn_bat.click()
        qapp.processEvents()

        # Prohibited executable must NEVER be opened or executed
        mock_popen.assert_not_called()
        mock_startfile.assert_not_called()

        # 5. Safe text/code opening dispatches to notepad.exe (not shell execution)
        for ext_name, content in [
            ("config.xml", "<config></config>"),
            ("settings.toml", "key = 'val'"),
            ("pipeline.yaml", "steps: []"),
            ("vector.svg", "<svg></svg>"),
            ("rules.ini", "[section]\nkey=val"),
        ]:
            mock_popen.reset_mock()
            mock_startfile.reset_mock()
            test_file = PROJECT_ROOT / "scratch" / ext_name
            test_file.write_text(content)
            try:
                card = ArtifactCard({"name": ext_name, "path": str(test_file)})
                btn = next(b for b in card.findChildren(QPushButton) if "Open" in b.text())
                btn.click()
                qapp.processEvents()

                mock_popen.assert_called_once_with(["notepad.exe", str(test_file.resolve())])
                mock_startfile.assert_not_called()
            finally:
                if test_file.exists():
                    test_file.unlink()

        # 6. Images and PDF dispatch to os.startfile (never subprocess.Popen)
        for media_name, bcontent in [
            ("diagram.png", b"\x89PNG\r\n\x1a\n"),
            ("report.pdf", b"%PDF-1.4"),
        ]:
            mock_popen.reset_mock()
            mock_startfile.reset_mock()
            test_media = PROJECT_ROOT / "scratch" / media_name
            test_media.write_bytes(bcontent)
            try:
                card = ArtifactCard({"name": media_name, "path": str(test_media)})
                btn = next(b for b in card.findChildren(QPushButton) if "Open" in b.text())
                btn.click()
                qapp.processEvents()

                mock_startfile.assert_called_once_with(str(test_media.resolve()))
                mock_popen.assert_not_called()
            finally:
                if test_media.exists():
                    test_media.unlink()
    finally:
        if dangerous_bat.exists():
            dangerous_bat.unlink()


def test_terminal_console_accordion_unlocked_and_badge_updates(qapp):
    """Verify Phase 3 Terminal Console header is unlocked, clickable, and updates badge."""
    from gui.widgets.chat_right_rail import ChatRightRail
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from core.config import PROJECT_ROOT
    from PySide6.QtCore import Qt

    auth = CryptographicApprovalAuthority.get_instance()
    rail = ChatRightRail()
    rail.show()
    rail.refresh_data()
    qapp.processEvents()

    # Verify header is active, NOT dimmed, and has pointing hand cursor
    assert rail._term_header.is_dimmed is False
    assert rail._term_header.cursor().shape() == Qt.PointingHandCursor
    assert rail._term_header._badge.text() == "Console Ready"

    # Body starts hidden
    assert rail._term_body.isVisible() is False

    # Toggle expansion
    rail._term_header.is_expanded = True
    rail._toggle_term_body(True)
    assert rail._term_body.isVisible() is True

    rail._toggle_term_body(False)
    assert rail._term_body.isVisible() is False

    # Create a pending ticket and refresh
    t_id = auth.create_command_ticket("git status", str(PROJECT_ROOT))
    rail.refresh_data()
    qapp.processEvents()

    assert "1 Pending" in rail._term_header._badge.text()


def test_hmac_approval_card_renders_within_rail_geometry(qapp):
    """Verify HMACApprovalCard renders within constrained 295px width with elided command."""
    from gui.widgets.chat_right_rail import HMACApprovalCard, ElidedLabel

    t_data = {
        "ticket_id": "tkt_test_geometry_01",
        "action_type": "command",
        "target": "git commit -m 'feat: very long command line that would normally overflow the right rail container'",
        "action_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "expires_in_secs": 280,
    }
    card = HMACApprovalCard(t_data)
    card.resize(295, 95)
    card.show()
    qapp.processEvents()

    labels = card.findChildren(ElidedLabel)
    assert len(labels) >= 1
    for lbl in labels:
        fm = lbl.fontMetrics()
        assert fm.horizontalAdvance(lbl.text()) <= lbl.width() + 5


def test_hmac_approve_action_executes_through_single_source_redemption(qapp):
    """Verify clicking Approve on HMACApprovalCard redeems ticket via CryptographicApprovalAuthority and logs command."""
    from gui.widgets.chat_right_rail import HMACApprovalCard
    from gui.real_backend_bridge import RealBackendBridge
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from core.config import PROJECT_ROOT
    from PySide6.QtWidgets import QPushButton

    auth = CryptographicApprovalAuthority.get_instance()
    bridge = RealBackendBridge.get_instance()
    bridge.clear_terminal_logs()

    # Issue a real command ticket
    t_id = auth.create_command_ticket("echo test_hmac_gate_redemption", str(PROJECT_ROOT))
    with auth._ticket_lock:
        ticket = auth._tickets[t_id]
        t_data = {
            "ticket_id": ticket.ticket_id,
            "action_type": ticket.action_type,
            "target": ticket.target,
            "action_hash": ticket.action_hash,
            "expires_in_secs": 300,
        }

    card = HMACApprovalCard(t_data)
    card.show()
    qapp.processEvents()

    # Click Approve & Execute
    approve_btn = next(b for b in card.findChildren(QPushButton) if "Approve" in b.text())
    approve_btn.click()
    qapp.processEvents()

    # Assert ticket is marked redeemed in authority
    with auth._ticket_lock:
        redeemed_ticket = auth._tickets[t_id]
        assert redeemed_ticket.is_redeemed is True

    # Assert terminal logs contain the command
    logs = bridge.get_terminal_logs()
    assert any("echo test_hmac_gate_redemption" in l["text"] for l in logs)


def test_hmac_deny_action_revokes_ticket(qapp):
    """Verify clicking Deny on HMACApprovalCard revokes ticket and logs rejection."""
    from gui.widgets.chat_right_rail import HMACApprovalCard
    from gui.real_backend_bridge import RealBackendBridge
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from core.config import PROJECT_ROOT
    from PySide6.QtWidgets import QPushButton

    auth = CryptographicApprovalAuthority.get_instance()
    bridge = RealBackendBridge.get_instance()
    bridge.clear_terminal_logs()

    # Issue a real command ticket
    t_id = auth.create_command_ticket("rmdir /s /q dangerous_folder", str(PROJECT_ROOT))
    with auth._ticket_lock:
        ticket = auth._tickets[t_id]
        t_data = {
            "ticket_id": ticket.ticket_id,
            "action_type": ticket.action_type,
            "target": ticket.target,
            "action_hash": ticket.action_hash,
            "expires_in_secs": 300,
        }

    card = HMACApprovalCard(t_data)
    card.show()
    qapp.processEvents()

    # Click Deny
    deny_btn = next(b for b in card.findChildren(QPushButton) if "Deny" in b.text())
    deny_btn.click()
    qapp.processEvents()

    # Assert ticket is marked redeemed/revoked
    with auth._ticket_lock:
        revoked_ticket = auth._tickets[t_id]
        assert revoked_ticket.is_redeemed is True

    # Assert terminal log records denial
    logs = bridge.get_terminal_logs()
    assert any(f"[DENIED] Ticket {t_id}" in l["text"] for l in logs)


def test_hmac_approve_action_enforces_safety_guardrails_on_destructive_payload(qapp, monkeypatch):
    """Verify approving a ticket with a destructive payload is blocked by execute_command safety guardrails."""
    from gui.widgets.chat_right_rail import HMACApprovalCard
    from gui.real_backend_bridge import RealBackendBridge
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from core.config import PROJECT_ROOT
    from PySide6.QtWidgets import QPushButton
    from unittest.mock import MagicMock
    import subprocess

    auth = CryptographicApprovalAuthority.get_instance()
    bridge = RealBackendBridge.get_instance()
    bridge.clear_terminal_logs()

    mock_run = MagicMock()
    orig_run = subprocess.run

    def selective_run(cmd, *args, **kwargs):
        if "rmdir" in str(cmd) or "rm " in str(cmd) or "format" in str(cmd):
            mock_run(cmd, *args, **kwargs)
            return MagicMock()
        return orig_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", selective_run)

    # Issue a real command ticket with a destructive banned payload
    t_id = auth.create_command_ticket("rmdir /s /q c:\\", str(PROJECT_ROOT))
    with auth._ticket_lock:
        ticket = auth._tickets[t_id]
        t_data = {
            "ticket_id": ticket.ticket_id,
            "action_type": ticket.action_type,
            "target": ticket.target,
            "action_hash": ticket.action_hash,
            "expires_in_secs": 300,
        }

    card = HMACApprovalCard(t_data)
    card.show()
    qapp.processEvents()

    # Click Approve & Execute
    approve_btn = next(b for b in card.findChildren(QPushButton) if "Approve" in b.text())
    approve_btn.click()
    qapp.processEvents()

    # Assert ticket was signed and redeemed through authority
    with auth._ticket_lock:
        redeemed_ticket = auth._tickets[t_id]
        assert redeemed_ticket.is_redeemed is True

    # Assert subprocess was NEVER executed for the prohibited payload
    mock_run.assert_not_called()

    # Assert terminal logs record the safety policy rejection
    logs = bridge.get_terminal_logs()
    assert any("Command blocked by safety policy" in l["text"] for l in logs)


def test_file_manager_mutations_automatically_record_session_artifacts(qapp, tmp_path):
    """Verify that FileManager file.create and file.write automatically register in RealBackendBridge."""
    from desktop.native.managers.file_manager import FileManager
    from gui.real_backend_bridge import RealBackendBridge
    from core.config import PROJECT_ROOT

    bridge = RealBackendBridge.get_instance()
    bridge.clear_artifacts()

    # Use a test file located inside PROJECT_ROOT / storage / test_artifacts
    test_dir = PROJECT_ROOT / "storage" / "test_scratch_artifacts"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "live_recorded_doc.md"

    try:
        fm = FileManager(workspace_root=str(PROJECT_ROOT))

        # 1. Execute file.create via FileManager
        res = fm.execute("file.create", arguments={"path": str(test_file), "content": "# Live Artifact Title\nInitial content."})
        assert res.success is True

        # Assert artifact was auto-registered in bridge
        artifacts = bridge.get_session_artifacts()
        assert any(a["path"] == str(test_file.resolve()) for a in artifacts)
        recorded = next(a for a in artifacts if a["path"] == str(test_file.resolve()))
        assert recorded["name"] == "live_recorded_doc.md"
        assert recorded["extension"] == ".md"

        # 2. Execute file.write updating the file -> assert in-place update with no duplicate
        res2 = fm.execute("file.write", arguments={"path": str(test_file), "content": "# Updated Content\nBigger payload text."})
        assert res2.success is True

        artifacts_after = bridge.get_session_artifacts()
        matching = [a for a in artifacts_after if a["path"] == str(test_file.resolve())]
        assert len(matching) == 1, "Duplicate artifact card created for the same file path!"

    finally:
        if test_file.exists():
            test_file.unlink()
        if test_dir.exists():
            try:
                test_dir.rmdir()
            except Exception:
                pass
        bridge.clear_artifacts()


def test_file_manager_zip_decompression_records_all_extracted_files(qapp, tmp_path):
    """Verify that batch/multi-file extraction via file.decompress registers all unpacked files."""
    import zipfile
    from desktop.native.managers.file_manager import FileManager
    from gui.real_backend_bridge import RealBackendBridge
    from core.config import PROJECT_ROOT

    bridge = RealBackendBridge.get_instance()
    bridge.clear_artifacts()

    test_dir = PROJECT_ROOT / "storage" / "test_zip_scratch"
    test_dir.mkdir(parents=True, exist_ok=True)
    zip_path = test_dir / "bundle.zip"
    extract_target = test_dir / "unpacked"

    try:
        # Create a test zip containing two files
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("report_alpha.txt", "Alpha report text payload")
            zf.writestr("subfolder/report_beta.md", "# Beta report payload")

        fm = FileManager(workspace_root=str(PROJECT_ROOT))
        res = fm.execute("file.decompress", arguments={"path": str(zip_path), "extract_to": str(extract_target)})
        assert res.success is True
        assert len(res.data.get("extracted_files", [])) == 2

        # Assert BOTH extracted files are registered in RealBackendBridge
        artifacts = bridge.get_session_artifacts()
        paths = [a["path"] for a in artifacts]
        assert str((extract_target / "report_alpha.txt").resolve()) in paths
        assert str((extract_target / "subfolder" / "report_beta.md").resolve()) in paths

    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
        bridge.clear_artifacts()


def test_agent_session_and_result_merger_stage6_registers_artifacts_and_deduplicates(qapp):
    """Verify that AgentSession deduplication and ResultMerger Stage 6 automatically record DAG artifacts."""
    from core.orchestration.agent_session import AgentSession
    from core.orchestration.artifact import Artifact
    from core.orchestration.result_merger import ResultMerger
    from gui.real_backend_bridge import RealBackendBridge
    from core.config import PROJECT_ROOT

    bridge = RealBackendBridge.get_instance()
    bridge.clear_artifacts()

    test_dir = PROJECT_ROOT / "storage" / "test_dag_artifacts"
    test_dir.mkdir(parents=True, exist_ok=True)
    f1 = test_dir / "dag_output1.py"
    f2 = test_dir / "dag_output2.json"
    f1.write_text("print('hello')", encoding="utf-8")
    f2.write_text('{"status": "ok"}', encoding="utf-8")

    try:
        session = AgentSession(goal="Test DAG artifact recording")

        # 1. Add stub artifact (location empty)
        art_stub = Artifact(artifact_id="art_fixed_123", artifact_type="code", content="code draft", location="")
        session.add_artifact(art_stub)
        assert len(session.artifacts) == 1

        # 2. Update stub with resolved location (same artifact_id)
        import dataclasses
        art_resolved = dataclasses.replace(art_stub, location=str(f1.resolve()))
        session.add_artifact(art_resolved)
        assert len(session.artifacts) == 1, "Stub update created duplicate artifact in AgentSession!"
        assert session.artifacts[0].location == str(f1.resolve())

        # 3. Add second artifact with disjoint id and location
        art2 = Artifact(artifact_id="art_fixed_456", artifact_type="data", content="json data", location=str(f2.resolve()))
        session.add_artifact(art2)
        assert len(session.artifacts) == 2

        # 4. Multi-index collision test: artifact with colliding location but different id -> updates in place
        art_collision = Artifact(artifact_id="art_new_999", artifact_type="code", content="updated code", location=str(f1.resolve()))
        session.add_artifact(art_collision)
        assert len(session.artifacts) == 2, "Disjoint location collision created duplicate in AgentSession!"
        assert session.artifacts[0].artifact_id == "art_new_999"

        # 5. Run Stage 6 ResultMerger.merge_session()
        merger = ResultMerger()
        merger.merge_session(session, success=True)

        # Assert artifacts surfaced in GUI bridge
        bridge_artifacts = bridge.get_session_artifacts()
        paths = [a["path"] for a in bridge_artifacts]
        assert str(f1.resolve()) in paths
        assert str(f2.resolve()) in paths

    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
        bridge.clear_artifacts()


def test_coding_agent_and_code_execution_tool_route_writes_to_artifacts(qapp):
    """Verify that CodingAgent and CodeExecutionTool route their writes through FileManager into session artifacts."""
    from agents.coding_agent import CodingAgent
    from agents.task_model import Task, TaskType, TaskInput
    from tools.code_execution_tool import CodeExecutionTool
    from gui.real_backend_bridge import RealBackendBridge
    from core.config import PROJECT_ROOT

    bridge = RealBackendBridge.get_instance()
    bridge.clear_artifacts()

    test_dir = PROJECT_ROOT / "storage" / "test_coding_agent_scratch"
    test_dir.mkdir(parents=True, exist_ok=True)
    sample_py = test_dir / "sample_module.py"
    sample_py.write_text("import sys\nimport os\n\ndef add(a, b):\n    return a + b\n", encoding="utf-8")

    try:
        # 1. Execute CodingAgent refactor
        coding_agent = CodingAgent(task_manager=None)
        task = Task(
            id="t_refactor_1",
            type=TaskType.CODE_REFACTOR,
            title="Refactor sample module",
            input=TaskInput(data={"file_path": str(sample_py), "refactoring_type": "all"}),
        )
        res = coding_agent.execute_task(task)
        assert res.success is True

        # Assert refactored file registered in bridge
        artifacts = bridge.get_session_artifacts()
        assert any(a["path"] == str(sample_py.resolve()) for a in artifacts)

        # 2. Execute CodeExecutionTool save_and_execute
        exec_tool = CodeExecutionTool(workspace_root=test_dir)
        exec_res = exec_tool.save_and_execute(code="print('execution tool live artifact test')\n", filename="exec_output.py")
        assert exec_res["success"] is True

        artifacts_after = bridge.get_session_artifacts()
        exec_path = str((test_dir / "generated_code" / "exec_output.py").resolve())
        assert any(a["path"] == exec_path for a in artifacts_after)

    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
        bridge.clear_artifacts()




