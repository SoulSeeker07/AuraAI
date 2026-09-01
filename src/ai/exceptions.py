class ProviderError(Exception):
    """Base exception for AI provider failures."""


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider is selected but missing credentials or dependencies."""


class ProviderNotFoundError(ProviderError):
    """Raised when a requested provider is not registered."""


class KeyPoolExhaustedError(ProviderError):
    """Raised when all API keys in the rotation pool are exhausted or rate-limited."""


class GeminiQuotaExhaustedError(ProviderError):
    """Raised when Gemini API quota is exhausted or rate-limited (HTTP 429)."""



