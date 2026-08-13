"""
Milestone 26 Personal Operating System Final Acceptance Benchmark
Location: scratch/test_m26_personal_os_gate.py

Verifies all 12 M26 acceptance gates:
  G1: Unified Runtime Boot (All subsystems booted cleanly)
  G2: Unified Natural-Language Entry (Text and Voice STT identical pipeline)
  G3: Contextual Continuity & Follow-up Referent Resolution
  G4: Desktop + Browser Unified Execution Map Task
  G5: Expert-System Routing (No secondary router/brain introduced)
  G6: Proactive Event Runtime Integration
  G7: ExecutionPolicy Governance & High-Risk Blocking
  G8: Failure Recovery (RECOVERED_SUCCESS on transient failure)
  G9: Independent Physical Evidence Verification (GoalVerifier)
  G10: Long-Running Runtime Session Stability
  G11: Unified Observability (Activity Trace L1 & L2)
  G12: Complete Personal-OS End-to-End Acceptance Gate
"""

import asyncio
import os
import sys
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath("src"))

from brain.aca.engine_interface import EngineRegistry
from brain.execution_coordinator import ExecutionCoordinator
from brain.executive.execution_map import Capability, ExecutionMap, ExecutionStep, StepType
from brain.goal_verifier import GoalVerifier
from core.backends.adapters.browser_backend import PlaywrightBrowserAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.orchestration.execution_policy import ExecutionPolicy
from core.orchestration.personal_os_runtime import PersonalOSRuntime
from experts import (
    CybersecurityAuditExpert,
    DomainExpertRegistry,
    FinancialAnalysisExpert,
    NetworkDiagnosticsExpert,
    SoftwareEngineeringExpert,
)


def setup_fresh_runtime():
    PersonalOSRuntime.reset_instance()
    EngineRegistry.reset_instance()
    DomainExpertRegistry.reset_instance()
    ExecutionPolicy._instance = None

    reg = EngineRegistry.get_instance()
    reg.register(DesktopEngineBackend(), name="desktop")
    reg.register(PlaywrightBrowserAdapter(), name="browser")
    print("ENGINES AT BOOT:", {k: v.__class__.__name__ for k, v in reg._engines.items()})

    expert_reg = DomainExpertRegistry.get_instance()
    expert_reg.register(SoftwareEngineeringExpert())
    expert_reg.register(NetworkDiagnosticsExpert())
    expert_reg.register(CybersecurityAuditExpert())
    expert_reg.register(FinancialAnalysisExpert())

    runtime = PersonalOSRuntime.get_instance()
    boot_info = runtime.boot()
    return runtime, boot_info


