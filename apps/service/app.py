from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router as api_router
from .ws_manager import WebSocketManager
from .ws_routes import set_manager, router as ws_router
from .logger import get_logger

log = get_logger("app")


def create_app() -> FastAPI:
    app = FastAPI(title="Aura Service", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # include HTTP routes
    app.include_router(api_router, prefix="/api")

    # create and attach websocket manager
    manager = WebSocketManager()
    set_manager(manager)

    # expose manager on app.state so other components can access it
    app.state.ws_manager = manager

    # include websocket routes (uses global manager reference)
    app.include_router(ws_router)

    @app.on_event("startup")
    async def startup_event():
        log.info("Aura Service starting up")

    @app.on_event("shutdown")
    async def shutdown_event():
        log.info("Aura Service shutting down")

    return app
