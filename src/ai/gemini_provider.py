from ai.provider import Provider


class GeminiProvider(Provider):
    def generate(self, prompt: str) -> str:
        return f"Gemini response to: {prompt}"
