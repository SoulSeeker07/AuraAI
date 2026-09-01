from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse, VisionRequest
from ai.provider import Provider

class FakeProvider(Provider):
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0
        self.capabilities = ProviderCapabilities(name="FakeProvider", default_model="fake-model")

    def chat(self, request: ChatRequest, **kwargs) -> ProviderResponse:
        if self.call_count < len(self.responses):

            response_text = self.responses[self.call_count]
            self.call_count += 1
        else:
            response_text = self.responses[-1] if self.responses else ""
            
        return ProviderResponse(
            text=response_text,
            provider="FakeProvider",
            model="fake-model",
        )
