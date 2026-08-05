"""Simple HTTP API client for Aura Service using httpx.

This keeps REST separate from the websocket transport.
"""

from __future__ import annotations

import httpx


class ApiClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, timeout: int = 5):
        self.base_url = f"http://{host}:{port}"
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def health(self) -> dict:
        resp = self._client.get("/api/health")
        resp.raise_for_status()
        return resp.json()

    def ready(self) -> dict:
        resp = self._client.get("/api/ready")
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()


if __name__ == "__main__":
    c = ApiClient()
    print(c.health())
    print(c.ready())
    c.close()
