import os
import sys
import time
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(1, str(PROJECT_ROOT))

mode = sys.argv[1] if len(sys.argv) > 1 else ""

if mode == "clean":
    import shutil
    if os.path.exists("./aura_memory_db"):
        shutil.rmtree("./aura_memory_db")
        print("Database cleaned.")
    sys.exit(0)

if mode == "session1":
    from main import get_aura_core
    from src.core.orchestration.personal_os_runtime import PersonalOSRuntime
    print("=== SESSION 1 ===")
    core1 = get_aura_core()
    mm = PersonalOSRuntime.get_instance().memory_manager

    mm.add_user_turn("My favorite browser is Firefox.")
    mm.add_assistant_turn("Got it, your favorite browser is Firefox.")

    mm.add_user_turn("My temporary task today is to open Calculator.")
    mm.add_assistant_turn("Okay, temporary task noted.")

    mm.add_user_turn("My password is SUPERSECRET123.")
    mm.add_assistant_turn("I will not remember that, it is sensitive.")

    mm.add_user_turn("What is 25 times 4?")
    mm.add_assistant_turn("100.")

    print("Shutting down core 1 to trigger consolidation...")
    core1.shutdown()
    sys.exit(0)

if mode == "session2":
    from main import get_aura_core
    from src.core.orchestration.personal_os_runtime import PersonalOSRuntime
    print("\n=== SESSION 2 ===")
    core2 = get_aura_core()
    mm2 = PersonalOSRuntime.get_instance().memory_manager

    print("\n--- Long-term memory query ---")
    messages = mm2.get_context_messages("Which browser do I prefer?")

    system_msgs = [m for m in messages if m["role"] == "system"]
    print("Injected system context from retrieval:")
    for msg in system_msgs:
        print(msg["content"])
        
    if "Firefox" in str(system_msgs):
        print("\nSUCCESS: 'Firefox' was found in the retrieved context!")
    else:
        print("\nFAILED: 'Firefox' was NOT found in the retrieved context.")

    if "Calculator" in str(system_msgs) or "SUPERSECRET123" in str(system_msgs):
        print("\nFAILED: Policy check failed, temporary/sensitive data was remembered.")
    else:
        print("\nSUCCESS: Policy correctly rejected temporary and sensitive data.")
    sys.exit(0)
