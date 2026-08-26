import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from core.config import DEFAULT_SETTINGS, SETTINGS_PATH
from core.logger import get_logger

load_dotenv()

logger = get_logger("settings")


class Settings:
    def __init__(self, path: Path = SETTINGS_PATH):
        self.path = path
        self.values = deepcopy(DEFAULT_SETTINGS)
        self.secrets = {
            "groq_api_key": os.getenv("GROQ_API_KEY", ""),
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            "google_api_key": os.getenv("GOOGLE_API_KEY", ""),
        }
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            logger.info("Created default settings at %s", self.path)
            return

        try:
            with self.path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load settings from %s: %s", self.path, exc)
            return

        if isinstance(loaded, dict):
            self.values.update(loaded)
            logger.info("Loaded settings from %s", self.path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(self.values, file, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value
        self.save()
        logger.info("Updated setting: %s", key)

    @property
    def overlay_hotkey(self) -> str:
        return str(self.get("overlay_hotkey", DEFAULT_SETTINGS["overlay_hotkey"]))

    @property
    def live_screen_interval_ms(self) -> int:
        return int(
            self.get(
                "live_screen_interval_ms", DEFAULT_SETTINGS["live_screen_interval_ms"]
            )
        )

    @property
    def ha_url(self) -> str:
        return os.getenv("HASS_URL", os.getenv("HA_URL", str(self.get("ha_url", "http://127.0.0.1:8123"))))

    @property
    def ha_token(self) -> str:
        return os.getenv("HASS_TOKEN", os.getenv("HA_TOKEN", ""))

    @property
    def tapo_username(self) -> str:
        return os.getenv("TAPO_USERNAME", str(self.get("tapo_username", "")))

    @property
    def tapo_password(self) -> str:
        return os.getenv("TAPO_PASSWORD", str(self.get("tapo_password", "")))

    @property
    def tapo_bulb_ip(self) -> str:
        return os.getenv("TAPO_BULB_IP", str(self.get("tapo_bulb_ip", "")))
