"""
Tests for Frontend Preview Staging Server
=========================================
Location: tests/engineering/test_preview_server.py
"""

import urllib.request
from pathlib import Path
import pytest

from engineering.preview_server import PreviewServer, get_preview_server


@pytest.fixture
def preview_server(tmp_path):
    staging_dir = tmp_path / "staging_preview"
    server = PreviewServer(staging_dir=staging_dir, preferred_port=8910)
    server.start()
    yield server
    server.stop()


def test_preview_server_lifecycle(preview_server):
    assert preview_server.is_running
    assert preview_server.base_url.startswith("http://127.0.0.1:")

    # Test serving HTML
    sample_html = "<html><body><h1>Aura Test</h1></body></html>"
    url = preview_server.serve_html(sample_html, "test.html")
    assert url == f"{preview_server.base_url}/test.html"

    # Fetch served content via HTTP
    req = urllib.request.Request(url, headers={"User-Agent": "AuraTest/1.0"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "<h1>Aura Test</h1>" in content
        assert "aura-hot-reload" in content

    # Test stopping
    preview_server.stop()
    assert not preview_server.is_running


def test_singleton_get_preview_server():
    s1 = get_preview_server()
    s2 = get_preview_server()
    assert s1 is s2
    assert s1.staging_dir.name == "preview"
