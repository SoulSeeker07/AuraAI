from core.event_bus import Event, EventBus
from core.local_responder import LocalResponder
from core.logger import get_logger

logger = get_logger("overlay_manager")


class OverlayManager:
    def __init__(self, event_bus: EventBus, responder: LocalResponder):
        self.event_bus = event_bus
        self.responder = responder
        self.event_bus.subscribe("overlay.prompt_submitted", self._handle_prompt)

    def _handle_prompt(self, event: Event) -> None:
        prompt = str(event.payload.get("prompt", "")).strip()
        if not prompt:
            return

        logger.info("Overlay prompt submitted")
        self.event_bus.publish("history.prompt", prompt=prompt)
        response = self.responder.respond(prompt)
        self.event_bus.publish("overlay.response", prompt=prompt, response=response)
