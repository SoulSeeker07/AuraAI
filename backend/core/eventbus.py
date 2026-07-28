from collections import defaultdict


class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)

    def subscribe(self, name: str, callback):
        self._listeners[name].append(callback)

    def publish(self, name: str, **payload):
        for cb in list(self._listeners.get(name, [])):
            try:
                cb(payload)
            except Exception:
                pass
