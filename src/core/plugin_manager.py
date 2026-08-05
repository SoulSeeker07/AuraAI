import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from core.config import PLUGIN_DIR
from core.event_bus import EventBus
from core.logger import get_logger

logger = get_logger("plugins")


@dataclass
class LoadedPlugin:
    name: str
    path: Path
    version: str = "0.1.0"
    enabled: bool = True
    module: ModuleType | None = None
    instance: Any = None


class PluginManager:
    def __init__(self, event_bus: EventBus, plugin_dir: Path = PLUGIN_DIR):
        self.event_bus = event_bus
        self.plugin_dir = plugin_dir
        self.plugins: dict[str, LoadedPlugin] = {}

    def load_plugins(self) -> None:
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        for plugin_path in sorted(
            path for path in self.plugin_dir.iterdir() if path.is_dir()
        ):
            try:
                plugin = self._load_plugin(plugin_path)
            except Exception:
                logger.exception("Failed to load plugin from %s", plugin_path)
                continue

            if plugin is not None:
                self.plugins[plugin.name] = plugin
                self.event_bus.publish(
                    "plugin.loaded", name=plugin.name, version=plugin.version
                )
                logger.info("Plugin loaded: %s", plugin.name)

    def register(self, plugin: Any, name: str | None = None) -> None:
        plugin_name = name or plugin.__class__.__name__
        self.plugins[plugin_name] = LoadedPlugin(
            name=plugin_name,
            path=self.plugin_dir,
            instance=plugin,
        )
        self.event_bus.publish("plugin.loaded", name=plugin_name, version="runtime")

    def list_plugins(self) -> list[LoadedPlugin]:
        return list(self.plugins.values())

    def _load_plugin(self, plugin_path: Path) -> LoadedPlugin | None:
        manifest = self._read_manifest(plugin_path)
        if not manifest.get("enabled", True):
            logger.info("Plugin disabled: %s", plugin_path.name)
            return None

        entrypoint = manifest.get("entrypoint", "plugin.py")
        module_path = plugin_path / entrypoint
        if not module_path.exists():
            logger.warning("Plugin missing entrypoint: %s", module_path)
            return LoadedPlugin(
                name=manifest.get("name", plugin_path.name),
                path=plugin_path,
                version=manifest.get("version", "0.1.0"),
                enabled=True,
            )

        module = self._import_module(
            manifest.get("name", plugin_path.name), module_path
        )
        instance = None
        if hasattr(module, "setup"):
            instance = module.setup(self.event_bus)

        return LoadedPlugin(
            name=manifest.get("name", plugin_path.name),
            path=plugin_path,
            version=manifest.get("version", "0.1.0"),
            enabled=True,
            module=module,
            instance=instance,
        )

    def _read_manifest(self, plugin_path: Path) -> dict[str, Any]:
        manifest_path = plugin_path / "plugin.json"
        if not manifest_path.exists():
            return {"name": plugin_path.name, "version": "0.1.0", "enabled": True}

        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)

        if not isinstance(manifest, dict):
            raise ValueError(f"Plugin manifest must be an object: {manifest_path}")
        return manifest

    def _import_module(self, plugin_name: str, module_path: Path) -> ModuleType:
        module_key = f"aura_plugin_{plugin_name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_key, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec for {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
