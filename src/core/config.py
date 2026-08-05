from pathlib import Path

APP_NAME = "Aura"
APP_VERSION = "0.2.0"
ORGANIZATION_NAME = "Aura"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
ASSET_DIR = PROJECT_ROOT / "assets"
DATABASE_DIR = PROJECT_ROOT / "database"
PLUGIN_DIR = PROJECT_ROOT / "plugins"
LOG_DIR = PROJECT_ROOT / "logs"
SCREENSHOT_DIR = LOG_DIR / "screenshots"
SETTINGS_PATH = PROJECT_ROOT / "configs" / "settings.json"

DEFAULT_THEME = "dark"

DEFAULT_HOTKEYS = {
    "overlay": "alt+space",
    "quick_voice": "ctrl+shift+a",
    "clipboard": "ctrl+alt+v",
}

DEFAULT_SETTINGS = {
    "theme": DEFAULT_THEME,
    "ai_provider": "groq",
    "model": "",
    "overlay_hotkey": DEFAULT_HOTKEYS["overlay"],
    "voice_enabled": False,
    "auto_start": False,
    "live_screen_interval_ms": 1500,
    "web_search_enabled": True,
}


def ensure_runtime_dirs() -> None:
    for path in (ASSET_DIR, DATABASE_DIR, PLUGIN_DIR, LOG_DIR, SCREENSHOT_DIR):
        path.mkdir(parents=True, exist_ok=True)
