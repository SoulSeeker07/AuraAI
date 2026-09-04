import os
import pytest
from unittest.mock import MagicMock, patch
from brain.intent_router import IntentRouter
from brain.conversation_engine import ConversationEngine
from brain.models import Intent
from Memory import Memory

@pytest.fixture
def memory_instance():
    mem = Memory()
    mem.upsert_fact("profile", "name", "Sreekanta")
    mem.upsert_fact("skills", "skill_1", "Python")
    mem.upsert_fact("goals", "goal_1", "Complete autonomous assistant")
    mem.upsert_fact("preferences", "pref_1", "Dark mode")
    mem.upsert_fact("projects", "project_1", "AuraAI")
    return mem

@pytest.fixture
def router(memory_instance, monkeypatch):
    monkeypatch.setenv("AURA_AUTONOMOUS_BROWSER_ENABLED", "1")
    return IntentRouter(memory_instance)

@pytest.fixture
def engine(memory_instance):
    return ConversationEngine(memory=memory_instance, provider_manager=None)

# ── Matrix of 23 Deterministic Fast-Path Intents ──
FASTPATH_INTENT_ROUTING_CASES = [
    ("turn on the smart light", "smarthome_control"),
    ("dim smart bulb to 50%", "smarthome_control"),
    ("what is the weather", "live_weather"),
    ("current temperature", "live_weather"),
    ("set screen brightness to 50%", "brightness_control"),
    ("dim screen brightness", "brightness_control"),
    ("mute audio", "audio_control"),
    ("mute the volume", "audio_control"),
    ("turn volume up", "audio_control"),
    ("turn down volume", "audio_control"),
    ("set volume to 80%", "audio_control"),
    ("what is my battery percentage", "battery_status"),
    ("charging status", "battery_status"),
    ("restart aura", "restart_aura"),
    ("restart the app", "restart_aura"),
    ("reboot aura", "restart_aura"),
    ("what time is it", "local_time"),
    ("today's date", "local_time"),
    ("summarize my memory", "memory_summary"),
    ("what do you remember", "memory_summary"),
    ("what is my name", "profile_lookup"),
    ("who am i", "profile_lookup"),
    ("what are my skills", "skills_lookup"),
    ("list my skills", "skills_lookup"),
    ("what are my goals", "goals_lookup"),
    ("what are my preferences", "preferences_lookup"),
    ("what is my favorite programming language", "preferences_lookup"),
    ("what's my favorite editor", "preferences_lookup"),
    ("what projects do you remember", "projects_lookup"),
    ("remember that my favorite color is cyan", "remember_fact"),
    ("remember that my favorite programming language is Python", "remember_fact"),
    ("open weather hud", "hud_overlay"),
    ("close weather hud", "hud_overlay"),
    ("hide weather overlay", "hud_overlay"),
    ("show system monitor", "hud_overlay"),
    ("toggle chat overlay", "hud_overlay"),
    ("open jarvis rings", "hud_overlay"),
    ("open personal os dashboard", "hud_overlay"),
    ("start voice listening", "voice_control"),
    ("stop listening", "voice_control"),
    ("say hello world", "say_phrase"),
    ("speak aloud welcome back", "say_phrase"),
    ("open resume.pdf", "open_file"),
    ("find and open notes.txt", "open_file"),
    ("search my documents for invoice", "rag_query"),
    ("check my resume for skills", "rag_query"),
    ("create a folder called test on desktop", "folder_creation"),
    ("open notepad", "desktop_action"),
    ("open instagram", "desktop_action"),
    ("open intagram", "desktop_action"),
    ("open insta", "desktop_action"),
    ("open youtube", "desktop_action"),
    ("open spotify", "desktop_action"),
    ("open chrome", "desktop_action"),
    ("open volume d", "desktop_action"),
    ("open volume D.", "desktop_action"),
    ("open new volume d", "desktop_action"),
    ("open drive d", "desktop_action"),
    ("open local disk d", "desktop_action"),
    ("open youtube and play music", "autonomous_browser"),
    ("minimize window", "desktop_action"),
    ("search amazon for mechanical keyboard", "autonomous_browser"),
    ("find cheapest flight to tokyo", "autonomous_browser"),
    ("implement a new weather widget component", "provider_chat"),
    ("fix bug in main.py", "provider_chat"),
    ("full system diagnostics", "system_status"),
    ("run full system diagnostics", "system_status"),
    ("system diagnostics", "system_status"),
    ("run system diagnostics", "system_status"),
    ("diagnostics", "system_status"),
    ("run diagnostics", "system_status"),
    ("hardware diagnostics", "system_status"),
    ("run hardware diagnostics", "system_status"),
]

