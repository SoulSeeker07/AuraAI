"""
M19.1 Goal Verifier Engine
==========================
Location: src/brain/goal_verifier.py

Mandatory gate evaluating physical state changes, evidence, and independent observations
to distinguish step interaction (e.g. "Clicked submit button") from true end-to-end
goal achievement (e.g. "Account created" or "Logged in").
"""

from __future__ import annotations

import logging
from typing import Any

from core.orchestration.observation_models import FailureType
from brain.verification import GoalVerificationReport
from brain.execution_coordinator import CoordinationResult, StepResult

logger = logging.getLogger(__name__)


class GoalVerifier:
    """
    Evaluates end-to-end goal fulfillment post-execution.
    
    Ensures that step completion or element interaction is not false-positively
    classified as goal success.
    """

    def verify_goal(
        self,
        goal: str,
        coordination_result: CoordinationResult,
        world_state: dict[str, Any] | None = None,
    ) -> GoalVerificationReport:
        """
        Verify if the end-to-end goal was actually accomplished.

        Args:
            goal: The overall user goal string.
            coordination_result: The CoordinationResult from ExecutionCoordinator.
            world_state: Optional snapshot of environment state.

        Returns:
            GoalVerificationReport with passed flag, evidence, and failure_type.
        """
        goal_lower = goal.lower()
        step_results = coordination_result.step_results
        failed_steps = coordination_result.failed_steps
        step_count = len(step_results)

        evidence: list[str] = []
        observed_state: dict[str, Any] = world_state or {}

        # 1. Step-level failure check
        if failed_steps:
            last_failed = failed_steps[-1]
            failure_type = self._classify_step_failure(last_failed)
            evidence.append(f"Step {last_failed.step_index + 1} failed: {last_failed.error or 'Verification failed'}")
            return GoalVerificationReport(
                goal=goal,
                passed=False,
                failure_type=failure_type.value,
                evidence=evidence,
                observed_state=observed_state,
                step_count=step_count,
                verified_steps=step_count - len(failed_steps),
            )

        if not step_results:
            return GoalVerificationReport(
                goal=goal,
                passed=False,
                failure_type=FailureType.GOAL_UNFULFILLED.value,
                evidence=["No execution steps were performed."],
                observed_state=observed_state,
                step_count=0,
                verified_steps=0,
            )

        # 2. Extract observations and state evidence across all steps
        verified_steps_count = 0
        for s in step_results:
            data = s.data if isinstance(s.data, dict) else {}
            v_rep = data.get("verification_report") or {}
            if isinstance(v_rep, dict) and v_rep.get("passed", False):
                verified_steps_count += 1
            elif getattr(v_rep, "passed", False):
                verified_steps_count += 1
            elif s.success:
                verified_steps_count += 1

            # Collect evidence strings
            obs = data.get("observation", {})
            if isinstance(obs, dict):
                state = obs.get("state")
                if state:
                    observed_state[f"step_{s.step_index + 1}_state"] = state
                ev = obs.get("evidence", {})
                if isinstance(ev, dict):
                    url = ev.get("url")
                    title = ev.get("title")
                    text = ev.get("text_content")
                    if url:
                        evidence.append(f"Observed URL: {url}")
                        observed_state["url"] = url
                    if title:
                        evidence.append(f"Observed Title: {title}")
                        observed_state["title"] = title
                    if text:
                        evidence.append(f"Observed Content: {str(text)[:80]}")

        # 3. Intent-Specific End-to-End Goal Verification Gates

        # A. Authentication / Login goals ("log in", "sign in")
        if any(kw in goal_lower for kw in ["log in", "login", "sign in", "signin"]):
            url = str(observed_state.get("url", "")).lower()
            title = str(observed_state.get("title", "")).lower()
            evidence_str = " ".join(evidence).lower()

            # False positive prevention: If current URL/title still contains login form indicators
            if "login" in url or "signin" in url or "sign in" in title or "log in" in title:
                # Check if authenticated state was verified
                auth_verified = any("authenticated" in e.lower() or "feed" in e.lower() or "dashboard" in e.lower() for e in [url, title, evidence_str])
                if not auth_verified:
                    return GoalVerificationReport(
                        goal=goal,
                        passed=False,
                        failure_type=FailureType.STATE_MISMATCH.value,
                        evidence=evidence + ["Action completed, but page remains on login/signin prompt."],
                        observed_state=observed_state,
                        step_count=step_count,
                        verified_steps=verified_steps_count,
                    )

        # B. Search / Navigation goals ("search", "find", "open")
        elif "search" in goal_lower or "find" in goal_lower:
            has_search_results = any(
                "result" in ev.lower() or "search" in ev.lower() or "candidate" in ev.lower()
                for ev in evidence
            )
            if not has_search_results:
                evidence.append("Search action triggered, but search results were not verified.")

        # C. Media Playback goals ("play", "watch")
        elif "play" in goal_lower or "watch" in goal_lower:
            playback_verified = any("playing" in ev.lower() or "watch" in ev.lower() for ev in evidence)
            if not playback_verified:
                evidence.append("Media action executed, but playback state not explicitly observed.")

        # 4. Final Goal Verification Decision
        goal_passed = verified_steps_count == step_count and coordination_result.success

        return GoalVerificationReport(
            goal=goal,
            passed=goal_passed,
            failure_type=FailureType.NONE.value if goal_passed else FailureType.GOAL_UNFULFILLED.value,
            evidence=evidence if evidence else ["All steps verified successfully."],
            observed_state=observed_state,
            step_count=step_count,
            verified_steps=verified_steps_count,
        )

    def _classify_step_failure(self, step: StepResult) -> FailureType:
        """Classify step-level failure into specific FailureType taxonomy."""
        error = (step.error or "").lower()
        data = step.data if isinstance(step.data, dict) else {}
        v_rep = data.get("verification_report", {})
        if isinstance(v_rep, dict):
            f_type = v_rep.get("failure_type")
            if f_type and f_type != FailureType.NONE.value:
                try:
                    return FailureType(f_type)
                except ValueError:
                    pass

        if "timeout" in error or "timed out" in error:
            return FailureType.TIMEOUT
        if "not found" in error or "selector" in error or "element" in error:
            return FailureType.ELEMENT_NOT_FOUND
        if "state" in error or "mismatch" in error:
            return FailureType.STATE_MISMATCH
        if "verification" in error:
            return FailureType.VERIFICATION_FAILURE

        return FailureType.EXECUTION_FAILURE


__all__ = ["GoalVerifier"]
