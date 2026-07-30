"""
Configuration Management - Centralized settings for the agent system.

The Configuration System provides:
- Provider keys (OpenAI, Groq, etc.)
- Model settings
- Plugin toggles
- Permission rules
- Logging settings
- Performance tuning
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ProviderType(Enum):
    """Types of AI providers."""
    OPENAI = "openai"
    GROQ = "groq"
    OLLAMA = "ollama"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"


@dataclass
class ModelSettings:
    """Settings for AI model usage."""
    provider: ProviderType
    model_name: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 30
    enabled: bool = True


@dataclass
class PluginSettings:
    """Settings for plugin system."""
    auto_load: bool = True
    load_directory: str = "plugins"
    enabled_plugins: List[str] = field(default_factory=list)
    disabled_plugins: List[str] = field(default_factory=list)


@dataclass
class SafetySettings:
    """Settings for safety layer."""
    require_confirmation: bool = True
    confirmation_timeout_seconds: int = 30
    destructive_operations_only: bool = True
    critical_operations_only: bool = True
    permission_checks_enabled: bool = True


@dataclass
class LoggingSettings:
    """Settings for logging."""
    level: str = "INFO"
    log_file: Optional[str] = None
    log_format: str = "json"  # or "text"
    max_log_size_mb: int = 10
    backup_count: int = 5


@dataclass
class PerformanceSettings:
    """Settings for performance tuning."""
    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 300
    queue_size: int = 100
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    memory_limit_mb: int = 512


@dataclass
class ResearchSettings:
    """Settings for research agent."""
    max_search_results: int = 10
    deep_research_depth: int = 3
    enable_citations: bool = True
    use_cache: bool = True


@dataclass
class Configuration:
    """
    Central configuration for the agent system.

    Provides access to all configuration settings.
    """
    # Provider settings
    providers: Dict[ProviderType, ModelSettings] = field(default_factory=dict)

    # Plugin settings
    plugins: PluginSettings = field(default_factory=PluginSettings)

    # Safety settings
    safety: SafetySettings = field(default_factory=SafetySettings)

    # Logging settings
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    # Performance settings
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)

    # Research settings
    research: ResearchSettings = field(default_factory=ResearchSettings)

    # Custom settings
    custom: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default provider settings."""
        if not self.providers:
            # Add default OpenAI configuration
            self.providers[ProviderType.OPENAI] = ModelSettings(
                provider=ProviderType.OPENAI,
                model_name="gpt-4",
                enabled=True
            )

    def get_provider_key(self, provider: ProviderType) -> Optional[str]:
        """Get API key for a provider."""
        if provider not in self.providers:
            return None

        model_settings = self.providers[provider]
        return self.custom.get(f"{provider.value}_api_key")

    def set_provider_key(self, provider: ProviderType, api_key: str):
        """Set API key for a provider."""
        self.custom[f"{provider.value}_api_key"] = api_key

    def get_model_settings(self, provider: ProviderType) -> Optional[ModelSettings]:
        """Get model settings for a provider."""
        return self.providers.get(provider)

    def set_model_settings(self, provider: ProviderType, settings: ModelSettings):
        """Set model settings for a provider."""
        self.providers[provider] = settings

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """Check if a plugin is enabled."""
        # If explicitly disabled, return False
        if plugin_name in self.plugins.disabled_plugins:
            return False

        # If explicitly enabled, return True
        if plugin_name in self.plugins.enabled_plugins:
            return True

        # Otherwise, follow auto_load setting
        return self.plugins.auto_load

    def is_operation_destructive(self, operation: str) -> bool:
        """Check if an operation is destructive."""
        return self.safety.destructive_operations_only or operation in [
            "file_delete", "file_move", "file_rename", "file_overwrite",
            "application_close", "system_shutdown", "system_restart"
        ]


class ConfigManager:
    """
    Manages configuration settings.

    Features:
    - Configuration loading
    - Configuration saving
    - Configuration validation
    - Default configuration
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the config manager.

        Args:
            config_path: Path to config file
        """
        self._config_path = config_path
        self._config: Configuration = Configuration()
        self._loaded = False

    def load_config(self, config_path: Optional[str] = None) -> bool:
        """
        Load configuration from file.

        Args:
            config_path: Path to config file

        Returns:
            True if loaded successfully
        """
        if config_path:
            self._config_path = config_path

        if not self._config_path:
            return False

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._config = Configuration(**data)

            self._loaded = True
            return True

        except Exception:
            return False

    def save_config(self, config_path: Optional[str] = None) -> bool:
        """
        Save configuration to file.

        Args:
            config_path: Path to save config file

        Returns:
            True if saved successfully
        """
        save_path = config_path or self._config_path

        if not save_path:
            return False

        try:
            data = {
                "providers": {
                    key.value: {
                        "provider": val.provider.value,
                        "model_name": val.model_name,
                        "temperature": val.temperature,
                        "max_tokens": val.max_tokens,
                        "timeout_seconds": val.timeout_seconds,
                        "enabled": val.enabled
                    }
                    for key, val in self._config.providers.items()
                },
                "plugins": {
                    "auto_load": self._config.plugins.auto_load,
                    "load_directory": self._config.plugins.load_directory,
                    "enabled_plugins": self._config.plugins.enabled_plugins,
                    "disabled_plugins": self._config.plugins.disabled_plugins
                },
                "safety": {
                    "require_confirmation": self._config.safety.require_confirmation,
                    "confirmation_timeout_seconds": self._config.safety.confirmation_timeout_seconds,
                    "destructive_operations_only": self._config.safety.destructive_operations_only,
                    "critical_operations_only": self._config.safety.critical_operations_only,
                    "permission_checks_enabled": self._config.safety.permission_checks_enabled
                },
                "logging": {
                    "level": self._config.logging.level,
                    "log_file": self._config.logging.log_file,
                    "log_format": self._config.logging.log_format,
                    "max_log_size_mb": self._config.logging.max_log_size_mb,
                    "backup_count": self._config.logging.backup_count
                },
                "performance": {
                    "max_concurrent_tasks": self._config.performance.max_concurrent_tasks,
                    "task_timeout_seconds": self._config.performance.task_timeout_seconds,
                    "queue_size": self._config.performance.queue_size,
                    "enable_caching": self._config.performance.enable_caching,
                    "cache_ttl_seconds": self._config.performance.cache_ttl_seconds,
                    "memory_limit_mb": self._config.performance.memory_limit_mb
                },
                "research": {
                    "max_search_results": self._config.research.max_search_results,
                    "deep_research_depth": self._config.research.deep_research_depth,
                    "enable_citations": self._config.research.enable_citations,
                    "use_cache": self._config.research.use_cache
                }
            }

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            return True

        except Exception:
            return False

    def get_config(self) -> Configuration:
        """Get current configuration."""
        return self._config

    def update_setting(self, category: str, key: str, value: Any):
        """Update a configuration setting."""
        if category == "custom":
            self._config.custom[key] = value
        elif hasattr(self._config, category):
            category_obj = getattr(self._config, category)
            if isinstance(category_obj, dict):
                category_obj[key] = value
            else:
                setattr(category_obj, key, value)

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self._config = Configuration()
        self._loaded = False


# Global config manager instance
_global_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get global config manager instance."""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager
