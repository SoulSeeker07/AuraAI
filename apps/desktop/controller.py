from PySide6.QtCore import QObject, Signal, Slot, QThread
import asyncio
import threading
import os
import json

try:
    import websockets
except Exception:
    websockets = None


class WebSocketWorker(QThread):
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(str)
    error = Signal(str)

    def __init__(self, host: str = "127.0.0.1", port: int = 8765, path: str = "/ws"):
        super().__init__()
        self.host = host
        self.port = port
        self.path = path
        self._loop = None
        self._ws = None
        self._stop_event = threading.Event()

    def run(self) -> None:
        # Create and run an asyncio loop inside this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception as e:
            self.error.emit(str(e))
        finally:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            self._loop.close()

    async def _main(self):
        if websockets is None:
            self.error.emit("websockets library not available")
            return
        uri = f"ws://{self.host}:{self.port}{self.path}"
        try:
            async with websockets.connect(uri) as ws:
                self._ws = ws
                self.connected.emit()
                while not self._stop_event.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        if msg is None:
                            continue
                        self.message_received.emit(msg)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.disconnected.emit()

    def stop(self):
        self._stop_event.set()
        # Closing the websocket safely
        if self._loop and self._ws:
            try:
                coro = self._ws.close()
                asyncio.run_coroutine_threadsafe(coro, self._loop)
            except Exception:
                pass
        self.wait(timeout=2000)

    def send(self, message: str):
        if not self._loop:
            return
        if not self._ws:
            return
        try:
            coro = self._ws.send(message)
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception as e:
            self.error.emit(str(e))


class DesktopController(QObject):
    connected = Signal(bool)
    status = Signal(str)
    messageReceived = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        host = os.getenv("AURA_HOST", "127.0.0.1")
        port = int(os.getenv("AURA_PORT", "8765"))
        path = os.getenv("AURA_WS_PATH", "/ws")
        self.worker = WebSocketWorker(host=host, port=port, path=path)
        self.worker.connected.connect(self._on_connected)
        self.worker.disconnected.connect(self._on_disconnected)
        self.worker.message_received.connect(self._on_message)
        self.worker.error.connect(self._on_error)

    @Slot()
    def start(self):
        if not websockets:
            self.status.emit("Missing websockets dependency")
            return
        if not self.worker.isRunning():
            self.worker.start()
            self.status.emit("Connecting...")

    @Slot()
    def stop(self):
        if self.worker.isRunning():
            self.worker.stop()
            self.status.emit("Disconnected")

    @Slot(str)
    def send(self, text: str):
        try:
            payload = json.dumps({"type": "message", "text": text})
            self.worker.send(payload)
        except Exception as e:
            self.status.emit(f"Send error: {e}")

    def _on_connected(self):
        self.status.emit("Connected to Aura Service")
        self.connected.emit(True)

    def _on_disconnected(self):
        self.status.emit("Disconnected from Aura Service")
        self.connected.emit(False)

    def _on_message(self, raw: str):
        # Forward raw messages to QML as-is
        self.messageReceived.emit(raw)

    def _on_error(self, text: str):
        self.status.emit(f"Error: {text}")
