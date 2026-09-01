"""
Frontend Preview Staging Server
===============================
Location: src/engineering/preview_server.py

Zero-latency, lightweight local HTTP staging server serving rendered HTML/JSX/CSS
artifacts from an isolated staging directory (.aura_staging/preview/) on a background thread.
"""

from __future__ import annotations

import functools
import http.server
import logging
import os
import socket
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default hot-reload client script injected into HTML preview documents
HOT_RELOAD_SCRIPT = """
<script id="aura-hot-reload">
(function() {
    let lastModified = 0;
    const pollInterval = 400;
    function checkUpdate() {
        fetch(window.location.href, { method: 'HEAD', cache: 'no-store' })
            .then(res => {
                const cur = res.headers.get('last-modified') || res.headers.get('etag');
                if (cur && lastModified && cur !== lastModified) {
                    window.location.reload();
                }
                lastModified = cur || lastModified;
            })
            .catch(() => {})
            .finally(() => setTimeout(checkUpdate, pollInterval));
    }
    setTimeout(checkUpdate, pollInterval);
})();
</script>
"""


class PreviewHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler with CORS support and hot-reload injection."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self):
        # Enable CORS for local cross-origin asset loading
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging in stdout
        logger.debug(f"[PreviewServer] {self.address_string()} - {format % args}")


class PreviewServer:
    """
    Lifecycle manager for the isolated frontend staging HTTP server.
    """

    def __init__(
        self,
        staging_dir: Optional[Path | str] = None,
        host: str = "127.0.0.1",
        preferred_port: int = 8765,
    ) -> None:
        if staging_dir is None:
            # Default to .aura_staging/preview/ relative to project root
            project_root = Path(__file__).resolve().parents[2]
            self.staging_dir = project_root / ".aura_staging" / "preview"
        else:
            self.staging_dir = Path(staging_dir).resolve()

        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.host = host
        self.preferred_port = preferred_port
        self.port = preferred_port
        self._server: Optional[http.server.ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _find_available_port(self) -> int:
        """Finds preferred port or dynamic fallback port."""
        for port in range(self.preferred_port, self.preferred_port + 50):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((self.host, port))
                    return port
                except OSError:
                    continue
        # Fallback to OS assigned random free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, 0))
            return s.getsockname()[1]

    def start(self) -> str:
        """Starts the background preview server if not already running."""
        if self._is_running and self._server:
            return self.base_url

        self.port = self._find_available_port()
        handler = functools.partial(PreviewHTTPRequestHandler, directory=str(self.staging_dir))

        self._server = http.server.ThreadingHTTPServer((self.host, self.port), handler)
        self._server.daemon_threads = True

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="AuraPreviewServerThread",
            daemon=True,
        )
        self._thread.start()
        self._is_running = True
        logger.info(f"[PreviewServer] Started local preview server at {self.base_url} (serving {self.staging_dir})")
        return self.base_url

    def stop(self) -> None:
        """Gracefully shuts down the background preview server."""
        if not self._is_running or not self._server:
            return

        logger.info("[PreviewServer] Shutting down preview server...")
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception as e:
            logger.warning(f"[PreviewServer] Error closing server: {e}")
        finally:
            self._is_running = False
            self._server = None
            self._thread = None

    def serve_html(self, html_content: str, filename: str = "index.html", inject_hot_reload: bool = True) -> str:
        """
        Writes HTML content to the staging directory and returns the live preview URL.
        """
        if not self._is_running:
            self.start()

        if inject_hot_reload and "aura-hot-reload" not in html_content:
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{HOT_RELOAD_SCRIPT}\n</body>")
            elif "</html>" in html_content:
                html_content = html_content.replace("</html>", f"{HOT_RELOAD_SCRIPT}\n</html>")
            else:
                html_content = f"{html_content}\n{HOT_RELOAD_SCRIPT}"

        target_file = self.staging_dir / filename
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(html_content, encoding="utf-8")

        return f"{self.base_url}/{filename}"

    def get_file_path(self, filename: str = "index.html") -> Path:
        return self.staging_dir / filename


# Global default preview server singleton
_default_preview_server: Optional[PreviewServer] = None


def get_preview_server() -> PreviewServer:
    global _default_preview_server
    if _default_preview_server is None:
        _default_preview_server = PreviewServer()
    return _default_preview_server
