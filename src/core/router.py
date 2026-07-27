class Router:
    def __init__(self):
        self.routes = {}

    def add_route(self, name, handler):
        self.routes[name] = handler

    def dispatch(self, name, *args, **kwargs):
        if name in self.routes:
            return self.routes[name](*args, **kwargs)
        raise KeyError(f"Route '{name}' not found")
