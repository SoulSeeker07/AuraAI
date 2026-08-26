"""
AuraAI Live Voice Recorder & Speech-to-Text Transcriber
======================================================
Location: src/tools/voice_recorder.py

Provides real-time mic toggle audio capture & fast cloud/local speech-to-text.
"""

import io
import os
import wave
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LiveVoiceRecorder:
    """Manages push-to-talk / toggle-to-talk microphone audio recording and transcription."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = 2  # 16-bit
        self._frames: list[bytes] = []
        self._is_recording = False
        self._record_thread: Optional[threading.Thread] = None
        self._stream = None
        self._pyaudio_instance = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start_recording(self) -> bool:
        """Begin capturing audio from default microphone."""
        if self._is_recording:
            return True

        self._frames = []
        self._is_recording = True

        try:
            import pyaudio
            self._pyaudio_instance = pyaudio.PyAudio()
            self._stream = self._pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=1024,
            )
        except Exception as e:
            logger.warning(f"[LiveVoiceRecorder] PyAudio init failed, trying sounddevice: {e}")
            self._stream = None

        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        logger.info("[LiveVoiceRecorder] Live microphone recording started.")
        return True

    def _record_loop(self):
        """Continuous background audio buffer loop."""
        if self._stream is not None:
            while self._is_recording:
                try:
                    data = self._stream.read(1024, exception_on_overflow=False)
                    self._frames.append(data)
                except Exception as e:
                    logger.debug(f"[LiveVoiceRecorder] Stream read warning: {e}")
                    break
        else:
            # Fallback to sounddevice if PyAudio was unavailable
            try:
                import sounddevice as sd
                def _callback(indata, frames, time_info, status):
                    if self._is_recording:
                        self._frames.append(bytes(indata))

                with sd.RawInputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='int16',
                    callback=_callback,
                ):
                    while self._is_recording:
                        sd.sleep(50)
            except Exception as e:
                logger.error(f"[LiveVoiceRecorder] SoundDevice recording error: {e}")

    def stop_recording(self) -> bytes:
        """Stop capturing and return standard WAV audio bytes."""
        if not self._is_recording:
            return b""

        self._is_recording = False

        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._pyaudio_instance is not None:
            try:
                self._pyaudio_instance.terminate()
            except Exception:
                pass
            self._pyaudio_instance = None

        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=1.0)

        logger.info(f"[LiveVoiceRecorder] Recording stopped. Captured {len(self._frames)} frames.")
        return self._build_wav(self._frames)

    def _build_wav(self, frames: list[bytes]) -> bytes:
        """Package raw PCM chunks into a valid WAV file in memory."""
        if not frames:
            return b""

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.sample_width)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(frames))

        buf.seek(0)
        return buf.read()

    @staticmethod
    def transcribe(audio_bytes: bytes) -> str:
        """Transcribe audio bytes using Groq Whisper with local fallback."""
        if not audio_bytes or len(audio_bytes) < 4000:
            logger.debug("[LiveVoiceRecorder] Audio data too short to transcribe.")
            return ""

        # 1. Primary: Groq Whisper Cloud (fast ~150ms) with KeyPool rotation
        try:
            from ai.key_pool import KeyPool
            pool = KeyPool.get_instance()
            if pool.count("groq") > 0:
                def _do_whisper(key: str) -> str:
                    from groq import Groq
                    client = Groq(api_key=key)
                    transcription = client.audio.transcriptions.create(
                        file=("voice.wav", audio_bytes),
                        model="whisper-large-v3-turbo",
                        response_format="text",
                    )
                    return str(transcription).strip()

                text = pool.execute_with_failover(_do_whisper, service="groq")
                if text:
                    logger.info(f"[LiveVoiceRecorder] Groq Whisper transcribed: '{text}'")
                    return text
        except Exception as e:
            logger.warning(f"[LiveVoiceRecorder] Groq Whisper transcription notice: {e}")

        # 2. Fallback: SpeechRecognition (Google Free Speech API / local)
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                audio_data = r.record(source)
            text = r.recognize_google(audio_data)
            logger.info(f"[LiveVoiceRecorder] Google Speech recognized: '{text}'")
            return text
        except Exception as e:
            logger.debug(f"[LiveVoiceRecorder] Local fallback notice: {e}")

        return ""
