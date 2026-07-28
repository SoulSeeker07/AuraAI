import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"
DEFAULTS = {
    "theme": "dark",
    "overlay_hotkey": "alt+space",
}


class Settings:
    def __init__(self, path: Path = SETTINGS_PATH):
        self.path = path
        self.values = DEFAULTS.copy()
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self):
        if not self.path.exists():
            self.save()
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.values.update(data)
        except Exception:
            pass

    def save(self):
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.values, f, indent=2)

    def get(self, key, default=None):
        return self.values.get(key, default)
