Aura Service (local)

Run instructions

1. Install dependencies:
   pip install fastapi uvicorn loguru pydantic

2. Run the service:
   python -m apps.service.main

Endpoints

- GET /api/health  -> returns {status: "ok", uptime: <s>}
- WebSocket: ws://{host}:{port}{AURA_WS_PATH} (default /ws) - echoes messages for now

Notes

- Logs are written to logs/service.log
- Configuration via .env or environment variables: AURA_HOST, AURA_PORT, AURA_LOG_LEVEL, AURA_WS_PATH
