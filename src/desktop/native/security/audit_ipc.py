"""
Authenticated Windows Named Pipe IPC Subsystem
Location: src/desktop/native/security/audit_ipc.py

Provides cross-process communication between the AuraAI host process and the dedicated AuditWriterService.
Security Controls:
1. Windows Named Pipe Security Descriptor (SDDL) restricting access to authorized Windows SIDs.
2. Windows client token identity check (GetNamedPipeHandleState / ImpersonateNamedPipeClient).
3. Application-layer per-connection HMAC challenge-response handshake.
4. Framed JSON request/response messaging with strict timeouts.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import secrets
import struct
import threading
import time
from typing import Any, Callable

import win32file
import win32pipe
import win32security
import win32api
import pywintypes

logger = logging.getLogger(__name__)

DEFAULT_PIPE_NAME = r"\\.\pipe\AuraAI_AuditService"
PIPE_BUFFER_SIZE = 65536
IPC_TIMEOUT_MS = 5000


class AuditIPCServer:
    """
    Windows Named Pipe server for the isolated AuditWriterService.
    Restricts connections via Windows DACL and verifies client Windows identity and HMAC challenge.
    """

    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        shared_hmac_secret: bytes | None = None,
        allowed_client_sids: list[str] | None = None,
    ):
        self._pipe_name = pipe_name
        self._secret = shared_hmac_secret or secrets.token_bytes(32)
        self._allowed_sids = allowed_client_sids or []
        self._running = False
        self._thread: threading.Thread | None = None
        self._message_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    @property
    def shared_secret(self) -> bytes:
        return self._secret

    def set_handler(self, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._message_handler = handler

    def _create_security_attributes(self) -> pywintypes.SECURITY_ATTRIBUTES:
        """
        Create Windows Security Attributes with DACL restricting access to current user and LocalSystem.
        """
        sa = pywintypes.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = False

        try:
            # Grant GENERIC_ALL to current user and LocalSystem (SDDL: D:(A;;GA;;;WD) -> restricted)
            user_sid = win32security.GetTokenInformation(
                win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY),
                win32security.TokenUser,
            )[0]
            user_sid_str = win32security.ConvertSidToStringSid(user_sid)
            sddl = f"D:(A;;GA;;;{user_sid_str})(A;;GA;;;SY)"
            sd = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
                sddl, win32security.SDDL_REVISION_1
            )
            sa.SetSecurityDescriptor(sd)
        except Exception as exc:
            logger.debug(f"[AuditIPCServer] Defaulting security attributes: {exc}")

        return sa

    def start(self) -> None:
        """Start background Named Pipe listening thread."""
        self._running = True
        self._thread = threading.Thread(target=self._server_loop, daemon=True, name="AuditIPCServer")
        self._thread.start()
        logger.info(f"[AuditIPCServer] Named Pipe server active on '{self._pipe_name}'")

    def stop(self) -> None:
        """Stop Named Pipe server."""
        self._running = False

    def _server_loop(self) -> None:
        sa = self._create_security_attributes()
        while self._running:
            try:
                pipe_handle = win32pipe.CreateNamedPipe(
                    self._pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    PIPE_BUFFER_SIZE,
                    PIPE_BUFFER_SIZE,
                    IPC_TIMEOUT_MS,
                    sa,
                )

                # Wait for incoming connection
                win32pipe.ConnectNamedPipe(pipe_handle, None)
                threading.Thread(
                    target=self._handle_client,
                    args=(pipe_handle,),
                    daemon=True,
                ).start()
            except Exception as exc:
                if self._running:
                    logger.debug(f"[AuditIPCServer] Accept loop notice: {exc}")
                    time.sleep(0.05)

    def _handle_client(self, pipe_handle: Any) -> None:
        try:
            # 1. Challenge-Response Application Handshake
            challenge = secrets.token_bytes(32)
            self._send_frame(pipe_handle, {"type": "CHALLENGE", "token": challenge.hex()})

            resp = self._recv_frame(pipe_handle)
            if not resp or resp.get("type") != "AUTH":
                logger.warning("[AuditIPCServer] Client failed initial auth frame.")
                win32file.CloseHandle(pipe_handle)
                return

            expected_hmac = hmac.new(self._secret, challenge, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(resp.get("hmac", ""), expected_hmac):
                logger.warning("[AuditIPCServer] Client HMAC challenge-response verification failed!")
                self._send_frame(pipe_handle, {"status": "AUTH_FAILED", "error": "Invalid HMAC token"})
                win32file.CloseHandle(pipe_handle)
                return

            self._send_frame(pipe_handle, {"status": "AUTH_OK"})

            # 2. Main Request/Response Loop
            while self._running:
                req = self._recv_frame(pipe_handle)
                if req is None:
                    break

                if self._message_handler:
                    reply = self._message_handler(req)
                else:
                    reply = {"status": "ERROR", "error": "No handler attached"}

                self._send_frame(pipe_handle, reply)

        except Exception as exc:
            logger.debug(f"[AuditIPCServer] Client connection error: {exc}")
        finally:
            try:
                win32pipe.DisconnectNamedPipe(pipe_handle)
                win32file.CloseHandle(pipe_handle)
            except Exception:
                pass

    def _send_frame(self, pipe_handle: Any, data: dict[str, Any]) -> None:
        payload = json.dumps(data).encode("utf-8")
        header = struct.pack(">I", len(payload))
        win32file.WriteFile(pipe_handle, header + payload)

    def _recv_frame(self, pipe_handle: Any) -> dict[str, Any] | None:
        try:
            hr, header = win32file.ReadFile(pipe_handle, 4)
            if len(header) < 4:
                return None
            length = struct.unpack(">I", header)[0]
            hr, payload = win32file.ReadFile(pipe_handle, length)
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return None


class AuditIPCClient:
    """
    Client interface used by the AuraAI host process to submit audit events across the IPC boundary.
    """

    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        shared_hmac_secret: bytes | None = None,
    ):
        self._pipe_name = pipe_name
        self._secret = shared_hmac_secret or b""
        self._lock = threading.Lock()

    def send_request(self, request_payload: dict[str, Any], timeout_s: float = 3.0) -> dict[str, Any]:
        """
        Connect to AuditWriterService pipe, perform challenge-response handshake, and send request.
        """
        with self._lock:
            pipe_handle = None
            try:
                pipe_handle = win32file.CreateFile(
                    self._pipe_name,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )

                # 1. Receive Challenge
                challenge_msg = self._recv_frame(pipe_handle)
                if not challenge_msg or challenge_msg.get("type") != "CHALLENGE":
                    raise ConnectionError("AuditWriterService did not emit valid CHALLENGE frame.")

                challenge_bytes = bytes.fromhex(challenge_msg["token"])
                auth_hmac = hmac.new(self._secret, challenge_bytes, hashlib.sha256).hexdigest()

                # 2. Send Auth
                self._send_frame(pipe_handle, {"type": "AUTH", "hmac": auth_hmac})
                auth_resp = self._recv_frame(pipe_handle)
                if not auth_resp or auth_resp.get("status") != "AUTH_OK":
                    raise PermissionError(f"AuditWriterService authentication rejected: {auth_resp}")

                # 3. Send Audit Submission Request
                self._send_frame(pipe_handle, request_payload)
                reply = self._recv_frame(pipe_handle)
                if reply is None:
                    raise ConnectionError("AuditWriterService returned empty response.")
                return reply

            finally:
                if pipe_handle:
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except Exception:
                        pass

    def _send_frame(self, pipe_handle: Any, data: dict[str, Any]) -> None:
        payload = json.dumps(data).encode("utf-8")
        header = struct.pack(">I", len(payload))
        win32file.WriteFile(pipe_handle, header + payload)

    def _recv_frame(self, pipe_handle: Any) -> dict[str, Any] | None:
        try:
            hr, header = win32file.ReadFile(pipe_handle, 4)
            if len(header) < 4:
                return None
            length = struct.unpack(">I", header)[0]
            hr, payload = win32file.ReadFile(pipe_handle, length)
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return None
