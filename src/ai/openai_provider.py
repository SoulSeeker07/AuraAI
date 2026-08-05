from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse
from ai.provider import Provider


class OpenAIProvider(Provider):
    capabilities = ProviderCapabilities(
        name="openai", default_model="", supports_streaming=True
    )

    def chat(self, request: ChatRequest) -> ProviderResponse:
        raise NotImplementedError("OpenAI provider is not wired yet.")
