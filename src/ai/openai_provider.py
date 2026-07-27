from ai.provider import Provider


class OpenAIProvider(Provider):
    def generate(self, prompt: str) -> str:
        return f"OpenAI response to: {prompt}"
