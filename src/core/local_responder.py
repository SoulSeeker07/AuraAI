from core.screen_context import ScreenContext


class LocalResponder:
    def __init__(self, screen_context: ScreenContext, live_screen=None):
        self.screen_context = screen_context
        self.live_screen = live_screen

    def respond(self, prompt: str) -> str:
        normalized = prompt.lower()
        if self._asks_about_screen(normalized):
            if self.live_screen is not None and self.live_screen.is_active:
                latest_path = self.live_screen.latest_frame_path
                if latest_path is not None:
                    return (
                        "Live screen mode is active.\n\n"
                        f"Latest frame: {latest_path}\n\n"
                        "Aura is continuously refreshing screen context now. The next upgrade is "
                        "connecting these frames to a vision model for live answers."
                    )

            capture_path = self.screen_context.capture_primary_screen()
            if capture_path is None:
                return (
                    "I heard you, but I could not capture the screen yet.\n\n"
                    "Next step: connect the vision provider so Aura can analyze what you see."
                )

            return (
                "I captured your screen.\n\n"
                f"Saved: {capture_path}\n\n"
                "Vision analysis is not connected yet, so I can't describe it automatically. "
                "That is the next piece to wire into Aura."
            )

        if prompt.startswith(">"):
            return (
                "Command captured.\n\n"
                "The command palette router is scaffolded, but plugin execution is not wired yet."
            )

        return (
            "Prompt captured.\n\n"
            "AI responses are coming next. For now, Aura keeps the overlay open and records "
            "this in the Control Center history."
        )

    def _asks_about_screen(self, normalized_prompt: str) -> bool:
        screen_words = ("screen", "desktop", "window", "what am i looking at", "what do you see")
        return any(word in normalized_prompt for word in screen_words)
