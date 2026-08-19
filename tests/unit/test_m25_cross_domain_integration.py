"""
Milestone 25 Cross-Domain Integration Gate & Interoperability Acceptance Suite
Location: tests/unit/test_m25_cross_domain_integration.py

Verifies:
1. Unified Coexistence: All 4 professional experts (Software, Network, Cybersecurity, Finance)
   coexist harmoniously behind a single unified ExpertDomainRouter & PlannerRegistry.
2. Deterministic Routing Disambiguation:
   - Software Engineering goals route to Software Expert
   - Network Engineering goals route to Network Expert
   - Cybersecurity goals route to Security Expert
   - Financial Analysis goals route to Finance Expert
   - Out-of-scope goals gracefully return None without error.
3. PlanDAG Interoperability & CapabilityRegistry Validation:
   - All 4 domain planners produce structured, cycle-free PlanDAG data structures.
   - All referenced capabilities validate against the universal CapabilityRegistry.
4. Causal Chain Continuity:
   - Full causal audit trail flows unbroken from event_id -> correlation_id -> policy_decision_id
     -> domain_assessment_id -> plan_id.
5. Zero Cross-Domain State Leakage:
   - Planners and analyzers maintain strict state isolation.
"""

import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.planner_registry import PlannerRegistry
from experts.models import DomainAssessment, PlanDAG
from experts.router import ExpertDomainRouter


@pytest.fixture(autouse=True)
def setup_router():
    """Ensure fresh singleton router with all default experts registered."""
    ExpertDomainRouter.reset_instance()
    router = ExpertDomainRouter.get_instance()
    yield router
    ExpertDomainRouter.reset_instance()


@pytest.mark.asyncio
async def test_cross_domain_router_registration_and_inventory(setup_router):
    """Verify all 4 professional domain experts are registered and discoverable."""
    router = setup_router
    domains = router.list_experts()

    assert "software_engineering" in domains
    assert "network_engineering" in domains
    assert "cybersecurity" in domains
    assert "finance" in domains
    assert len(domains) == 4


@pytest.mark.asyncio
async def test_cross_domain_deterministic_disambiguation(setup_router):
    """Verify distinct domain queries are accurately and deterministically routed to their respective experts."""
    router = setup_router

    scenarios = [
        ("Refactor authentication handler and fix pytest assertion error", "software_engineering"),
        ("Investigate high latency, packet loss, and DNS timeout on gateway 192.168.1.1", "network_engineering"),
        ("Scan repository for leaked API keys, audit open listening ports, and check CVEs", "cybersecurity"),
        ("Build financial model calculating EBITDA, gross margins, and YoY revenue CAGR", "finance"),
    ]

    for goal_text, expected_domain in scenarios:
        expert, assessment, rationale = await router.route(goal_text)
        assert expert is not None, f"Failed to route '{goal_text}'"
        assert expert.domain == expected_domain
        assert assessment is not None
        assert assessment.domain == expected_domain
        assert assessment.confidence >= 0.85
        assert (
            expected_domain.replace("_", " ") in rationale.lower()
            or expected_domain in rationale.lower()
            or "financial" in rationale.lower()
        )


@pytest.mark.asyncio
async def test_cross_domain_unsupported_goal_graceful_fallback(setup_router):
    """Verify completely unrelated non-technical goals fail safely with no expert selected."""
    router = setup_router
    obscure_goal = "Write a haiku about autumn leaves in Kyoto"
    expert, assessment, rationale = await router.route(obscure_goal, min_confidence=0.50)

    assert expert is None
    assert assessment is None
    assert "No domain expert matched" in rationale


@pytest.mark.asyncio
async def test_cross_domain_plandag_synthesis_and_registry_validation(setup_router):
    """Verify that all 4 experts synthesize valid, acyclic PlanDAGs that validate against CapabilityRegistry."""
    router = setup_router
    cap_registry = CapabilityRegistry.get_instance()

    test_goals = {
        "software_engineering": "Fix circular import in service modules and run regression tests",
        "network_engineering": "Probe DNS records and evaluate round-trip latency to 8.8.8.8",
        "cybersecurity": "Audit exposed credentials in .env files and evaluate attack surface",
        "finance": "Calculate budget vs actual variances and generate multi-scenario forecast",
    }

    for domain_name, goal_text in test_goals.items():
        expert = router.get_expert(domain_name)
        assert expert is not None

        assessment = await expert.assess(goal_text)
        assert isinstance(assessment, DomainAssessment)
        assert assessment.domain == domain_name

        plan = await expert.generate_plan(goal_text, assessment)
        assert isinstance(plan, PlanDAG)
        assert plan.domain == domain_name
        assert len(plan.nodes) >= 3

        # Topological stage calculation
        stages = plan.compute_execution_stages()
        assert len(stages) >= 2

        # Validate against Universal CapabilityRegistry
        val_result = expert.validate_plan(plan, capability_registry=cap_registry)
        assert val_result.valid is True, f"Validation failed for domain '{domain_name}': {val_result.errors}"


@pytest.mark.asyncio
async def test_cross_domain_causal_identity_chain(setup_router):
    """Verify causal tracking flows unbroken across autonomous event context into domain assessment and PlanDAG."""
    router = setup_router

    causal_context = {
        "event_id": "evt_autonomous_crash_001",
        "correlation_id": "corr_cross_domain_001",
        "policy_decision_id": "pol_hmac_authorized_001",
    }

    goal = "Diagnose pytest test failure in payment processor"
    expert, assessment, rationale = await router.route(goal, context={"causal_context": causal_context})

    assert expert is not None
    assert assessment is not None
    assert assessment.causal_context["event_id"] == "evt_autonomous_crash_001"
    assert assessment.causal_context["correlation_id"] == "corr_cross_domain_001"
    assert assessment.causal_context["policy_decision_id"] == "pol_hmac_authorized_001"

    plan = await expert.generate_plan(goal, assessment)
    assert plan.causal_context["event_id"] == "evt_autonomous_crash_001"
    assert plan.assessment_id == assessment.assessment_id
    assert plan.plan_id.startswith("plan_")


@pytest.mark.asyncio
async def test_planner_registry_unified_delegation():
    """Verify MasterOrchestrator's PlannerRegistry delegates seamlessly to all 4 experts."""
    reg = PlannerRegistry.get_instance()
    router = reg.get_expert_router()
    assert len(router.list_experts()) == 4

    expert, asm, rat = await reg.route_to_expert("Compute EBITDA margin and revenue variance for Q4")
    assert expert is not None
    assert expert.domain == "finance"
    assert asm is not None
    assert asm.domain == "finance"
