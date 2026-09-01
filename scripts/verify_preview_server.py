import urllib.request
from gui.webengine_init import ensure_webengine_flags
ensure_webengine_flags()

from engineering.preview_server import PreviewServer

def main():
    server = PreviewServer()
    url = server.serve_html(
        "<html><body><h1>Aura Webview Verification</h1><script>console.log('Webview live verification');</script></body></html>",
        "verify.html",
    )
    print(f"Server started at: {url}")
    with urllib.request.urlopen(url, timeout=3) as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "Aura Webview Verification" in html
        print("HTTP request successfully fetched preview content.")
    server.stop()
    print("Preview server shutdown cleanly.")

if __name__ == "__main__":
    main()
