"""
Speech Manager — Text-to-Speech Native Windows Manager
Location: src/desktop/native/managers/speech_manager.py

Provides text-to-speech capabilities via pyttsx3 (SAPI.SpVoice COM wrapper)
with a graceful native PowerShell System.Speech fallback.
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import threading
from typing import Any

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# Optional dependency: pyttsx3
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    pyttsx3 = None  # type: ignore[assignment]
    HAS_PYTTSX3 = False


class SpeechManager(BaseNativeManager):
    """
    Manages text-to-speech (TTS) on Windows using pyttsx3 with PowerShell fallback.

    Capabilities:
    - speech.say: Speak text asynchronously in background daemon thread
    - speech.list_voices: Enumerate available TTS voices
    - speech.set_voice: Set active voice by ID or name
    - speech.set_rate: Set speech rate (words per minute, default ~200)
    - speech.set_volume: Set speech volume (0.0 to 1.0)
    - speech.stop: Stop active speech immediately
    """

    NAME = "speech"
    VERSION = "1.0"
    PRIORITY = 30
    DEPENDENCIES: list[str] = []

    CAPABILITIES: list[str] = [
        "speech.say",
        "speech.list_voices",
        "speech.set_voice",
        "speech.set_rate",
        "speech.set_volume",
        "speech.stop",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._engine: Any = None
        self._use_fallback: bool = not HAS_PYTTSX3
        self._current_voice: str | None = None
        self._rate: int = 200
        self._volume: float = 1.0
        self._is_speaking: bool = False

        self._engine_lock = threading.Lock()
        self._speak_lock = threading.Lock()
        self._process_lock = threading.Lock()

        self._current_process: subprocess.Popen[str] | None = None
        self._speech_thread: threading.Thread | None = None
        self._capabilities = list(self.CAPABILITIES)
        self._initialized: bool = False

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by SpeechManager."""
        return list(self.CAPABILITIES)

    def initialize(self) -> bool:
        """
        Initialize speech manager and lazy-load TTS engine if available.

        Returns:
            True if initialization succeeded.
        """
        self._initialized = True
        if HAS_PYTTSX3 and not self._use_fallback:
            self._get_engine()
        return True

    def health_check(self) -> HealthCheckResult:
        """
        Check health of SpeechManager and available TTS backends.

        Returns:
            HealthCheckResult with engine and fallback diagnostics.
        """
        active_backend = "powershell" if self._use_fallback or not HAS_PYTTSX3 else "pyttsx3"
        missing: list[str] = []
        if not HAS_PYTTSX3:
            missing.append("pyttsx3")

        fallbacks = ["powershell"] if (not HAS_PYTTSX3 or self._use_fallback) else []

        status = HealthStatus.HEALTHY

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=fallbacks,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={
                "initialized": self._initialized,
                "pyttsx3_available": HAS_PYTTSX3,
                "using_fallback": self._use_fallback,
                "active_backend": active_backend,
                "current_voice": self._current_voice,
                "rate": self._rate,
                "volume": self._volume,
                "is_speaking": self._is_speaking,
            },
        )

    def shutdown(self) -> None:
        """Shutdown speech manager, stopping active speech and releasing resources."""
        self._stop_speech()
        with self._engine_lock:
            if self._engine is not None:
                try:
                    self._engine.stop()
                except Exception as exc:
                    logger.debug(f"Error while stopping pyttsx3 during shutdown: {exc}")
                self._engine = None
        self._initialized = False

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        """
        Execute native speech operation for the given capability.

        Args:
            capability: Capability name (e.g., 'speech.say', 'speech.list_voices')
            goal: Original goal or task description
            arguments: Dictionary of arguments
            **kwargs: Extra arguments passed to operation

        Returns:
            DesktopResult indicating success or failure.
        """
        args = arguments or {}
        args.update(kwargs)
        cap = capability.lower().strip()

        try:
            if cap in ("speech.say", "say"):
                return self._handle_say(goal=goal, capability=capability, arguments=args)
            elif cap in ("speech.list_voices", "speech.voices", "list_voices", "voices"):
                return self._handle_list_voices(goal=goal, capability=capability, arguments=args)
            elif cap in ("speech.set_voice", "set_voice"):
                return self._handle_set_voice(goal=goal, capability=capability, arguments=args)
            elif cap in ("speech.set_rate", "set_rate"):
                return self._handle_set_rate(goal=goal, capability=capability, arguments=args)
            elif cap in ("speech.set_volume", "set_volume"):
                return self._handle_set_volume(goal=goal, capability=capability, arguments=args)
            elif cap in ("speech.stop", "stop"):
                return self._handle_stop(goal=goal, capability=capability, arguments=args)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported capability: {capability}",
                )
        except Exception as exc:
            logger.error(f"SpeechManager.{cap} failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Operation failed: {exc}",
            )

    # ==================== Handlers ====================

    def _handle_say(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """Handle speech.say capability."""
        text = (
            arguments.get("text")
            or arguments.get("message")
            or arguments.get("content")
            or goal
            or ""
        )
        if isinstance(text, str):
            text = text.strip()
        else:
            text = str(text).strip()

        if not text:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="No text provided to speak (missing 'text' argument).",
            )

        voice = (
            arguments.get("voice_id")
            or arguments.get("voice_name")
            or arguments.get("voice")
        )
        rate_arg = arguments.get("rate")
        volume_arg = arguments.get("volume")
        wait = bool(arguments.get("wait") or arguments.get("block", False))

        rate: int | None = None
        if rate_arg is not None:
            try:
                rate = max(50, min(400, int(rate_arg)))
            except (ValueError, TypeError):
                rate = None

        volume: float | None = None
        if volume_arg is not None:
            try:
                v = float(volume_arg)
                if v > 1.0 and v <= 100.0:
                    v = v / 100.0
                volume = max(0.0, min(1.0, v))
            except (ValueError, TypeError):
                volume = None

        # Stop prior speech before starting new speech
        self._stop_speech()

        thread = threading.Thread(
            target=self._speak_worker,
            args=(text, voice, rate, volume),
            daemon=True,
            name="SpeechManager-Worker",
        )
        self._speech_thread = thread
        thread.start()

        if wait:
            thread.join()

        backend = "powershell" if self._use_fallback or not HAS_PYTTSX3 else "pyttsx3"
        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "text": text,
                "voice": voice or self._current_voice,
                "rate": rate if rate is not None else self._rate,
                "volume": volume if volume is not None else self._volume,
                "backend": backend,
                "async": not wait,
            },
            events=["speech_completed" if wait else "speech_started"],
        )

    def _handle_list_voices(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """Handle speech.list_voices capability."""
        voices_data: list[dict[str, Any]] = []
        backend = "pyttsx3"

        engine = self._get_engine()
        if engine is not None and not self._use_fallback:
            try:
                voices = engine.getProperty("voices")
                if voices:
                    for v in voices:
                        voices_data.append(
                            {
                                "id": getattr(v, "id", ""),
                                "name": getattr(v, "name", ""),
                                "gender": getattr(v, "gender", None),
                                "age": getattr(v, "age", None),
                                "languages": getattr(v, "languages", []),
                            }
                        )
            except Exception as exc:
                logger.warning(
                    f"pyttsx3 getProperty('voices') failed ({exc}); falling back to PowerShell."
                )
                self._use_fallback = True

        if not voices_data or self._use_fallback:
            backend = "powershell"
            voices_data = self._list_voices_powershell()

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "voices": voices_data,
                "count": len(voices_data),
                "backend": backend,
            },
            events=["voices_listed"],
        )

    def _handle_set_voice(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """Handle speech.set_voice capability."""
        voice = (
            arguments.get("voice_id")
            or arguments.get("voice_name")
            or arguments.get("voice")
        )
        if not voice:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Missing required argument 'voice_id' or 'voice_name'.",
            )

        self._current_voice = str(voice)
        backend = "powershell"
        engine = self._get_engine()

        if engine is not None and not self._use_fallback:
            try:
                resolved_id = self._resolve_voice_id_pyttsx3(engine, self._current_voice)
                engine.setProperty("voice", resolved_id)
                backend = "pyttsx3"
            except Exception as exc:
                logger.warning(f"pyttsx3 setProperty('voice') failed: {exc}")
                self._use_fallback = True

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "voice": self._current_voice,
                "backend": backend,
            },
            events=["voice_changed"],
        )

    def _handle_set_rate(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """Handle speech.set_rate capability."""
        rate_val = arguments.get("rate")
        if rate_val is None:
            rate_val = arguments.get("wpm", 200)

        try:
            rate = int(rate_val)
        except (ValueError, TypeError):
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Invalid rate value: {rate_val}. Must be an integer.",
            )

        rate = max(50, min(400, rate))
        self._rate = rate
        backend = "powershell"
        engine = self._get_engine()

        if engine is not None and not self._use_fallback:
            try:
                engine.setProperty("rate", self._rate)
                backend = "pyttsx3"
            except Exception as exc:
                logger.warning(f"pyttsx3 setProperty('rate') failed: {exc}")
                self._use_fallback = True

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "rate": self._rate,
                "backend": backend,
            },
            events=["rate_changed"],
        )

    def _handle_set_volume(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """Handle speech.set_volume capability."""
        vol_val = arguments.get("volume")
        if vol_val is None:
            vol_val = arguments.get("vol")

        if vol_val is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Missing required argument 'volume' (float between 0.0 and 1.0).",
            )

        try:
            volume = float(vol_val)
        except (ValueError, TypeError):
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Invalid volume value: {vol_val}. Must be a float between 0.0 and 1.0.",
            )

        if volume > 1.0 and volume <= 100.0:
            volume = volume / 100.0
        volume = max(0.0, min(1.0, volume))
        self._volume = volume

        backend = "powershell"
        engine = self._get_engine()

        if engine is not None and not self._use_fallback:
            try:
                engine.setProperty("volume", self._volume)
                backend = "pyttsx3"
            except Exception as exc:
                logger.warning(f"pyttsx3 setProperty('volume') failed: {exc}")
                self._use_fallback = True

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "volume": self._volume,
                "backend": backend,
            },
            events=["volume_changed"],
        )

    def _handle_stop(
        self,
        goal: str,
        capability: str,
        arguments: dict[str, Any],
    ) -> DesktopResult:
        """Handle speech.stop capability."""
        was_speaking = self._is_speaking
        self._stop_speech()

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data={
                "stopped": True,
                "was_speaking": was_speaking,
            },
            events=["speech_stopped"],
        )

    # ==================== Internal TTS Engine Helpers ====================

    def _get_engine(self) -> Any:
        """
        Get or lazy-initialize pyttsx3 engine.
        Sets _use_fallback to True if pyttsx3 is unavailable or initialization fails.
        """
        if self._engine is not None:
            return self._engine

        if not HAS_PYTTSX3 or self._use_fallback:
            self._use_fallback = True
            return None

        with self._engine_lock:
            if self._engine is not None:
                return self._engine
            try:
                engine = pyttsx3.init()
                if self._rate is not None:
                    engine.setProperty("rate", self._rate)
                if self._volume is not None:
                    engine.setProperty("volume", self._volume)
                if self._current_voice:
                    resolved_id = self._resolve_voice_id_pyttsx3(engine, self._current_voice)
                    engine.setProperty("voice", resolved_id)
                self._engine = engine
                self._use_fallback = False
                return self._engine
            except Exception as exc:
                logger.warning(
                    f"Failed to initialize pyttsx3 engine ({exc}); switching to PowerShell TTS fallback."
                )
                self._engine = None
                self._use_fallback = True
                return None

    def _resolve_voice_id_pyttsx3(self, engine: Any, voice_query: str) -> str:
        """Resolve a voice name or ID to a matching pyttsx3 voice ID."""
        try:
            voices = engine.getProperty("voices")
            if voices:
                query_lower = voice_query.lower()
                # 1. Exact match on ID or Name
                for v in voices:
                    vid = getattr(v, "id", "")
                    vname = getattr(v, "name", "")
                    if vid == voice_query or vname.lower() == query_lower:
                        return vid
                # 2. Substring match
                for v in voices:
                    vid = getattr(v, "id", "")
                    vname = getattr(v, "name", "")
                    if query_lower in vname.lower() or query_lower in vid.lower():
                        return vid
        except Exception as exc:
            logger.debug(f"Error resolving pyttsx3 voice query '{voice_query}': {exc}")
        return voice_query

    def _speak_worker(
        self,
        text: str,
        voice: str | None = None,
        rate: int | None = None,
        volume: float | None = None,
    ) -> None:
        """Worker executing text-to-speech in a background daemon thread."""
        with self._speak_lock:
            self._is_speaking = True
            try:
                engine = self._get_engine()
                if engine is not None and not self._use_fallback:
                    try:
                        # Apply temporary overrides if requested
                        if voice:
                            resolved_id = self._resolve_voice_id_pyttsx3(engine, voice)
                            engine.setProperty("voice", resolved_id)
                        if rate is not None:
                            engine.setProperty("rate", rate)
                        if volume is not None:
                            engine.setProperty("volume", volume)

                        engine.say(text)
                        engine.runAndWait()

                        # Restore persistent state
                        if voice and self._current_voice:
                            restored_id = self._resolve_voice_id_pyttsx3(engine, self._current_voice)
                            engine.setProperty("voice", restored_id)
                        if rate is not None and self._rate is not None:
                            engine.setProperty("rate", self._rate)
                        if volume is not None and self._volume is not None:
                            engine.setProperty("volume", self._volume)
                        return
                    except Exception as exc:
                        logger.warning(
                            f"pyttsx3 speech synthesis failed ({exc}); falling back to PowerShell."
                        )
                        self._use_fallback = True

                # Fallback to PowerShell
                self._speak_powershell(text=text, voice=voice, rate=rate, volume=volume)
            except Exception as exc:
                logger.error(f"Speech execution failed: {exc}", exc_info=True)
            finally:
                self._is_speaking = False

    def _speak_powershell(
        self,
        text: str,
        voice: str | None = None,
        rate: int | None = None,
        volume: float | None = None,
    ) -> None:
        """Speak text using PowerShell System.Speech.Synthesis.SpeechSynthesizer."""
        escaped_text = text.replace("'", "''")
        active_voice = voice or self._current_voice
        active_rate = rate if rate is not None else self._rate
        active_volume = volume if volume is not None else self._volume

        # Convert WPM (~200 is normal) to PowerShell rate (-10 to +10)
        ps_rate = max(-10, min(10, int(round((active_rate - 200) / 15.0))))
        # Convert 0.0 - 1.0 to PowerShell volume (0 to 100)
        ps_volume = max(0, min(100, int(round(active_volume * 100.0))))

        script_lines = [
            "Add-Type -AssemblyName System.Speech",
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        ]

        if active_voice:
            escaped_voice = active_voice.replace("'", "''")
            script_lines.append(
                f"$v = $s.GetInstalledVoices() | Where-Object {{ "
                f"$_.VoiceInfo.Name -eq '{escaped_voice}' -or "
                f"$_.VoiceInfo.Id -eq '{escaped_voice}' -or "
                f"$_.VoiceInfo.Name -like '*{escaped_voice}*' "
                f"}} | Select-Object -First 1"
            )
            script_lines.append("if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }")

        script_lines.append(f"$s.Rate = {ps_rate}")
        script_lines.append(f"$s.Volume = {ps_volume}")
        script_lines.append(f"$s.Speak('{escaped_text}')")

        script = "\n".join(script_lines)
        b64 = base64.b64encode(script.encode("utf-16le")).decode("ascii")

        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", b64]

        with self._process_lock:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._current_process = proc

        try:
            _, stderr = proc.communicate()
            if proc.returncode != 0 and stderr:
                logger.error(
                    f"PowerShell speech failed (exit code {proc.returncode}): {stderr.strip()}"
                )
        except Exception as exc:
            logger.error(f"PowerShell speech process communication error: {exc}")
        finally:
            with self._process_lock:
                if self._current_process is proc:
                    self._current_process = None

    def _list_voices_powershell(self) -> list[dict[str, Any]]:
        """List installed voices using PowerShell System.Speech.Synthesis."""
        script = """
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($s.GetInstalledVoices() | ForEach-Object {
    [PSCustomObject]@{
        id = $_.VoiceInfo.Id
        name = $_.VoiceInfo.Name
        gender = $_.VoiceInfo.Gender.ToString()
        culture = $_.VoiceInfo.Culture.ToString()
        age = $_.VoiceInfo.Age.ToString()
        enabled = $_.Enabled
    }
})
ConvertTo-Json -InputObject $voices
"""
        b64 = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            res = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", b64],
                capture_output=True,
                text=True,
                timeout=10.0,
            )
            if res.returncode != 0:
                logger.error(f"Failed to list voices via PowerShell: {res.stderr}")
                return []

            output = res.stdout.strip()
            if not output:
                return []

            data = json.loads(output)
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
            return []
        except Exception as exc:
            logger.error(f"Error enumerating voices via PowerShell: {exc}")
            return []

    def _stop_speech(self) -> None:
        """Stop current speech output across both pyttsx3 and PowerShell backends."""
        self._is_speaking = False

        # Stop pyttsx3 if active
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception as exc:
                logger.debug(f"Error stopping pyttsx3 engine: {exc}")

        # Stop PowerShell subprocess if running
        with self._process_lock:
            if self._current_process is not None:
                try:
                    self._current_process.terminate()
                    try:
                        self._current_process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        self._current_process.kill()
                except Exception as exc:
                    logger.debug(f"Error terminating PowerShell speech process: {exc}")
                finally:
                    self._current_process = None
