import asyncio
from dotenv import load_dotenv
load_dotenv()

from core.backends.adapters.smarthome_backend import SmartHomeBackendAdapter
from core.capabilities.capability_registry import CapabilityRegistry

async def main():
    reg = CapabilityRegistry.get_instance()
    cap = reg.get("light.turn_on")
    print(f"Capability in registry: {cap.name}, is_live: {cap.is_live}, domain: {cap.domain}")

    adapter = SmartHomeBackendAdapter()
    print("Testing get_state on physical bulb...")
    res = await adapter.execute_async("entity.get_state", "Get bulb state", {})
    print(f"State result: success={res.success}, data={res.data}")

if __name__ == "__main__":
    asyncio.run(main())
