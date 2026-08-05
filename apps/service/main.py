"""Entrypoint for Aura Service.

Run with: python -m apps.service.main
Or: python apps/service/main.py
"""

import uvicorn

from .app import create_app
from .config import settings
from .logger import get_logger

log = get_logger("runner")


def run():
    app = create_app()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
