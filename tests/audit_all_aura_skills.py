"""
Comprehensive Skill & Command Audit Suite for AuraAI
===================================================
Tests every skill, every planner role, and every system command
directly against the live AuraCore instance.
"""

import asyncio
import sys
from pathlib import Path

# Add src to sys.path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from core.aura_core import AuraCore
from core.orchestration.decision_engine import DecisionEngine
from core.system.system_knowledge_resolver import SystemKnowledgeResolver
from gui.real_backend_bridge import RealBackendBridge


TEST_CASES = [
    # 1. System Self-Knowledge & Capabilities
    ("System Capabilities", "what are your capabilities", lambda res: "capabilities" in res.lower() or "registered" in res.lower()),
    ("System Limitations", "what are your limitations", lambda res: "cannot" in res.lower() or "limitation" in res.lower() or "policy" in res.lower()),
    ("Swarm & DAG Pool", "inspect active DAG reasoning graph and subagent pool", lambda res: "Swarm" in res or "DAG" in res or "Planners" in res),
    
    # 2. Hardware Diagnostics & Environmental Telemetry
    ("Hardware Diagnostics", "hardware health", lambda res: "CPU" in res and "RAM" in res and "GPU" in res),
    ("Environmental Weather", "weather", lambda res: "Weather" in res or "Temperature" in res or "°C" in res),
    ("Workspace File Scanner", "scan workspace", lambda res: "Python Files" in res or "Lines of Code" in res or "Workspace" in res),
    
    # 3. Token Quota & Multi-Account Tracking
    ("Daily Token Counter", "how many tokens left today", lambda res: "Tokens" in res and "1,000,000" in res),
    
    # 4. Long-Term Vector Memory
    ("Memory Inspection", "inspect memory", lambda res: "Memory" in res or "Facts" in res or "Vector" in res),
    
    # 5. Desktop Automation & Browser Navigation
    ("Browser Navigation", "open instagram", lambda res: "instagram" in res.lower() or "browser" in res.lower()),
    ("Browser Search", "open youtube", lambda res: "youtube" in res.lower() or "browser" in res.lower()),
]


async def run_audit():
    print("=" * 70)
    print("🚀 STARTING EXHAUSTIVE AURA AI SKILL & COMMAND AUDIT")
    print("=" * 70)

    core = AuraCore.get_instance()
    de = DecisionEngine()
    
    passed = 0
    failed = 0

    for name, query, validator in TEST_CASES:
        print(f"\n[TEST] {name} -> Query: '{query}'")
        try:
            # 1. Test DecisionEngine evaluation
            outcome = de.evaluate(query)
            print(f"  └─ Intent: {outcome.intent_type.value} | Preferred Planner: {outcome.preferred_planner}")
            
            # 2. Test full AuraCore process_request execution
            response = await core.process_request(query)
            if not response:
                response = await core.get_ai_response(query)
            
            resp_str = str(response)
            is_valid = validator(resp_str)
            
            if is_valid and not resp_str.startswith("❌ Pipeline Execution Error"):
                print(f"  └─ ✅ PASSED (Preview: {resp_str[:70]}...)")
                passed += 1
            else:
                print(f"  └─ ❌ FAILED Validation! Response: {resp_str[:120]}...")
                failed += 1
        except Exception as exc:
            print(f"  └─ 💥 EXCEPTION: {exc}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"AUDIT SUMMARY: {passed} PASSED, {failed} FAILED (Total: {len(TEST_CASES)})")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_audit())
    sys.exit(0 if success else 1)
