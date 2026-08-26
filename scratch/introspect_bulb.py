import asyncio
from kasa import Credentials, Discover

async def test_bulb_features():
    creds = Credentials(username="yrsreekanta@gmail.com", password="Lakshmi@1")
    dev = await Discover.discover_single("192.168.29.215", credentials=creds)
    await dev.update()
    
    print("Device attributes and methods:")
    print("is_color:", getattr(dev, "is_color", None))
    print("is_variable_color_temp:", getattr(dev, "is_variable_color_temp", None))
    print("color_temp_range:", getattr(dev, "color_temp_range", None))
    print("valid_color_temps:", getattr(dev, "valid_temperature_range", None))
    print("hsv:", getattr(dev, "hsv", None))
    print("has light_effect:", hasattr(dev, "set_light_effect"))
    if hasattr(dev, "light_effects"):
        print("light_effects:", dev.light_effects)

if __name__ == "__main__":
    asyncio.run(test_bulb_features())
