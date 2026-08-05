"""
Configuration module for AuraAI

Contains configuration classes and settings.
"""

from pathlib import Path
from typing import Any


class AuraConfig:
    """
    Configuration class for AuraAI.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize configuration.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Default settings
        self.project_root = self.config.get(
            "project_root", Path(__file__).resolve().parent.parent
        )
        self.workspace = self.config.get("workspace", str(self.project_root))
        self.groq_api_key = self.config.get("groq_api_key", "")

        # Logging settings
        self.log_dir = self.config.get("log_dir", self.project_root / "logs")

        # Component settings
        self.memory_enabled = self.config.get("memory_enabled", True)
        self.knowledge_enabled = self.config.get("knowledge_enabled", True)
        self.vision_enabled = self.config.get("vision_enabled", False)
        self.voice_enabled = self.config.get("voice_enabled", False)
        self.plugins_enabled = self.config.get("plugins_enabled", True)

        # Plugin settings
        self.plugin_path = self.config.get(
            "plugin_path", Path(__file__).parent.parent / "plugins"
        )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value

    def save(self, config_file: Path):
        """
        Save configuration to a file.

        Args:
            config_file: Path to configuration file
        """
        import json

        with open(config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    @classmethod
    def load(cls, config_file: Path) -> "AuraConfig":
        """
        Load configuration from a file.

        Args:
            config_file: Path to configuration file

        Returns:
            AuraConfig instance
        """
        import json

        try:
            with open(config_file) as f:
                config_data = json.load(f)
            return cls(config_data)
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()


# Module-level LOG_DIR for import
LOG_DIR = AuraConfig().log_dir
log_dir = LOG_DIR
