import asyncio
import http.server
import socket
import threading
import time
import pytest
import httpx
from groq import Groq, APITimeoutError
from ai.groq_provider import GroqProvider


class SlowHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        # Intentionally sleep for 2 seconds to simulate slow backend response
        time.sleep(2.0)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"choices": []}')

    def log_message(self, format, *args):
        # Silence server log messages during test
        pass


@pytest.fixture
def slow_server():
    # Find free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = http.server.HTTPServer(("127.0.0.1", port), SlowHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_transport_socket_timeout_unblocks_thread(slow_server):
    """
    Verify that passing timeout to httpx transport layer actually closes the socket
    and unblocks the executing OS thread near timeout seconds.
    """
    client = httpx.Client(timeout=0.4)

    start_time = time.time()
    with pytest.raises(httpx.TimeoutException):
        client.post(f"{slow_server}/chat/completions", json={"model": "test"})
    elapsed = time.time() - start_time

    assert 0.35 <= elapsed < 1.0, f"Expected socket timeout in ~0.4s, took {elapsed:.2f}s"


def test_groq_sdk_client_timeout_unblocks_thread(slow_server):
    """
    Verify that Groq SDK client used by GroqProvider unblocks the executing OS thread
    near timeout seconds via APITimeoutError when passed timeout=0.4.
    """
    groq_client = Groq(
        api_key="gsk_fake_key_for_testing",
        base_url=f"{slow_server}/v1",
        max_retries=0,
    )

    start_time = time.time()
    with pytest.raises(APITimeoutError):
        groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "hello"}],
            timeout=0.4,
        )
    elapsed = time.time() - start_time

    assert 0.35 <= elapsed < 1.2, f"Expected Groq APITimeoutError in ~0.4s, took {elapsed:.2f}s"
