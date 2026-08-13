"""
Unit tests for ActivityTraceRenderer
Location: tests/unit/test_activity_trace_renderer.py
"""

from core.orchestration.activity_trace_renderer import ActivityTraceRenderer
from brain.execution_coordinator import CoordinationResult, StepResult


def test_activity_trace_renderer_levels():
    s1 = StepResult(
        step_index=0,
        engine="desktop",
        action="app_open",
        success=True,
        execution_time=1.2,
        data={
            "observation": {"state": "window_visible", "evidence": {"title": "Untitled - Notepad"}},
            "verification_report": {"passed": True, "evidence": ["Window title matched"]},
        },
    )
    s2 = StepResult(
        step_index=1,
        engine="browser",
        action="browser.navigate",
        success=True,
        execution_time=2.3,
        data={
            "observation": {"state": "page_loaded", "evidence": {"url": "https://www.google.com"}},
            "verification_report": {"passed": True, "evidence": ["URL matched"]},
            "recovery_trace": {"primary_target": "bad_url", "alternative_target": "https://www.google.com", "recovery_status": "RECOVERED_SUCCESS"},
        },
    )

    coord_res = CoordinationResult(
        goal="Open Notepad and navigate to Google",
        success=True,
        step_results=[s1, s2],
        total_time=3.5,
    )

    # Test Level 1
    t1 = ActivityTraceRenderer.render(coord_res, level=1)
    assert "Aura:" in t1
    assert "Worked for 3.5s" in t1

    # Test Level 2
    t2 = ActivityTraceRenderer.render(coord_res, level=2)
    assert "2 steps · 2 verified · 1 retries" in t2
    assert "Engines: Browser, Desktop" in t2

    # Test Level 3
    t3 = ActivityTraceRenderer.render(coord_res, level=3)
    assert "AURA EXECUTION ACTIVITY TRACE" in t3
    assert "Desktop · app_open" in t3
    assert "Browser · browser.navigate" in t3
    assert "RECOVERED_SUCCESS" in t3


def test_coordination_result_render_trace_method():
    s1 = StepResult(step_index=0, engine="desktop", action="app_open", success=True, execution_time=0.5)
    coord_res = CoordinationResult(goal="Test goal", success=True, step_results=[s1], total_time=0.5)

    trace = coord_res.render_trace(level=1)
    assert "Worked for 0.5s" in trace
