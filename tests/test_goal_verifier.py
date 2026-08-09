"""
Tests for M19.1 Goal Verifier Engine
Location: tests/test_goal_verifier.py
"""

import pytest
from src.brain.goal_verifier import GoalVerifier
from src.brain.execution_coordinator import CoordinationResult, StepResult
from src.core.orchestration.observation_models import FailureType


def test_goal_verifier_success():
    verifier = GoalVerifier()
    step1 = StepResult(
        step_index=0,
        engine="browser",
        action="navigate",
        success=True,
        observations=["Navigated to https://youtube.com"],
        data={
            "observation": {
                "state": "page_loaded",
                "evidence": {"url": "https://youtube.com", "title": "YouTube"},
            },
            "verification_report": {"passed": True},
        },
    )
    step2 = StepResult(
        step_index=1,
        engine="browser",
        action="search",
        success=True,
        observations=["Searched for Python tutorials"],
        data={
            "observation": {
                "state": "search_results",
                "evidence": {"text_content": "18 candidates found"},
            },
            "verification_report": {"passed": True},
        },
    )
    coord_res = CoordinationResult(
        goal="Search YouTube for Python tutorials",
        success=True,
        step_results=[step1, step2],
        failed_steps=[],
        total_time=1.5,
    )

    report = verifier.verify_goal("Search YouTube for Python tutorials", coord_res)
    assert report.passed is True
    assert report.failure_type == FailureType.NONE.value
    assert report.step_count == 2
    assert report.verified_steps == 2


def test_goal_verifier_login_false_positive_prevention():
    verifier = GoalVerifier()
    step1 = StepResult(
        step_index=0,
        engine="browser",
        action="click_submit",
        success=True,
        observations=["Clicked submit button"],
        data={
            "observation": {
                "state": "form_submitted",
                "evidence": {
                    "url": "https://facebook.com/login",
                    "title": "Log in to Facebook",
                },
            },
            "verification_report": {"passed": True},
        },
    )
    coord_res = CoordinationResult(
        goal="Log into Facebook",
        success=True,
        step_results=[step1],
        failed_steps=[],
        total_time=0.8,
    )

    report = verifier.verify_goal("Log into Facebook", coord_res)
    assert report.passed is False
    assert report.failure_type == FailureType.STATE_MISMATCH.value
    assert any("remains on login/signin prompt" in ev for ev in report.evidence)


def test_goal_verifier_step_failure_classification():
    verifier = GoalVerifier()
    failed_step = StepResult(
        step_index=0,
        engine="browser",
        action="click_button",
        success=False,
        error="Element input#search_input not found",
    )
    coord_res = CoordinationResult(
        goal="Search for item",
        success=False,
        step_results=[failed_step],
        failed_steps=[failed_step],
        total_time=0.4,
    )

    report = verifier.verify_goal("Search for item", coord_res)
    assert report.passed is False
    assert report.failure_type == FailureType.ELEMENT_NOT_FOUND.value
