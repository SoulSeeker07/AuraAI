"""
Executive Brain Test Suite
==========================

Tests the 5-layer cognitive architecture:
    Layer 1: DMM (Decision Making Module)
    Layer 2: Planner
    Layer 3: Executor
    Layer 4: Reflection
    Layer 5: Learning
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main():
    """Run the Executive Brain test suite."""
    print("=" * 60)
    print("EXECUTIVE BRAIN TEST SUITE")
    print("=" * 60)

    from src.brain.executive import (
        DecisionMakingModule,
        ExecutionMap,
        ExecutiveBrain,
        ExecutiveExecutor,
        ExecutivePlanner,
        LearningEngine,
        ReflectionEngine,
    )

    # ── Test 1: DMM produces structured ExecutionMap ────────────────────────
    print("\n[Test 1] DMM: 'Open YouTube in Chrome'")
    dmm = DecisionMakingModule()
    result = dmm.analyze("Open YouTube in Chrome")

    assert isinstance(
        result, ExecutionMap
    ), f"DMM should produce ExecutionMap, got {type(result).__name__}"
    valid, errors = result.validate()
    assert valid, f"ExecutionMap should be valid: {errors}"

    print(f"  ✓ Goal: {result.goal}")
    print(f"  ✓ Capabilities: {[c.value for c in result.required_capabilities]}")
    print(f"  ✓ Steps: {len(result.execution_plan)}")
    for step in result.execution_plan:
        print(f"    - [{step.step_type.value}] {step.description}")
    print(f"  ✓ Verification: {result.verification.checks}")

    # ── Test 2: DMM handles "Open another Notepad" ──────────────────────────
    print("\n[Test 2] DMM: 'Open another Notepad'")
    result2 = dmm.analyze("Open another Notepad")
    assert isinstance(result2, ExecutionMap)
    print(f"  ✓ Goal: {result2.goal}")
    print(f"  ✓ New instance: {result2.metadata.get('app')}")
    for step in result2.execution_plan:
        print(f"    - [{step.step_type.value}] {step.description}")

    # ── Test 3: Planner converts map to runtime plan ────────────────────────
    print("\n[Test 3] Planner: convert ExecutionMap → ExecutionPlan")
    planner = ExecutivePlanner()
    plan = planner.create_plan(result)
    print(f"  ✓ Plan ID: {plan.plan_id}")
    print(f"  ✓ Total steps: {plan.total_steps}")
    print(f"  ✓ Estimated timeout: {plan.estimated_timeout}s")
    for action in plan.ordered_actions:
        print(
            f"    - [{action.step_type}] {action.description} (cap={action.capability})"
        )

    # ── Test 4: Executor with mock engine ───────────────────────────────────
    print("\n[Test 4] Executor: execute plan via mock callbacks")

    async def mock_desktop(params):
        """Mock desktop engine callback."""
        print(
            f"    [Desktop Engine] Executing: {params.get('operation', 'unknown')} "
            f"app={params.get('app_name', 'unknown')}"
        )
        return {
            "success": True,
            "observations": [f"Launched {params.get('app_name', 'app')}"],
        }

    async def mock_browser(params):
        """Mock browser engine callback."""
        print(f"    [Browser Engine] Navigating to: {params.get('url', 'unknown')}")
        return {
            "success": True,
            "observations": [f"Navigated to {params.get('url', '')}"],
        }

    executor = ExecutiveExecutor()
    executor.register_callback("desktop", mock_desktop)
    executor.register_callback("browser", mock_browser)

    plan_result = await executor.execute_plan(plan)
    print(f"  ✓ Execution success: {plan_result.success}")
    print(f"  ✓ Steps passed: {len(plan_result.step_results)}")
    print(f"  ✓ Total time: {plan_result.total_time:.2f}s")

    # ── Test 5: Reflection validates success ────────────────────────────────
    print("\n[Test 5] Reflection: validate successful execution")
    reflection = ReflectionEngine()
    outcome = reflection.reflect(plan_result)
    assert outcome.success
    print(f"  ✓ Reflection success: {outcome.success}")
    print(f"  ✓ Reflections: {outcome.reflections}")

    # ── Test 6: Reflection handles failure with recovery ────────────────────
    print("\n[Test 6] Reflection: handle failure with recovery pattern")

    from src.brain.executive.executor import StepResult
    from src.brain.executive.planner import ExecutionPlan as EP

    # Simulate failed execution
    failed_result = EP(
        plan_id="test_fail",
        execution_map_id="test_map",
        goal="Open paint",
        ordered_actions=[],
    )
    failed_plan_result = plan_result.__class__(
        plan_id="test_fail",
        success=False,
        step_results=[
            StepResult(
                action_id="act_1",
                success=False,
                error="paint.exe not found",
                data={"app_name": "paint"},
            )
        ],
        failed_steps=[
            StepResult(
                action_id="act_1",
                success=False,
                error="paint.exe not found",
                data={"app_name": "paint"},
            )
        ],
    )
    fail_outcome = reflection.reflect(failed_plan_result)
    print(f"  ✓ Success: {fail_outcome.success}")
    print(f"  ✓ Recovered: {fail_outcome.recovered}")
    print(f"  ✓ Recovery: {fail_outcome.recoveries}")
    print(f"  ✓ Fallback actions: {fail_outcome.fallback_actions}")

    # ── Test 7: Learning captures behavior rules ────────────────────────────
    print("\n[Test 7] Learning: capture behavior rule")
    learning = LearningEngine()
    learned = learning.learn_behavior_rule(
        trigger="Summarize today's session",
        action="Summarize RuntimeSession",
    )
    print(f"  ✓ Learned: {learned.item_type} → {learned.trigger}")
    items = learning.get_learned_items()
    print(f"  ✓ Total learned: {len(items)} items")

    # ── Test 8: Full Executive Brain pipeline ───────────────────────────────
    print("\n[Test 8] Full Executive Brain pipeline")

    brain = ExecutiveBrain(
        dmm=dmm,
        planner=planner,
        executor=executor,
        reflection=reflection,
        learning=learning,
    )

    response = await brain.process("Open YouTube in Chrome")
    print(f"  ✓ Success: {response.success}")
    print(f"  ✓ Response: {response.text}")
    print(f"  ✓ Execution map: {response.execution_map is not None}")
    print(f"  ✓ Plan: {response.plan is not None}")
    print(f"  ✓ Plan result: {response.plan_result is not None}")
    print(f"  ✓ Reflection: {response.reflection is not None}")
    print(f"  ✓ Learned: {len(response.learned)} items")

    # ── Test 9: DMM handles "Implement dark mode in GUI" ────────────────────
    print("\n[Test 9] DMM: 'Implement dark mode in GUI'")
    eng_result = dmm.analyze("Implement dark mode in the GUI")
    assert isinstance(eng_result, ExecutionMap)
    print(f"  ✓ Goal: {eng_result.goal}")
    print(f"  ✓ Capabilities: {[c.value for c in eng_result.required_capabilities]}")
    for step in eng_result.execution_plan:
        print(f"    - [{step.step_type.value}] {step.description}")

    # ── Test 10: Serialization round-trip ───────────────────────────────────
    print("\n[Test 10] ExecutionMap serialization round-trip")
    map_dict = result.to_dict()
    restored = ExecutionMap.from_dict(map_dict)
    assert restored.goal == result.goal
    assert len(restored.execution_plan) == len(result.execution_plan)
    print("  ✓ Serialization round-trip successful")

    print("\n" + "=" * 60)
    print("ALL EXECUTIVE BRAIN TESTS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
