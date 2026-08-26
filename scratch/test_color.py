import asyncio
from kasa import Credentials, Discover

async def test_color():
    creds = Credentials(username="yrsreekanta@gmail.com", password="Lakshmi@1")
    dev = await Discover.discover_single("192.168.29.215", credentials=creds)
    await dev.update()
    
    print("Modules:", dev.modules.keys())
    light = dev.modules.get("Light") or dev.modules.get("light")
    if light:
        print("Light module attrs:", [m for m in dir(light) if not m.startswith("_")])
        # Test setting color to red (Hue: 0, Sat: 100, Val: 100)
        await light.set_hsv(0, 100, 100)
        await dev.update()
        print("After setting red HSV:", light.hsv)

if __name__ == "__main__":
    asyncio.run(test_color())
