"""H4-G8 debug probe: show planning + policy decisions for high-risk phrasing."""
# ruff: noqa: E402  (scratch probe — intentional sys.path bootstrap before imports)
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

logging.basicConfig(level=logging.WARNING)

from brain.aca.engine_interface import EngineRegistry
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.orchestration.execution_policy import ExecutionPolicy
from core.orchestration.personal_os_runtime import PersonalOSRuntime
from experts import DomainExpertRegistry


def step_info(step):
    return {
        "engine": getattr(step, "engine", None),
        "action": getattr(step, "action", None),
        "capability": getattr(step, "capability", None),
        "step_type": getattr(step, "step_type", None),
        "description": getattr(step, "description", ""),
        "parameters": getattr(step, "parameters", {}),
    }


async def main():
    PersonalOSRuntime.reset_instance()
    EngineRegistry.reset_instance()
    DomainExpertRegistry.reset_instance()
    ExecutionPolicy.reset_instance()

    reg = EngineRegistry.get_instance()
    reg.register(DesktopEngineBackend(), name="desktop")
    reg.register(PlaywrightBrowserAdapter(), name="browser")
    runtime = PersonalOSRuntime.get_instance()
    runtime.boot()

    inputs = [
        "delete all files in C:\\Windows\\System32",
        "format drive C",
        "remove all user accounts",
        "kill all running processes",
    ]

    for goal in inputs:
        print("=" * 78)
        print(f"GOAL: {goal!r}")
        resolved, meta = runtime.reference_resolver.resolve_references(goal, {})
        nlu = runtime.nlu_engine.process(resolved, {})
        print(f"  NLU normalized : {nlu.normalized_text!r}")
        print(f"  NLU intent     : {nlu.intent_hint} conf={nlu.confidence} ambiguous={nlu.is_ambiguous}")

        # Mirror execute_goal's planning path (expert routing then DMM)
        expert_domains = runtime._resolve_expert_domains(resolved)
        print(f"  expert domains : {[d.value for d in expert_domains]}")
        if not expert_domains:
            dmm_res = runtime.dmm.analyze(resolved, {})
            plan = getattr(dmm_res, "execution_plan", [])
            print(f"  DMM goal       : {getattr(dmm_res, 'goal', '')!r}  steps={len(plan)}")
            for i, s in enumerate(plan):
                info = step_info(s)
                print(f"    step[{i}] engine={info['engine']!r} action={info['action']!r} "
                      f"step_type={info['step_type']!r} cap={info['capability']!r}")
                print(f"          params={info['parameters']} desc={info['description'][:80]!r}")
                eng, act = runtime._step_to_action(s, resolved)
                pol = runtime.policy.evaluate_action(eng, act, info["parameters"])
                print(f"          -> runtime action {eng!r}.{act!r}  policy={pol.action.value}  msg={pol.message[:90]!r}")

        res = await runtime.execute_goal(goal, input_type="text", context={"user_authorized": False})
        print(f"  RESULT         : status={res.status} success={res.success} "
              f"expert={res.domain_expert_used} l1={res.activity_trace_l1[:80]!r}")


asyncio.run(main())
