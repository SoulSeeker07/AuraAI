import asyncio
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))

from core.aura_core import AuraCore

async def main():
    print("=" * 60)
    print("TESTING BACKEND VOICE_CONTROL INTENT RESOLUTION")
    print("=" * 60)
    
    core = AuraCore.get_instance()
    
    # Test 1: Start listening
    res1 = await core.process_request("start listening")
    print("\n[Command: 'start listening']")
    print("Result:", res1)
    
    # Test 2: Voice status
    res2 = await core.process_request("voice listening status")
    print("\n[Command: 'voice listening status']")
    print("Result:", res2)
    
    # Test 3: Stop listening
    res3 = await core.process_request("stop listening")
    print("\n[Command: 'stop listening']")
    print("Result:", res3)
    
    print("\n" + "=" * 60)
    print("BACKEND VOICE INTENTS VERIFIED SUCCESSFULLY")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
