from pathlib import Path
from typing import Any

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


class AuraConfig:
    """Configuration class for AuraAI."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.project_root = self.config.get("project_root", PROJECT_ROOT)
        self.workspace = self.config.get("workspace", str(self.project_root))
        self.groq_api_key = self.config.get("groq_api_key", "")
        self.log_dir = self.config.get("log_dir", LOG_DIR)
        self.memory_enabled = self.config.get("memory_enabled", True)
        self.knowledge_enabled = self.config.get("knowledge_enabled", True)
        self.vision_enabled = self.config.get("vision_enabled", False)
        self.voice_enabled = self.config.get("voice_enabled", False)
        self.plugins_enabled = self.config.get("plugins_enabled", True)
        self.plugin_path = self.config.get("plugin_path", PLUGIN_DIR)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value

    def save(self, config_file: Path):
        import json

        with open(config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    @classmethod
    def load(cls, config_file: Path) -> "AuraConfig":
        import json

        try:
            with open(config_file) as f:
                return cls(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()


log_dir = LOG_DIR


def ensure_runtime_dirs() -> None:
    for path in (ASSET_DIR, DATABASE_DIR, PLUGIN_DIR, LOG_DIR, SCREENSHOT_DIR):
        path.mkdir(parents=True, exist_ok=True)
