import time
import urllib.request
from pathlib import Path
from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from engineering.preview_server import PreviewServer

def main():
    template_path = Path("src/engineering/templates/starter_app.html")
    assert template_path.exists()
    content = template_path.read_text(encoding="utf-8")

    server = PreviewServer()
    url = server.serve_html(content, "starter_preview.html")
    print(f"Starter App served at: {url}")

    with urllib.request.urlopen(url, timeout=3) as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "AURA CYBER-HUD" in html
        assert "aura-hot-reload" in html
        print("[PASS] Starter App fetched and verified with hot-reload injection.")

    server.stop()
    print("[PASS] Server stopped cleanly.")

if __name__ == "__main__":
    main()
