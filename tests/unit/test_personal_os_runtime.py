"""
Unit tests for PersonalOSRuntime (Milestone 26 Personal Operating System Integration)
Location: tests/unit/test_personal_os_runtime.py

Verifies:
  - Unified runtime boot & subsystem initialization
  - Unified natural-language execution (Text & Voice STT)
  - Contextual follow-up resolution & memory continuity
  - Cross-domain expert routing without additional brains
  - Governance policy blocking & security barriers
  - Independent physical evidence verification
"""

import pytest
import asyncio
from brain.aca.engine_interface import EngineRegistry
from experts import DomainExpertRegistry, SoftwareEngineeringExpert
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction
from core.orchestration.personal_os_runtime import PersonalOSRuntime


def setup_fresh_runtime():
    PersonalOSRuntime.reset_instance()
    EngineRegistry.reset_instance()
    DomainExpertRegistry.reset_instance()
    ExecutionPolicy.reset_instance()

    reg = EngineRegistry.get_instance()
    reg.register(DesktopEngineBackend(), name="desktop")
    reg.register(PlaywrightBrowserAdapter(), name="browser")

    expert_reg = DomainExpertRegistry.get_instance()
    expert_reg.register(SoftwareEngineeringExpert())

    runtime = PersonalOSRuntime.get_instance()
    runtime.boot()
    return runtime


@pytest.mark.asyncio
async def test_00_singleton_identity_invariant():
    """
    ARCHITECTURAL INVARIANT: All singleton registries used by PersonalOSRuntime
    must be the SAME Python object as those obtained directly from their classes.

    This test guards against the Python module-split bug where importing
    `brain.X` and `src.brain.X` loads the same physical module under two keys,
    producing two separate class objects with two separate `_instance` slots.

    If this test fails, check pyproject.toml `pythonpath = ["src"]` and ensure
    NO file in tests/ or src/ uses `src.brain.*`, `src.core.*`, `src.experts.*`,
    or `src.autonomy.*` prefixes — all imports must use the bare path.
    """
    runtime = setup_fresh_runtime()

    assert EngineRegistry.get_instance() is runtime.engine_registry, (
        "EngineRegistry singleton mismatch: runtime.engine_registry is a DIFFERENT object "
        "from EngineRegistry.get_instance(). This means the module was loaded under two "
        "different import paths (e.g. `brain.*` vs `src.brain.*`). Fix the import convention."
    )

    assert DomainExpertRegistry.get_instance() is runtime.expert_registry, (
        "DomainExpertRegistry singleton mismatch: runtime.expert_registry is a DIFFERENT object "
        "from DomainExpertRegistry.get_instance(). This means the module was loaded under two "
        "different import paths (e.g. `experts.*` vs `src.experts.*`). Fix the import convention."
    )

    assert ExecutionPolicy.get_instance() is runtime.policy, (
        "ExecutionPolicy singleton mismatch: runtime.policy is a DIFFERENT object "
        "from ExecutionPolicy.get_instance(). This means the module was loaded under two "
        "different import paths (e.g. `core.orchestration.*` vs `src.core.orchestration.*`). "
        "Fix the import convention."
    )


@pytest.mark.asyncio
async def test_01_personal_os_runtime_boot():
    runtime = setup_fresh_runtime()
    assert runtime._booted is True
    assert len(runtime.engine_registry._engines) >= 2


@pytest.mark.asyncio
async def test_02_unified_goal_execution_text_and_voice():
    runtime = setup_fresh_runtime()
    res_text = await runtime.execute_goal("open notepad and write hello world", input_type="text")
    assert res_text.success is True
    assert res_text.input_type == "text"
    assert res_text.verification_passed is True

    res_voice = await runtime.execute_goal("open browser and search google", input_type="voice")
    assert res_voice.success is True
    assert res_voice.input_type == "voice"
    assert res_voice.verification_passed is True


@pytest.mark.asyncio
async def test_03_contextual_follow_up_referent_resolution():
    runtime = setup_fresh_runtime()

    res1 = await runtime.execute_goal("open notepad", input_type="text")
    assert res1.success is True

    res2 = await runtime.execute_goal("write text to that app", input_type="text")
    assert res2.success is True
    assert res2.verification_passed is True


@pytest.mark.asyncio
async def test_04_expert_routing_without_extra_brain():
    runtime = setup_fresh_runtime()
    res = await runtime.execute_goal("refactor module src/experts/models.py", input_type="text")
    assert res.success is True
    assert res.domain_expert_used == "software_engineering"
    assert res.verification_passed is True


@pytest.mark.asyncio
async def test_05_policy_governance_blocking():
    runtime = setup_fresh_runtime()
    res = await runtime.execute_goal("delete file protected.key", input_type="text", context={"user_authorized": False})
    assert res.success is False
    assert res.status == "BLOCKED"
    assert "[POLICY BLOCKED]" in res.activity_trace_l1
