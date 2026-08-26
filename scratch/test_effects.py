import asyncio
from kasa import Credentials, Discover

async def test_effects():
    creds = Credentials(username="yrsreekanta@gmail.com", password="Lakshmi@1")
    dev = await Discover.discover_single("192.168.29.215", credentials=creds)
    await dev.update()
    
    fx = dev.modules.get("LightEffect")
    if fx:
        print("LightEffect attrs:", [m for m in dir(fx) if not m.startswith("_")])
        if hasattr(fx, "effect_list"):
            print("effect_list:", fx.effect_list)
        if hasattr(fx, "effects"):
            print("effects:", fx.effects)
        if hasattr(fx, "effect"):
            print("current effect:", fx.effect)

if __name__ == "__main__":
    asyncio.run(test_effects())
