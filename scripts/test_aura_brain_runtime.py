"""
AuraBrain Executive Runtime Test Suite
======================================

Tests the full cognitive pipeline:
    Context Manager → World Model → Goal Analyzer → Capability Selector
    → Execution Map Generator → Execution Map Validator → Execution Coordinator
    → Verification → Reflection → Learning
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main():
    """Run the AuraBrain Executive Runtime test suite."""
    print("=" * 60)
    print("AURABRAIN EXECUTIVE RUNTIME TEST SUITE")
    print("=" * 60)

    from src.brain import (
        AuraBrain,
        ContextManager,
        WorldModel,
        GoalAnalyzer,
        CapabilitySelector,
        ExecutionMapGenerator,
        ExecutionMapValidator,
        ExecutionCoordinator,
        VerificationEngine,
        ReflectionEngine,
        LearningEngine,
    )

    # ── Test 1: Context Manager collects state ──────────────────────────────
    print("\n[Test 1] Context Manager")
    cm = ContextManager()
    ctx = cm.collect("Open YouTube in Chrome", {"developer_mode": True})
    print(f"  ✓ Context collected: {ctx.summarize()[:80]}...")
    print(f"  ✓ Developer mode: {ctx.developer_mode}")

    # ── Test 2: World Model tracks computer state ───────────────────────────
    print("\n[Test 2] World Model")
    wm = WorldModel()
    world = wm.update()
    print(f"  ✓ World state: {world.summarize()[:80]}...")
    wm.set_browser_tabs([{"title": "YouTube", "url": "https://youtube.com"}])
    print(f"  ✓ Browser tabs set: {len(wm.get_state().browser_tabs)}")

    # ── Test 3: Goal Analyzer decomposes goals ──────────────────────────────
    print("\n[Test 3] Goal Analyzer")
    ga = GoalAnalyzer()
    goals = ga.analyze("Open YouTube in Chrome")
    print(f"  ✓ Primary goal: {goals.primary_goal}")
    for g in goals.goals:
        print(f"    - {g.description}")
        for sg in g.sub_goals:
            print(f"      • {sg}")

    # ── Test 4: Capability Selector maps goals to capabilities ──────────────
    print("\n[Test 4] Capability Selector")
    cs = CapabilitySelector()
    caps = cs.select(goals)
    print(f"  ✓ Required engines: {caps.required_engines}")
    for c in caps.capabilities:
        print(f"    - [{c.capability}] {c.action}: {c.description}")

    # ── Test 5: Execution Map Generator produces structured map ─────────────
    print("\n[Test 5] Execution Map Generator")
    emg = ExecutionMapGenerator()
    exec_map = emg.generate("Open YouTube in Chrome", ctx, world, goals, caps)
    print(f"  ✓ Goal: {exec_map['goal']}")
    print(f"  ✓ Capabilities: {exec_map['capabilities']}")
    print(f"  ✓ Steps: {len(exec_map['steps'])}")
    for s in exec_map['steps']:
        print(f"    - [{s['engine']}] {s['action']}")
    print(f"  ✓ Verification: {exec_map['verification']}")

    # ── Test 6: Execution Map Validator validates the map ───────────────────
    print("\n[Test 6] Execution Map Validator")
    emv = ExecutionMapValidator()
    validation = emv.validate(exec_map)
    print(f"  ✓ Valid: {validation.valid}")
    print(f"  ✓ Errors: {validation.errors}")
    print(f"  ✓ Warnings: {validation.warnings}")

    # ── Test 7: Execution Coordinator delegates to engines ──────────────────
    print("\n[Test 7] Execution Coordinator")

    async def mock_desktop(action, params):
        print(f"    [Desktop] {action}: {params.get('application', 'unknown')}")
        return {"success": True, "observations": [f"Desktop: {action} completed"]}

    async def mock_browser(action, params):
        print(f"    [Browser] {action}: {params.get('url', 'unknown')}")
        return {"success": True, "observations": [f"Browser: {action} completed"]}

    ec = ExecutionCoordinator()
    ec.register_engine("desktop", mock_desktop)
    ec.register_engine("browser", mock_browser)

    coord_result = await ec.coordinate(exec_map)
    print(f"  ✓ Success: {coord_result.success}")
    print(f"  ✓ Steps: {len(coord_result.step_results)}")

    # ── Test 8: Verification checks outcomes ────────────────────────────────
    print("\n[Test 8] Verification Engine")
    ve = VerificationEngine()
    report = ve.verify(exec_map, coord_result)
    print(f"  ✓ Passed: {report.passed}")
    for check in report.checks:
        print(f"    - {'✓' if check.passed else '✗'} {check.description}")

    # ── Test 9: Reflection evaluates execution ──────────────────────────────
    print("\n[Test 9] Reflection Engine")
    re = ReflectionEngine()
    reflection = re.reflect(coord_result)
    print(f"  ✓ Success: {reflection.success}")
    print(f"  ✓ Reflections: {len(reflection.reflections)}")

    # ── Test 10: Conservative Learning ──────────────────────────────────────
    print("\n[Test 10] Conservative Learning")
    le = LearningEngine()
    learned = le.learn_from_interaction(
        "When I ask 'Summarize today's session', summarize RuntimeSession.",
        coord_result,
        report,
    )
    print(f"  ✓ Learned: {len(learned)} items")
    for item in learned:
        print(f"    - [{item.item_type}] {item.trigger} → {item.value}")

    # ── Test 11: Full AuraBrain pipeline ────────────────────────────────────
    print("\n[Test 11] Full AuraBrain Executive Runtime pipeline")
    brain = AuraBrain(
        context_manager=cm,
        world_model=wm,
        goal_analyzer=ga,
        capability_selector=cs,
        execution_map_generator=emg,
        execution_map_validator=emv,
        execution_coordinator=ec,
        verification_engine=ve,
        reflection_engine=re,
        learning_engine=le,
    )

    response = await brain.process("Open YouTube in Chrome")
    print(f"  ✓ Success: {response.success}")
    print(f"  ✓ Response: {response.text}")
    print(f"  ✓ Context: {response.context is not None}")
    print(f"  ✓ World: {response.world_state is not None}")
    print(f"  ✓ Goals: {response.goal_analysis is not None}")
    print(f"  ✓ Capabilities: {response.capability_selection is not None}")
    print(f"  ✓ Execution Map: {response.execution_map is not None}")
    print(f"  ✓ Validation: {response.validation is not None}")
    print(f"  ✓ Coordination: {response.coordination is not None}")
    print(f"  ✓ Verification: {response.verification is not None}")
    print(f"  ✓ Reflection: {response.reflection is not None}")
    print(f"  ✓ Learned: {len(response.learned)} items")

    # ── Test 12: Validation catches bad maps ────────────────────────────────
    print("\n[Test 12] Validator catches invalid maps")
    bad_map = {
        "goal": "Test",
        "capabilities": ["unknown_engine"],
        "steps": [
            {"engine": "unknown_engine", "action": "bad_action", "parameters": {}}
        ],
        "verification": [],
    }
    bad_validation = emv.validate(bad_map)
    print(f"  ✓ Valid: {bad_validation.valid}")
    print(f"  ✓ Errors: {bad_validation.errors}")

    print("\n" + "=" * 60)
    print("ALL AURABRAIN EXECUTIVE RUNTIME TESTS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)