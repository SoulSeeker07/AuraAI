# Local API (Draft)

A local HTTP API and WebSocket will be provided by the AuraService for desktop and overlay clients.

Endpoints (initial):
- GET /api/health
- GET /api/ready
- WS /ws — realtime channel for events and streaming responses

Authentication: local-only by default; future secure token exchange for third-party clients.
