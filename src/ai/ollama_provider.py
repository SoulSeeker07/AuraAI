from ai.provider import Provider
from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse


class OllamaProvider(Provider):
    capabilities = ProviderCapabilities(name="ollama", default_model="", supports_streaming=True)

    def chat(self, request: ChatRequest) -> ProviderResponse:
        raise NotImplementedError("Ollama provider is not wired yet.")
