import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(1, str(PROJECT_ROOT))

from main import get_aura_core
from clients.gui_client import GUIClient
from gui.real_backend_bridge import RealBackendBridge

async def main():
    print("=" * 60, flush=True)
    print("AURA UNIFIED KERNEL & GUI VERIFICATION TEST SUITE", flush=True)
    print("=" * 60, flush=True)

    # 1. Test RealBackendBridge.get_weather_data()
    print("\n[1/5] Testing RealBackendBridge.get_weather_data()...", flush=True)
    bridge = RealBackendBridge.get_instance()
    w_data = bridge.get_weather_data()
    print(f"Weather Data: {w_data}", flush=True)
    assert "city" in w_data and "temp" in w_data, "RealBackendBridge.get_weather_data() failed"
    print("✓ RealBackendBridge weather data verified.", flush=True)

    # 2. Test AuraCore instantiation
    print("\n[2/5] Initializing AuraCore singleton...", flush=True)
    core = get_aura_core(config={"voice_enabled": False})
    assert core is not None, "Failed to get AuraCore"
    print("✓ AuraCore initialized.", flush=True)

    # 3. Test GUIClient.send_message()
    print("\n[3/5] Testing GUIClient.send_message()...", flush=True)
    gui_client = GUIClient(core)
    gui_res = await gui_client.send_message("what is the weather")
    print(f"GUIClient Response:\n{gui_res}", flush=True)
    assert "Weather" in gui_res or "°C" in gui_res, "GUIClient weather response failed"
    print("✓ GUIClient.send_message verified.", flush=True)

    # 4. Test AuraCore.process_request with all capabilities (GUI path)
    print("\n[4/5] Testing AuraCore.process_request (GUI command execution path)...", flush=True)
    test_cases = [
        ("what is the weather", ["Weather", "°C"]),
        ("turn on the smart light", ["Smart Bulb", "turned ON", "state", "bulb"]),
        ("set screen brightness to 50%", ["Display Brightness", "Brightness", "%"]),
        ("what is my battery percentage", ["Battery", "battery"]),
        ("mute audio", ["Audio", "Muted", "muted", "audio", "volume"]),
        ("open weather hud", ["Weather HUD", "Overlay", "toggled"]),
        ("what is my name", ["name", "Name"]),
    ]

    for query, expected_keywords in test_cases:
        print(f"\n--- Query: '{query}' ---", flush=True)
        res = await core.process_request(query)
        print(f"Result:\n{res}", flush=True)
        assert any(k.lower() in res.lower() for k in expected_keywords), f"Query '{query}' failed to produce expected output: {res}"
        print(f"✓ '{query}' passed.", flush=True)

    # 5. Test CLI Regression (ConversationEngine direct path)
    print("\n[5/5] Testing CLI regression (ConversationEngine.process direct path)...", flush=True)
    if hasattr(core, "conversation_engine") and core.conversation_engine:
        cli_res = await core.conversation_engine.process("what is the weather")
        print(f"CLI ConvEngine Text:\n{cli_res.text}", flush=True)
        assert "Weather" in cli_res.text or "°C" in cli_res.text, "CLI ConversationEngine regression failed"
        print("✓ CLI ConversationEngine regression check passed.", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("ALL 5 VERIFICATION SUITES PASSED CLEANLY!", flush=True)
    print("=" * 60, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
