from ai.provider import Provider


class OllamaProvider(Provider):
    def generate(self, prompt: str) -> str:
        return f"Ollama response to: {prompt}"
