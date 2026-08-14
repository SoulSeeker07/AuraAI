#!/usr/bin/env python3
"""
Level 4: Physical Hardware Integration Test for ContinuousVoiceLoop
Provides an interactive CLI to manually control and verify the full hardware voice lifecycle.
"""

import sys
import time
import asyncio
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from src.core.orchestration.personal_os_runtime import PersonalOSRuntime
from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState
from src.voice.voice_manager import VoiceManager
import logging

logging.basicConfig(level=logging.WARNING)

def print_help():
    print("--- LEVEL 4 INTERACTIVE VOICE TEST ---")
    print("Commands:")
    print("  start listening : Boot the OS Runtime and start the ContinuousVoiceLoop")
    print("  stop listening  : Stop the loop and shut down hardware")
    print("  state           : Print the current state of the ContinuousVoiceLoop and VoiceManager")
    print("  help            : Show this menu")
    print("  exit            : Quit testing")
    print("--------------------------------------")

async def main():
    print("==================================================")
    print(" AURA LEVEL 4: PHYSICAL HARDWARE INTEGRATION")
    print("==================================================")
    
    # 1. Boot OS Runtime
    os_runtime = PersonalOSRuntime.get_instance()
    
    print("[1/2] Booting PersonalOSRuntime...")
    try:
        os_runtime.boot()
    except Exception as e:
        print(f"Error booting OS Runtime: {e}")
        
    print("[2/2] Ready for commands.")
    print_help()
    
    loop = os_runtime.voice_loop
    
    while True:
        try:
            loop_instance = asyncio.get_running_loop()
            cmd = await loop_instance.run_in_executor(None, input, "\nAura CLI > ")
            cmd = cmd.strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
            
        if not cmd:
            continue
            
        if cmd == "start listening":
            if loop._running:
                print("Voice loop is already running.")
                continue
                
            print("Starting ContinuousVoiceLoop...")
            loop.start()
            print("State: WAITING_FOR_WAKE")
            
        elif cmd == "stop listening":
            if not loop._running:
                print("Voice loop is not running.")
                continue
                
            print("Stopping ContinuousVoiceLoop...")
            loop.stop()
            print("Voice loop stopped.")
            
        elif cmd == "state":
            fsm_state = loop.state.name
            vm_state = loop.voice_manager.state.name if hasattr(loop.voice_manager, 'state') else "UNKNOWN"
            is_active = loop.voice_manager.is_active if hasattr(loop.voice_manager, 'is_active') else "UNKNOWN"
            print(f"FSM State: {fsm_state}")
            print(f"VoiceManager State: {vm_state}")
            print(f"VoiceManager Hardware Active: {is_active}")
            print(f"FSM Running Flag: {loop._running}")
            
        elif cmd in ("help", "?"):
            print_help()
            
        elif cmd in ("exit", "quit"):
            print("Exiting...")
            if loop._running:
                loop.stop()
            break
            
        else:
            print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    asyncio.run(main())
