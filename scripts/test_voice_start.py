import os
import sys
import logging
import asyncio
from pathlib import Path
import time

# Add src to pythonpath
sys.path.append(str(Path(__file__).parent.parent / "src"))
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.DEBUG)

from dotenv import load_dotenv
load_dotenv()

from src.core.orchestration.personal_os_runtime import PersonalOSRuntime

async def main():
    os_runtime = PersonalOSRuntime.get_instance()
    success = os_runtime.voice_loop.start()
    print("VoiceLoop started:", success)
    print("Waiting 15 seconds to see if wake word is detected...")
    await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(main())
print("Is audio recording?", os_runtime.voice_loop.voice_manager.audio_manager.is_recording())