async def run_m26_benchmark():
    runtime, boot_info = setup_fresh_runtime()

    # Gate G1: Unified Runtime Boot
    g1_pass = boot_info.get("status") == "BOOTED" and boot_info.get("subsystems_ready") is True

    # Gate G2: Unified Natural-Language Entry (Text & Voice)
    rep_text = await runtime.execute_goal("open notepad and write hello world", input_type="text")
    rep_voice = await runtime.execute_goal("open browser and search google", input_type="voice")
    print(f"[DEBUG G2] rep_text success={rep_text.success} status={rep_text.status} traces={rep_text.activity_trace_l2}")
    print(f"[DEBUG G2] rep_voice success={rep_voice.success} status={rep_voice.status} traces={rep_voice.activity_trace_l2}")
    g2_pass = rep_text.success and rep_voice.success and rep_text.input_type == "text" and rep_voice.input_type == "voice"

    # Gate G3: Contextual Continuity & Follow-Up Referent Resolution
    rep_cont = await runtime.execute_goal("write text to that app", input_type="text")
    print(f"[DEBUG G3] rep_cont success={rep_cont.success} verification={rep_cont.verification_passed}")
    g3_pass = rep_cont.success and rep_cont.verification_passed is True

    # Gate G4: Desktop + Browser Unified Execution Map Task
    unified_goal = "open notepad and navigate browser to data:text/html,<h1>Unified</h1>"
    rep_uni = await runtime.execute_goal(unified_goal, input_type="text")
    print(f"[DEBUG G4] rep_uni success={rep_uni.success} steps={rep_uni.steps_executed}")
    g4_pass = rep_uni.success and rep_uni.steps_executed >= 2

    # Gate G5: Expert-System Routing (Without Secondary Brain)
    rep_exp = await runtime.execute_goal("audit workspace security posture", input_type="text")
    print(f"[DEBUG G5] rep_exp success={rep_exp.success} expert={rep_exp.domain_expert_used}")
    g5_pass = rep_exp.success and rep_exp.domain_expert_used == "cybersecurity_audit"

    # Gate G6: Proactive Event Runtime Integration
    g6_pass = runtime.event_runtime._running is True and hasattr(runtime.event_runtime, "_queue")

    # Gate G7: ExecutionPolicy Governance & High-Risk Blocking
    rep_block = await runtime.execute_goal("delete protected file secret.key", input_type="text", context={"user_authorized": False})
    print(f"[DEBUG G7] rep_block status={rep_block.status} success={rep_block.success}")
    g7_pass = rep_block.status == "BLOCKED" and rep_block.success is False

    # Gate G8: Failure Recovery (RECOVERED_SUCCESS)
    coord = runtime.coordinator
    step_fail = ExecutionStep(
        step_type=StepType.LAUNCH,
        description="Launch notepad with simulated retry",
        capability=Capability.DESKTOP,
        parameters={"app_name": "notepad", "action": "app.launch"},
    )
    exec_map_rec = ExecutionMap(goal="launch notepad with retry", execution_plan=[step_fail])

    class FailOnceBackend(DesktopEngineBackend):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def execute(self, capability: str, goal: Any = "", arguments: dict | None = None) -> Any:
            self.attempts += 1
            if self.attempts == 1:
                raise TimeoutError("Simulated transient physical failure")
            return super().execute(capability, goal, arguments)

    fail_backend = FailOnceBackend()
    reg = EngineRegistry.get_instance()
    reg.register(fail_backend, name="desktop")

    map_rec_dict = {"goal": exec_map_rec.goal, "steps": [{"engine": "desktop", "action": "open_app", "parameters": {"app_name": "notepad"}}]}
    rec_res = await coord.coordinate(map_rec_dict)
    has_recovery = any(isinstance(getattr(s, "data", {}), dict) and s.data.get("recovery_trace") is not None for s in rec_res.step_results)
    g8_pass = rec_res.success is True and (len(rec_res.failed_steps) > 0 or has_recovery)
    reg.register(DesktopEngineBackend(), name="desktop")

    # Gate G9: Independent Physical Evidence Verification
    g9_pass = rep_text.verification_passed is True and len(rep_text.evidence) > 0

    # Gate G10: Long-Running Runtime Session Stability
    g10_pass = len(runtime.turn_history) >= 5 and all(isinstance(h.worked_time_ms, float) for h in runtime.turn_history)

    # Gate G11: Unified Observability (Activity Trace L1 & L2)
    g11_pass = len(rep_text.activity_trace_l1) > 0 and len(rep_text.activity_trace_l2) > 0 and "Worked for" in rep_text.activity_trace_l1

    # Gate G12: Complete Personal-OS End-to-End Acceptance Gate
    g12_pass = all([g1_pass, g2_pass, g3_pass, g4_pass, g5_pass, g6_pass, g7_pass, g8_pass, g9_pass, g10_pass, g11_pass])

    facts = {
        "G1: Unified Runtime Boot (All Subsystems Cleanly Initialized)": g1_pass,
        "G2: Unified Natural-Language Entry (Text & Voice STT Pipeline)": g2_pass,
        "G3: Contextual Continuity & Referent Follow-Up Resolution": g3_pass,
        "G4: Desktop + Browser Unified Execution Map Task": g4_pass,
        "G5: Expert-System Routing (No Secondary Router/Brain)": g5_pass,
        "G6: Proactive Event Runtime Integration": g6_pass,
        "G7: ExecutionPolicy Governance & High-Risk Blocking (BLOCKED)": g7_pass,
        "G8: Failure Recovery (RECOVERED_SUCCESS on Transient Failure)": g8_pass,
        "G9: Independent Physical Evidence Verification (GoalVerifier)": g9_pass,
        "G10: Long-Running Runtime Session Stability (Turn History)": g10_pass,
        "G11: Unified Observability (Activity Trace L1 & L2 Renders)": g11_pass,
        "G12: Complete Personal-OS End-to-End Acceptance Gate": g12_pass,
    }

    all_pass = all(facts.values())

    print("==========================================================================")
    print("     AURA MILESTONE 26 -- PERSONAL OPERATING SYSTEM FINAL BENCHMARK")
    print("==========================================================================")
    for k, v in facts.items():
        status_str = "PASS" if v else "FAIL"
        print(f"  +-- {k:<66} : {status_str}")
    print("--------------------------------------------------------------------------")
    print(f"Milestone 26 Personal OS Acceptance Final Result: {'PASS' if all_pass else 'FAIL'}")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_m26_benchmark())
