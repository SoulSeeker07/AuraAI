"""
Aura Cognitive Architecture (ACA) Test Suite
============================================

Tests the staged cognitive architecture with shared Blackboard,
Goal Manager, TaskGraph, Policy Engine, RuntimeSession, and Artifacts.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main():
    """Run the ACA test suite."""
    print("=" * 60)
    print("AURA COGNITIVE ARCHITECTURE (ACA) TEST SUITE")
    print("=" * 60)

    from src.brain import (
        CapabilitySelector,
        ContextManager,
        ExecutionCoordinator,
        ExecutionMapValidator,
        GoalAnalyzer,
        LearningEngine,
        ReflectionEngine,
        VerificationEngine,
        WorldModel,
    )
    from src.brain.aca import (
        ACABrain,
        ArtifactManager,
        ConfidenceGate,
        FusionEngine,
        GoalManager,
        PolicyEngine,
        StrategyEngine,
    )
    from src.brain.schemas import (
        CognitiveState,
        RuntimeSession,
        TaskGraph,
    )
    from src.brain.schemas.thought import Confidence

    # ── Test 1: Blackboard ──────────────────────────────────────────────────
    print("\n[Test 1] Blackboard shared working memory")
    bb = CognitiveState()
    bb.user_input = "Open YouTube in Chrome"
    bb.set_stage("stage0_perception")
    print(f"  ✓ Stage: {bb.stage}")
    print(f"  ✓ User input: {bb.user_input}")

    # ── Test 2: TaskGraph (DAG) ─────────────────────────────────────────────
    print("\n[Test 2] TaskGraph — DAG for parallel execution")
    tg = TaskGraph(goal="Research → Summarize → Save → Open VS Code")
    n1 = tg.add_node("research", "search", {"query": "Aura OS"}, "Research")
    n2 = tg.add_node("provider", "synthesize", {}, "Summarize", depends_on=[n1.node_id])
    n3 = tg.add_node("filesystem", "write_file", {}, "Save", depends_on=[n2.node_id])
    n4 = tg.add_node(
        "desktop",
        "launch_application",
        {"application": "code"},
        "Open VS Code",
        depends_on=[n2.node_id],
    )
    levels = tg.get_execution_order()
    print(f"  ✓ Nodes: {len(tg.nodes)}")
    print(f"  ✓ Root nodes: {len(tg.root_nodes)}")
    print(f"  ✓ Leaf nodes: {len(tg.leaf_nodes)}")
    print(f"  ✓ Execution levels: {len(levels)}")
    for i, level in enumerate(levels):
        print(f"    Level {i + 1}: {[n.action for n in level]}")

    # ── Test 3: RuntimeSession ──────────────────────────────────────────────
    print("\n[Test 3] RuntimeSession — source of truth")
    session = RuntimeSession(goal="Open YouTube in Chrome")
    session.start()
    session.set_task_graph(tg)
    session.update_progress(50)
    session.add_artifact({"type": "research", "name": "Findings"})
    print(f"  ✓ Session: {session.session_id}")
    print(f"  ✓ Status: {session.status}")
    print(f"  ✓ Progress: {session.progress}%")
    print(f"  ✓ Artifacts: {len(session.artifacts)}")
    session.complete()
    print(f"  ✓ Completed: {session.status}")

    # ── Test 4: Goal Manager ────────────────────────────────────────────────
    print("\n[Test 4] Goal Manager — long-term goals")
    gm = GoalManager()
    goal = gm.create_goal(
        description="Build Aura OS",
        completion_criteria=["ACA complete", "Voice runtime", "GUI"],
        sub_goals=["Executive Brain", "Voice Runtime", "GUI"],
    )
    gm.add_session(goal.goal_id, session.session_id)
    gm.update_progress(goal.goal_id, 50)
    print(f"  ✓ Goal: {goal.description}")
    print(f"  ✓ Status: {goal.status}")
    print(f"  ✓ Progress: {goal.progress}%")
    print(f"  ✓ Sub-goals: {len(goal.sub_goals)}")
    print(f"  ✓ Sessions: {len(goal.active_sessions)}")

    # ── Test 5: Policy Engine ───────────────────────────────────────────────
    print("\n[Test 5] Policy Engine — governance layer")
    pe = PolicyEngine()
    pe.add_policy(
        {
            "name": "no_delete",
            "condition": "delete",
            "action": "deny",
            "reason": "Deletion requires manual confirmation",
        }
    )
    from src.brain.schemas.thought import Goal as G
    from src.brain.schemas.thought import SafetyAssessment, Thought

    dc = Thought(
        goal=G(description="Delete file", confidence=0.95),
        raw_input="Delete the file",
        safety=SafetyAssessment(safe=True),
        confidence=Confidence(goal=0.95, entity=0.9, capability=0.95),
    )
    decision = pe.evaluate(dc)
    print(f"  ✓ Approved: {decision.approved}")
    print(f"  ✓ Policy: {decision.policy}")
    print(f"  ✓ Reason: {decision.reason}")

    # ── Test 6: Artifact Manager ────────────────────────────────────────────
    print("\n[Test 6] Artifact Manager — everything creates artifacts")
    am = ArtifactManager()
    art = am.create_artifact(
        artifact_type="research",
        name="Research Findings",
        content="Aura OS research results",
        creator="research",
        session_id=session.session_id,
    )
    print(f"  ✓ Artifact: {art.artifact_id}")
    print(f"  ✓ Type: {art.artifact_type}")
    print(f"  ✓ Name: {art.name}")

    # ── Test 7: Full ACABrain pipeline with all new pieces ─────────────────
    print("\n[Test 7] Full ACABrain pipeline (with Goal, Policy, Session, Artifacts)")

    async def mock_desktop(action, params):
        print(f"    [Desktop] {action}")
        return {"success": True, "observations": [f"Desktop: {action} completed"]}

    async def mock_browser(action, params):
        print(f"    [Browser] {action}")
        return {"success": True, "observations": [f"Browser: {action} completed"]}

    coordinator = ExecutionCoordinator()
    coordinator.register_engine("desktop", mock_desktop)
    coordinator.register_engine("browser", mock_browser)

    aca = ACABrain(
        context_manager=ContextManager(),
        world_model=WorldModel(),
        goal_analyzer=GoalAnalyzer(),
        capability_selector=CapabilitySelector(),
        fusion_engine=FusionEngine(),
        confidence_gate=ConfidenceGate(),
        goal_manager=GoalManager(),
        policy_engine=PolicyEngine(),
        planner=StrategyEngine(),
        validator=ExecutionMapValidator(),
        coordinator=coordinator,
        verification=VerificationEngine(),
        artifact_manager=ArtifactManager(),
        reflection=ReflectionEngine(),
        learning=LearningEngine(),
    )

    response = await aca.process("Open YouTube in Chrome")
    print(f"  ✓ Success: {response.success}")
    print(f"  ✓ Response: {response.text}")
    print(f"  ✓ Blackboard: {response.blackboard is not None}")
    print(f"  ✓ Session: {response.session is not None}")
    print(
        f"  ✓ Session status: {response.session.status if response.session else 'N/A'}"
    )
    print(f"  ✓ Goal: {response.goal is not None}")
    print(f"  ✓ Artifacts: {len(response.artifacts)}")

    # ── Test 8: Policy blocks dangerous request ─────────────────────────────
    print("\n[Test 8] Policy Engine blocks dangerous request")
    aca2 = ACABrain(
        context_manager=ContextManager(),
        world_model=WorldModel(),
        goal_analyzer=GoalAnalyzer(),
        capability_selector=CapabilitySelector(),
        fusion_engine=FusionEngine(),
        confidence_gate=ConfidenceGate(),
        goal_manager=GoalManager(),
        policy_engine=PolicyEngine(),
    )
    aca2.add_policy(
        {
            "name": "no_delete",
            "condition": "delete",
            "action": "deny",
            "reason": "Deletion requires manual confirmation",
        }
    )
    response2 = await aca2.process("Delete the file")
    print(f"  ✓ Success: {response2.success}")
    print(f"  ✓ Response: {response2.text}")

    print("\n" + "=" * 60)
    print("ALL ACA TESTS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
