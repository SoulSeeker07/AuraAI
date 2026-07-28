from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse, VisionRequest


class Provider(ABC):
    capabilities: ProviderCapabilities

    @abstractmethod
    def chat(self, request: ChatRequest) -> ProviderResponse:
        raise NotImplementedError

    def stream(self, request: ChatRequest) -> Iterable[str]:
        yield self.chat(request).text

    def vision(self, request: VisionRequest) -> ProviderResponse:
        raise NotImplementedError("This provider does not support vision.")
