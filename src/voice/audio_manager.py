"""
Audio Manager

Single owner of microphone and speaker resources. Manages audio input/output
and ensures proper device handling and resource management.
"""

import logging
import threading
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AudioDeviceInfo:
    """Information about an audio device."""

    device_id: int
    name: str
    input: bool
    output: bool
    channels: int = 1
    sample_rate: int = 16000
    bits_per_sample: int = 16


class AudioManager:
    """
    Manages audio devices and streams.

    This is the single owner of microphone and speaker resources,
    ensuring proper device handling and resource management.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure single instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the audio manager."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = False

        # Audio device information
        self.input_device: AudioDeviceInfo | None = None
        self.output_device: AudioDeviceInfo | None = None

        # Audio streams
        self.input_stream = None
        self.output_stream = None

        # Audio data buffers
        self._input_buffer = bytearray()
        self._output_buffer = bytearray()
        self._buffer_lock = threading.Lock()

        # Callbacks
        self._input_callback: Callable[[bytes], None] | None = None
        self._output_callback: Callable[[bytes], None] | None = None

        # State tracking
        self._is_recording = False
        self._is_playing = False
        self._recording_thread = None
        
        import queue
        self._audio_queue = queue.Queue()

        logger.info("Audio Manager initialized")
        self._initialized = True

    def get_input_devices(self) -> list[AudioDeviceInfo]:
        """Get list of available input devices."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            input_devices = []

            for dev in devices:
                if dev["max_input_channels"] > 0:
                    device_info = AudioDeviceInfo(
                        device_id=dev["index"],
                        name=dev["name"],
                        input=True,
                        output=False,
                        channels=dev["max_input_channels"],
                        sample_rate=int(dev["default_samplerate"]),
                        bits_per_sample=16,
                    )
                    input_devices.append(device_info)

            logger.info(f"Found {len(input_devices)} input devices")
            return input_devices

        except ImportError:
            logger.warning("sounddevice not available, cannot query devices")
            return []
        except Exception as e:
            logger.error(f"Error getting input devices: {e}")
            return []

    def get_output_devices(self) -> list[AudioDeviceInfo]:
        """Get list of available output devices."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            output_devices = []

            for dev in devices:
                if dev["max_output_channels"] > 0:
                    device_info = AudioDeviceInfo(
                        device_id=dev["index"],
                        name=dev["name"],
                        input=False,
                        output=True,
                        channels=dev["max_output_channels"],
                        sample_rate=int(dev["default_samplerate"]),
                        bits_per_sample=16,
                    )
                    output_devices.append(device_info)

            logger.info(f"Found {len(output_devices)} output devices")
            return output_devices

        except ImportError:
            logger.warning("sounddevice not available, cannot query devices")
            return []
        except Exception as e:
            logger.error(f"Error getting output devices: {e}")
            return []

    def get_default_input_device(self) -> AudioDeviceInfo | None:
        """Get default input device."""
        devices = self.get_input_devices()
        return devices[0] if devices else None

    def get_default_output_device(self) -> AudioDeviceInfo | None:
        """Get default output device."""
        devices = self.get_output_devices()
        return devices[0] if devices else None

    def select_input_device(self, device_id: int) -> bool:
        """Select input device by ID."""
        try:

            devices = self.get_input_devices()
            device = next((d for d in devices if d.device_id == device_id), None)

            if device:
                self.input_device = device
                logger.info(f"Selected input device: {device.name}")
                return True
            else:
                logger.error(f"Input device {device_id} not found")
                return False

        except Exception as e:
            logger.error(f"Error selecting input device: {e}")
            return False

    def select_output_device(self, device_id: int) -> bool:
        """Select output device by ID."""
        try:

            devices = self.get_output_devices()
            device = next((d for d in devices if d.device_id == device_id), None)

            if device:
                self.output_device = device
                logger.info(f"Selected output device: {device.name}")
                return True
            else:
                logger.error(f"Output device {device_id} not found")
                return False

        except Exception as e:
            logger.error(f"Error selecting output device: {e}")
            return False

    def start_recording(
        self,
        callback: Callable[[bytes], None],
        sample_rate: int = 16000,
        channels: int = 1,
        device_id: int | None = None,
    ) -> bool:
        """
        Start recording audio from microphone.

        Args:
            callback: Function to call with audio chunks
            sample_rate: Audio sample rate
            channels: Number of audio channels
            device_id: Optional specific device to use

        Returns:
            True if successful
        """
        if self._is_recording:
            logger.warning("Already recording")
            return False

        try:
            import sounddevice as sd

            # Use selected device or default
            input_device = self.input_device
            if not input_device and device_id:
                input_device = AudioDeviceInfo(
                    device_id=device_id,
                    name="specified_device",
                    input=True,
                    output=False,
                    channels=channels,
                    sample_rate=sample_rate,
                    bits_per_sample=16,
                )

            if not input_device:
                logger.error("No input device selected")
                return False

            # Drain any residual queued audio
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except Exception:
                    break

            with self._buffer_lock:
                self._input_buffer.clear()

            # Set up callback
            self._input_callback = callback
            self._is_recording = True

            # Pre-flight physical device sample rate check
            # NOTE: On Windows (MME/WASAPI shared), the Windows Audio Engine handles software
            # resampling (e.g. 44.1k/48k -> 16k) transparently. Warning rather than hard-failing
            # allows standard Windows audio drivers to open smoothly without crashing.
            try:
                dev_info = sd.query_devices(input_device.device_id, 'input')
                native_rate = dev_info.get('default_samplerate')
                if native_rate and int(native_rate) != sample_rate:
                    logger.info(
                        f"[AudioManager] Microphone physical default rate is {int(native_rate)}Hz; "
                        f"PortAudio driver will resample to {sample_rate}Hz."
                    )
                sd.check_input_settings(
                    device=input_device.device_id,
                    channels=channels,
                    dtype='int16',
                    samplerate=sample_rate,
                )
            except Exception as _check_err:
                logger.warning(f"[AudioManager] Audio device pre-flight check warning: {_check_err}")

            # Start recording
            if not self.input_stream:
                self.input_stream = sd.InputStream(
                    device=input_device.device_id,
                    channels=channels,
                    samplerate=sample_rate,
                    dtype='int16',
                    callback=self._stream_callback,
                )

            self.input_stream.start()
            
            # Start monitor thread if not already running
            if not self._recording_thread or not self._recording_thread.is_alive():
                self._recording_thread = threading.Thread(target=self._monitor_stream)
                self._recording_thread.daemon = True
                self._recording_thread.start()

            logger.info(f"Started recording on device {input_device.device_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self._is_recording = False
            return False

    def stop_recording(self) -> bool:
        """Stop recording audio."""
        if not self._is_recording:
            return False

        try:
            if self.input_stream:
                self.input_stream.stop()
                # Do NOT close the stream here, keep it for deterministic ownership
                # We just pause capturing.

            self._is_recording = False
            self._input_callback = None
            
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except Exception:
                    break

            with self._buffer_lock:
                self._input_buffer.clear()

            logger.info("Stopped recording")
            return True

        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return False

    def start_playback(
        self,
        callback: Callable[[bytes], None],
        sample_rate: int = 16000,
        channels: int = 1,
        device_id: int | None = None,
    ) -> bool:
        """
        Start playing audio to speaker.

        Args:
            callback: Function to call with audio chunks
            sample_rate: Audio sample rate
            channels: Number of audio channels
            device_id: Optional specific device to use

        Returns:
            True if successful
        """
        if self._is_playing:
            logger.warning("Already playing")
            return False

        try:
            import sounddevice as sd

            # Use selected device or default
            output_device = self.output_device
            if not output_device and device_id:
                output_device = AudioDeviceInfo(
                    device_id=device_id,
                    name="specified_device",
                    input=False,
                    output=True,
                    channels=channels,
                    sample_rate=sample_rate,
                    bits_per_sample=16,
                )

            if not output_device:
                logger.error("No output device selected")
                return False

            # Set up callback
            self._output_callback = callback
            self._is_playing = True

            # Start playback
            self.output_stream = sd.OutputStream(
                device=output_device.device_id,
                channels=channels,
                samplerate=sample_rate,
                dtype='int16',
                callback=self._playback_callback,
            )

            self.output_stream.start()

            logger.info(f"Started playback on device {output_device.device_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            self._is_playing = False
            return False

    def stop_playback(self) -> bool:
        """Stop playing audio."""
        if not self._is_playing:
            return False

        try:
            if self.output_stream:
                self.output_stream.stop()
                self.output_stream.close()
                self.output_stream = None

            self._is_playing = False
            self._output_callback = None

            logger.info("Stopped playback")
            return True

        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            return False

    def _stream_callback(self, indata, frames, time, status):
        """Callback for audio input stream."""
        if status:
            logger.warning(f"Audio input status: {status}")

        if self._is_recording:
            try:
                self._audio_queue.put_nowait(indata.tobytes())
            except Exception:
                pass

    def _playback_callback(self, outdata, frames, time, status):
        """Callback for audio output stream."""
        if status:
            logger.warning(f"Audio output status: {status}")

        if self._output_callback and self._is_playing:
            audio_data = self._output_callback(frames)
            if audio_data:
                outdata[:] = audio_data.tobytes()
            else:
                # Silence
                outdata[:] = b"\x00" * len(outdata)
        else:
            # Silence if not playing
            outdata[:] = b"\x00" * len(outdata)

    def _monitor_stream(self):
        """Monitor recording stream status and process audio queue."""
        import queue
        import time
        while self._is_recording:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                if self._input_callback and self._is_recording:
                    self._input_callback(chunk)
            except queue.Empty:
                pass
            except Exception as e:
                if self._is_recording:
                    logger.error(f"Stream monitoring error: {e}")

    def save_recording(
        self, filepath: str, sample_rate: int = 16000, channels: int = 1
    ) -> bool:
        """
        Save recorded audio to a WAV file.

        Args:
            filepath: Path to save the recording
            sample_rate: Audio sample rate
            channels: Number of channels

        Returns:
            True if successful
        """
        try:
            if not self._input_buffer:
                logger.warning("No audio data to save")
                return False

            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with wave.open(str(filepath), "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16-bit audio
                wf.setframerate(sample_rate)
                wf.writeframes(self._input_buffer)

            logger.info(f"Saved recording to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error saving recording: {e}")
            return False

    def play_wav_file(self, filepath: str, sample_rate: int = 16000) -> bool:
        """
        Play a WAV file.

        Args:
            filepath: Path to WAV file
            sample_rate: Audio sample rate

        Returns:
            True if successful
        """
        try:
            import sounddevice as sd

            if self._is_playing:
                logger.warning("Already playing")
                return False

            filepath = Path(filepath)
            if not filepath.exists():
                logger.error(f"WAV file not found: {filepath}")
                return False

            # Load WAV file
            with wave.open(str(filepath), "rb") as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                audio_data = wf.readframes(wf.getnframes())

            # Play audio
            self.output_stream = sd.OutputStream(
                device=self.output_device.device_id if self.output_device else None,
                channels=channels,
                samplerate=sample_rate,
                data=audio_data,
            )

            self.output_stream.start()
            logger.info(f"Playing WAV file: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error playing WAV file: {e}")
            return False

    def get_audio_stats(self) -> dict[str, Any]:
        """Get current audio statistics."""
        return {
            "input_device": self.input_device.name if self.input_device else None,
            "output_device": self.output_device.name if self.output_device else None,
            "is_recording": self._is_recording,
            "is_playing": self._is_playing,
            "input_buffer_size": len(self._input_buffer),
            "output_buffer_size": len(self._output_buffer),
        }

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._is_playing

    def cleanup(self):
        """Clean up audio resources."""
        logger.info("Cleaning up audio resources")
        self.stop_recording()
        
        # Explicitly close streams on full cleanup
        if self.input_stream:
            try:
                self.input_stream.close()
            except Exception:
                pass
            self.input_stream = None
            
        self.stop_playback()
        self._input_buffer.clear()
        self._output_buffer.clear()
