from backend.core.logger import get_logger

logger = get_logger("service_manager")


class ServiceManager:
    def __init__(self):
        self._services: list = []

    def register(self, service):
        self._services.append(service)

    def start_all(self):
        for s in self._services:
            try:
                if hasattr(s, "start"):
                    s.start()
            except Exception:
                logger.exception("Failed to start service: %s", s)

    def stop_all(self):
        for s in reversed(self._services):
            try:
                if hasattr(s, "stop"):
                    s.stop()
            except Exception:
                logger.exception("Failed to stop service: %s", s)
