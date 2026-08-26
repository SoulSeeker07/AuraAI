import asyncio
from kasa import Credentials, Discover

async def test_bulb():
    creds = Credentials(username="yrsreekanta@gmail.com", password="Lakshmi@1")
    dev = await Discover.discover_single("192.168.29.215", credentials=creds)
    await dev.update()
    print(f"Device: {dev.alias}, is_on: {dev.is_on}, brightness: {dev.brightness}")

if __name__ == "__main__":
    asyncio.run(test_bulb())
