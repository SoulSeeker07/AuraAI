from core.screen_context import ScreenContext

from Chatbot import get_default_bot


class LocalResponder:
    def __init__(self, screen_context: ScreenContext, live_screen=None):
        self.screen_context = screen_context
        self.live_screen = live_screen
        self.chatbot = get_default_bot()

    def respond(self, prompt: str) -> str:
        normalized = prompt.lower()
        if self._asks_about_screen(normalized):
            if self.live_screen is not None and self.live_screen.is_active:
                latest_path = self.live_screen.latest_frame_path
                if latest_path is not None:
                    return self.chatbot.ask_about_image(prompt, latest_path)

            capture_path = self.screen_context.capture_primary_screen()
            if capture_path is None:
                return (
                    "I heard you, but I could not capture the screen yet.\n\n"
                    "Next step: connect the vision provider so Aura can analyze what you see."
                )

            return self.chatbot.ask_about_image(prompt, capture_path)

        if prompt.startswith(">"):
            return (
                "Command captured.\n\n"
                "The command palette router is scaffolded, but plugin execution is not wired yet."
            )

        return self.chatbot.ask(prompt)

    def _asks_about_screen(self, normalized_prompt: str) -> bool:
        screen_words = ("screen", "desktop", "window", "what am i looking at", "what do you see")
        return any(word in normalized_prompt for word in screen_words)
