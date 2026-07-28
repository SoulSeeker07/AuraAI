class ProviderError(Exception):
    """Base exception for AI provider failures."""


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider is selected but missing credentials or dependencies."""


class ProviderNotFoundError(ProviderError):
    """Raised when a requested provider is not registered."""
