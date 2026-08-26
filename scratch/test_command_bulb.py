import asyncio
from dotenv import load_dotenv
load_dotenv()

from core.backends.adapters.smarthome_backend import SmartHomeBackendAdapter

async def test_bulb_commands():
    adapter = SmartHomeBackendAdapter()
    
    print("1. Testing set_brightness to 40%...")
    res = await adapter.execute_async("light.set_brightness", "Set brightness to 40", {"brightness": 40})
    print(f"Result: success={res.success}, obs={res.observations}, brightness={res.data.get('state', {}).get('attributes', {}).get('brightness')}")

if __name__ == "__main__":
    asyncio.run(test_bulb_commands())
