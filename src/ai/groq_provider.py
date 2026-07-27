from ai.provider import Provider


class GroqProvider(Provider):
    def generate(self, prompt: str) -> str:
        return f"Groq response to: {prompt}"
