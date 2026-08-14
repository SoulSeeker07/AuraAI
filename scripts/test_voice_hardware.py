import os
import sys
import time
import logging
import asyncio

# Setup paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(1, os.path.join(project_root, 'src'))

from voice.continuous_loop import ContinuousVoiceLoop
from voice.voice_manager import VoiceManager
from voice.wake_word import WakeWordProvider

# We will intercept the logs to generate the final report
class HardwareLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = set()

    def emit(self, record):
        msg = self.format(record)
        if "[MIC] Stream opened: PASS" in msg:
            self.events.add("MIC_ACQUISITION")
        elif "[WAKE] Listener active: PASS" in msg:
            self.events.add("WAKE_ACTIVE")
        elif "[WAKE] Wake detected: PASS" in msg:
            self.events.add("WAKE_DETECTED")
        elif "[STT] Audio captured: PASS" in msg:
            self.events.add("STT_CAPTURE")
        elif "[STT] Transcription: PASS" in msg:
            self.events.add("STT_TRANSCRIPTION")
        elif "[TTS] Piper playback: PASS" in msg:
            self.events.add("TTS_PLAYBACK")
        elif "[MIC] Suppression: PASS" in msg:
            self.events.add("MIC_SUPPRESSION")
        elif "[MIC] Buffer flushed: PASS" in msg:
            self.events.add("BUFFER_FLUSH")
        elif "[MIC] Recovery: PASS" in msg:
            self.events.add("MIC_RECOVERY")
        elif "[WAKE] Listener resumed: PASS" in msg:
            self.events.add("WAKE_RESUMED")
        elif "[VOICE] Shutdown: PASS" in msg:
            self.events.add("SHUTDOWN")
        elif "[MIC] Stream released: PASS" in msg:
            self.events.add("MIC_RELEASED")

log_handler = HardwareLogHandler()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger().addHandler(log_handler)
logger = logging.getLogger("TestVoiceHardware")

class MockOSRuntime:
    """Mock execution to bypass LLM and tool running for L4 testing."""
    async def execute_goal(self, transcript: str, input_type: str):
        class MockReport:
            def __init__(self, text):
                self.success = True
                self.spoken_summary = text
        
        # Simple echo response
        return MockReport(f"You said: {transcript}")

    @classmethod
    def get_instance(cls):
        return cls()

# Patch PersonalOSRuntime so ContinuousVoiceLoop uses our mock
import src.core.orchestration.personal_os_runtime
src.core.orchestration.personal_os_runtime.PersonalOSRuntime = MockOSRuntime

def print_report(events, is_second_cycle=False):
    print("\n" + "="*50)
    print("AURA M21 L4 HARDWARE TEST")
    print("="*50 + "\n")

    def check(condition):
        return "PASS" if condition else "FAIL"
    
    first_wake = "WAKE_DETECTED" in events and "STT_TRANSCRIPTION" in events
    
    print(f"{'Microphone acquisition':<30} {check('MIC_ACQUISITION' in events)}")
    print(f"{'Aura wake detector':<30} {check('WAKE_ACTIVE' in events)}")
    print(f"{'First wake -> STT':<30} {check(first_wake)}")
    print(f"{'First TTS':<30} {check('TTS_PLAYBACK' in events)}")
    print(f"{'Mic suppression':<30} {check('MIC_SUPPRESSION' in events)}")
    print(f"{'Buffer flush':<30} {check('BUFFER_FLUSH' in events)}")
    print(f"{'Wake recovery':<30} {check('MIC_RECOVERY' in events and 'WAKE_RESUMED' in events)}")
    
    print(f"{'Shutdown':<30} {check('SHUTDOWN' in events)}")
    print(f"{'Microphone release':<30} {check('MIC_RELEASED' in events)}")
    print(f"{'Restart cycle':<30} {check(is_second_cycle)}")
    
    print("\n" + "="*50)
    
    all_passed = (
        "MIC_ACQUISITION" in events and
        "WAKE_ACTIVE" in events and
        "WAKE_DETECTED" in events and
        "STT_TRANSCRIPTION" in events and
        "TTS_PLAYBACK" in events and
        "MIC_SUPPRESSION" in events and
        "BUFFER_FLUSH" in events and
        "MIC_RECOVERY" in events and
        "WAKE_RESUMED" in events and
        "SHUTDOWN" in events and
        "MIC_RELEASED" in events and
        is_second_cycle
    )
    
    if all_passed:
        print("M21 L4 RESULT: PASS")
    else:
        print("M21 L4 RESULT: FAIL")
    print("="*50 + "\n")

async def main():
    logger.info("Initializing ContinuousVoiceLoop for hardware test...")
    vm = VoiceManager()
    loop = ContinuousVoiceLoop(voice_manager=vm)
    
    # Force AURA Wake Word just in case settings don't apply it
    vm.settings["wake_word_provider"] = WakeWordProvider.AURA.value
    
    print("\n--- TEST CYCLE 1 ---")
    logger.info("Starting loop...")
    success = loop.start()
    
    if not success:
        logger.error("Failed to start loop. Check microphone permissions.")
        print_report(log_handler.events)
        return
        
    print("\n*** PLEASE SPEAK THE WAKE WORD NOW ***")
    print("*** THEN SAY 'Hello this is a test' ***")
    print("*** AFTER TTS FINISHES, SPEAK THE WAKE WORD AGAIN! ***\n")
    
    try:
        # We will wait until they trigger it twice.
        while loop.turn_count < 2:
            await asyncio.sleep(1)
            
        print("\n*** Second turn completed! Shutting down... ***\n")
        loop.stop()
        
        # Test restart cycle
        print("\n--- TEST CYCLE 2 (RESTART) ---")
        success2 = loop.start()
        if success2:
            print("\n*** RESTART CYCLE SUCCESSFUL! Shutting down final time... ***\n")
            await asyncio.sleep(2)
            loop.stop()
            is_second_cycle = True
        else:
            print("\n*** RESTART CYCLE FAILED! ***\n")
            is_second_cycle = False
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        loop.stop()
        is_second_cycle = False
        
    # Print the final machine-readable report
    print_report(log_handler.events, is_second_cycle)

if __name__ == "__main__":
    asyncio.run(main())
