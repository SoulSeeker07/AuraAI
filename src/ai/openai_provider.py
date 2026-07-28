from ai.provider import Provider
from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse


class OpenAIProvider(Provider):
    capabilities = ProviderCapabilities(name="openai", default_model="", supports_streaming=True)

    def chat(self, request: ChatRequest) -> ProviderResponse:
        raise NotImplementedError("OpenAI provider is not wired yet.")
