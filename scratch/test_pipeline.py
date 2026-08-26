import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(1, str(PROJECT_ROOT))

from core.aura_core import AuraCore

async def test():
    print("Instantiating AuraCore...", flush=True)
    core = AuraCore(config={"voice_enabled": False})
    
    queries = [
        "what is the weather",
        "turn on the smart light",
        "set screen brightness to 50%",
        "what is my battery percentage",
        "mute audio"
    ]
    
    for q in queries:
        print(f"\n====================\nTesting: '{q}'", flush=True)
        res = await core.process_request(q)
        print(f"RESULT: {res}", flush=True)

if __name__ == "__main__":
    asyncio.run(test())
