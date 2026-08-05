from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse
from ai.provider import Provider


class GeminiProvider(Provider):
    capabilities = ProviderCapabilities(
        name="gemini", default_model="", supports_streaming=True
    )

    def chat(self, request: ChatRequest) -> ProviderResponse:
        raise NotImplementedError("Gemini provider is not wired yet.")
