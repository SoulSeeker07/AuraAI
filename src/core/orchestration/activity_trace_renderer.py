"""
Aura Activity Trace / CLI Execution Trace Renderer
==================================================

Renders collapsible / multi-level activity traces for user interaction:
  - Level 1 (Compact): Clean user summary ("✓ Done — YouTube search completed. Worked for 8.4s ›")
  - Level 2 (Summary): Execution summary ("Worked for 8.4s ▼ | 4 steps · 4 verified · 0 retries")
  - Level 3 (Full Diagnostic): Full auditable execution trace per step (Action, Engine, Target/Query,
    Observation, Verification status, Recovery trace, Duration, Final Result).

Exposes auditable execution facts, not private LLM chain-of-thought.
"""

from __future__ import annotations
from typing import Any


class ActivityTraceRenderer:
    """Renders execution coordination results into 3 levels of CLI activity traces."""

    @classmethod
    def render(cls, result: Any, level: int = 1) -> str:
        """Render activity trace at level 1 (compact), 2 (summary), or 3 (full diagnostic)."""
        if level == 1:
            return cls.render_compact(result)
        elif level == 2:
            return cls.render_summary(result)
        else:
            return cls.render_full(result)

    @classmethod
    def render_compact(cls, result: Any) -> str:
        goal = getattr(result, "goal", "") or (result.get("goal") if isinstance(result, dict) else "execution")
        success = getattr(result, "success", False) if not isinstance(result, dict) else result.get("success", False)
        duration = getattr(result, "total_time", 0.0) if not isinstance(result, dict) else result.get("total_time", 0.0)

        status_symbol = "✓" if success else "✗"
        summary_text = "completed successfully" if success else "stopped/failed"

        return (
            f"Aura\n"
            f"────────────────────────────────────────────\n\n"
            f"You: {goal}\n\n"
            f"Aura: {status_symbol} Done — {goal} {summary_text}.\n\n"
            f"  Worked for {duration:.1f}s  ›"
        )

    @classmethod
    def render_summary(cls, result: Any) -> str:
        goal = getattr(result, "goal", "") or (result.get("goal") if isinstance(result, dict) else "execution")
        success = getattr(result, "success", False) if not isinstance(result, dict) else result.get("success", False)
        duration = getattr(result, "total_time", 0.0) if not isinstance(result, dict) else result.get("total_time", 0.0)
        step_results = getattr(result, "step_results", []) if not isinstance(result, dict) else result.get("step_results", [])

        total_steps = len(step_results)
        verified_count = 0
        retry_count = 0
        engines_used = set()

        for s in step_results:
            engine = getattr(s, "engine", "") if not isinstance(s, dict) else s.get("engine", "")
            if engine:
                engines_used.add(engine.capitalize())
            v_rep = getattr(s, "data", {}).get("verification_report") if not isinstance(s, dict) else s.get("data", {}).get("verification_report")
            if v_rep and (v_rep.get("passed") if isinstance(v_rep, dict) else getattr(v_rep, "passed", False)):
                verified_count += 1
            rec_trace = getattr(s, "data", {}).get("recovery_trace") if not isinstance(s, dict) else s.get("data", {}).get("recovery_trace")
            if rec_trace:
                retry_count += 1

        status_symbol = "✓" if success else "✗"
        engines_str = ", ".join(sorted(engines_used)) or "Core"

        goal_v = getattr(result, "data", {}).get("goal_verification") if not isinstance(result, dict) else result.get("data", {}).get("goal_verification")
        g_status = " ✓ GOAL VERIFIED PASS" if (goal_v and (goal_v.get("passed") if isinstance(goal_v, dict) else getattr(goal_v, "passed", False))) else ""

        lines = [
            "Aura",
            "────────────────────────────────────────────",
            "",
            f"You: {goal}",
            "",
            f"Aura: {status_symbol} Done — {goal}.",
            "",
            f"  Worked for {duration:.1f}s  ▼",
            "",
            f"  ├─ {total_steps} steps · {verified_count} verified · {retry_count} retries",
            f"  ├─ Engines: {engines_str}",
            f"  └─ Status: {'ALL STEPS VERIFIED PASS' if success else 'STEP FAILURE ENCOUNTERED'}{g_status}",
        ]
        return "\n".join(lines)

    @classmethod
    def render_full(cls, result: Any) -> str:
        goal = getattr(result, "goal", "") or (result.get("goal") if isinstance(result, dict) else "execution")
        success = getattr(result, "success", False) if not isinstance(result, dict) else result.get("success", False)
        duration = getattr(result, "total_time", 0.0) if not isinstance(result, dict) else result.get("total_time", 0.0)
        step_results = getattr(result, "step_results", []) if not isinstance(result, dict) else result.get("step_results", [])
        data_res = getattr(result, "data", {}) if not isinstance(result, dict) else result.get("data", {})
        goal_v = data_res.get("goal_verification")

        lines = [
            "==========================================================================",
            "                      AURA EXECUTION ACTIVITY TRACE",
            "==========================================================================",
            f"Goal        : {goal}",
            f"Status      : {'SUCCESS' if success else 'FAILED/HALTED'}",
            f"Total Time  : {duration:.2f}s",
            f"Total Steps : {len(step_results)}",
        ]

        if goal_v:
            g_passed = goal_v.get("passed") if isinstance(goal_v, dict) else getattr(goal_v, "passed", False)
            g_fail_type = goal_v.get("failure_type") if isinstance(goal_v, dict) else getattr(goal_v, "failure_type", "none")
            lines.append(f"Goal Verify : {'✓ VERIFIED PASS' if g_passed else f'✗ FAILED ({g_fail_type})'}")

        lines.append("--------------------------------------------------------------------------")

        for i, s in enumerate(step_results, 1):
            engine = getattr(s, "engine", "") if not isinstance(s, dict) else s.get("engine", "")
            action = getattr(s, "action", "") if not isinstance(s, dict) else s.get("action", "")
            s_success = getattr(s, "success", False) if not isinstance(s, dict) else s.get("success", False)
            s_time = getattr(s, "execution_time", 0.0) if not isinstance(s, dict) else s.get("execution_time", 0.0)
            data = getattr(s, "data", {}) if not isinstance(s, dict) else s.get("data", {})

            obs = data.get("observation", {})
            v_rep = data.get("verification_report", {})
            rec_trace = data.get("recovery_trace", {})

            state = obs.get("state", "window_active" if s_success else "failed")
            evidence = obs.get("evidence", {})
            text_content = evidence.get("text_content") or evidence.get("title") or evidence.get("url") or ""

            v_passed = v_rep.get("passed") if isinstance(v_rep, dict) else getattr(v_rep, "passed", s_success)
            v_evidence = v_rep.get("evidence", []) if isinstance(v_rep, dict) else getattr(v_rep, "evidence", [])

            lines.append(f"\n[Step {i}] {engine.capitalize()} · {action}")
            lines.append(f"  ├─ Action       : {action}")
            lines.append(f"  ├─ Status       : {'✓ PASS' if s_success else '✗ FAIL'}")
            lines.append(f"  ├─ State        : {state}")
            if text_content:
                clean_text = str(text_content).replace("\n", "\\n")
                if len(clean_text) > 60:
                    clean_text = clean_text[:57] + "..."
                lines.append(f"  ├─ Observed     : {clean_text}")
            if v_evidence:
                lines.append(f"  ├─ Verification : {'✓ PASS' if v_passed else '✗ FAIL'} ({v_evidence[0]})")
            else:
                lines.append(f"  ├─ Verification : {'✓ PASS' if v_passed else '✗ FAIL'}")

            if rec_trace:
                lines.append("  ├─ Recovery     :")
                lines.append(f"  │   ├─ Primary  : {rec_trace.get('primary_target')}")
                lines.append(f"  │   ├─ Alt Target: {rec_trace.get('alternative_target')}")
                lines.append(f"  │   └─ Outcome  : {rec_trace.get('recovery_status')}")

            lines.append(f"  └─ Duration     : {s_time:.2f}s")

        lines.append("\n==========================================================================")
        return "\n".join(lines)