@pytest.mark.parametrize("query,expected_intent", FASTPATH_INTENT_ROUTING_CASES)
def test_fastpath_intent_routing_matrix(router, query, expected_intent):
    """Machine-checked test asserting that all user queries map to the exact expected fastpath intent."""
    intent = router.detect(query)
    assert intent.name == expected_intent, (
        f"Query '{query}' resolved to intent '{intent.name}' (data: {intent.data}), expected '{expected_intent}'"
    )

# ── Local Answer Matrix (Execution & Formatting) ──
@patch("tools.weather_service.LiveWeatherService.get_live_weather")
@patch("tools.battery_service.BatteryDiagnosticsService.get_full_battery_report")
@patch("tools.restart_manager.RestartManager.restart_aura")
@patch("desktop.native.managers.display_helpers.set_display_brightness")
def test_fastpath_execution_matrix(
    mock_brightness, mock_restart, mock_battery, mock_weather, engine
):
    """Machine-checked test asserting that _answer_local_intent returns formatted responses for local intents."""
    # 1. Weather
    mock_weather.return_value = {
        "city": "Bengaluru", "region": "Karnataka", "temp_c": 22,
        "high": 28, "low": 19, "condition": "Clear", "humidity": 60,
        "wind_kmh": 12, "uv": 5, "icon": "🌤️"
    }
    ans = engine._answer_local_intent(Intent("live_weather"))
    assert ans is not None and "Bengaluru" in ans and "22°C" in ans

    # 2. Battery
    mock_battery.return_value = {
        "percent": 75, "power_plugged": True,
        "battery_name": "L19M4PC0", "chemistry": "Li-Ion",
        "power_plan": "Balanced", "runtime_formatted": "AC Connected", "health": "Optimal",
        "markdown": "🔋 **Hardware Power & Battery Diagnostics**\n• Battery Level: 75%\n• Power State: AC Connected"
    }
    ans = engine._answer_local_intent(Intent("battery_status"))
    assert ans is not None and "75%" in ans and "Battery" in ans

    # 3. Brightness
    mock_brightness.return_value = {"success": True, "level": 50, "method": "sbc"}
    ans = engine._answer_local_intent(Intent("brightness_control", {"raw": "set screen brightness to 50%"}))
    assert ans is not None and "50%" in ans

    # 4. Restart
    mock_restart.return_value = "🔄 **AuraAI Graceful Restart Initiated**"
    ans = engine._answer_local_intent(Intent("restart_aura"))
    assert ans is not None and "Restart" in ans

    # 5. Local Time
    ans = engine._answer_local_intent(Intent("local_time"))
    assert ans is not None and ("Time" in ans or ":" in ans or "date" in ans.lower())

    # 6. Profile / Facts Lookup
    ans = engine._answer_local_intent(Intent("profile_lookup"))
    assert ans is not None and "Sreekanta" in ans

    ans = engine._answer_local_intent(Intent("skills_lookup", {"wants_count": False}))
    assert ans is not None and "Python" in ans

    ans = engine._answer_local_intent(Intent("goals_lookup"))
    assert ans is not None and "Complete autonomous assistant" in ans

    ans = engine._answer_local_intent(Intent("preferences_lookup"))
    assert ans is not None and "Dark mode" in ans

    ans = engine._answer_local_intent(Intent("projects_lookup"))
    assert ans is not None and "AuraAI" in ans

    # 7. Memory Summary
    ans = engine._answer_local_intent(Intent("memory_summary"))
    assert ans is not None and ("Profile:" in ans or "Projects:" in ans or "Memory" in ans)

    # 8. Say Phrase
    ans = engine._answer_local_intent(Intent("say_phrase", {"phrase": "Hello Aura"}))
    assert ans is not None and "Hello Aura" in ans

    # 9. Smart Home Bulb Turn On
    ans = engine._answer_local_intent(Intent("smarthome_control", {"raw": "turn on smart light", "normalized": "turn on smart light"}))
    assert ans is not None and ("Smart Bulb" in ans or "Light" in ans or "bulb" in ans.lower())

    # 10. Bluetooth Status
    ans = engine._answer_local_intent(Intent("bluetooth_status"))
    assert ans is not None and "Bluetooth" in ans

    # 11. Wi-Fi Status
    ans = engine._answer_local_intent(Intent("wifi_status"))
    assert ans is not None and ("Wi-Fi" in ans or "wifi" in ans.lower())

    # 12. Network / IP Status
    ans = engine._answer_local_intent(Intent("network_status"))
    assert ans is not None and ("Network" in ans or "Adapter" in ans)

    # 13. System / Hardware Telemetry
    ans = engine._answer_local_intent(Intent("system_status"))
    assert ans is not None and ("System" in ans or "CPU" in ans)

    # 10. HUD Overlay
    ans = engine._answer_local_intent(Intent("hud_overlay", {"overlay_type": "weather_overlay", "raw": "open weather hud", "query": "open weather hud"}))
    assert ans is not None and "Weather HUD" in ans
