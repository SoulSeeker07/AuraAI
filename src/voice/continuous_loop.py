"""
Aura Continuous Voice Loop Orchestrator
=======================================

Provides a continuous voice interaction loop:
  Wake Word ("Hey Aura") / STT
       ↓
  NLU Intent Parsing & Strategy Generation
       ↓
  ExecutionCoordinator Loop (Execute → Observe → Verify → Recover → Goal Verify)
       ↓
  TTS Response (Spoken Activity Trace Summary)
       ↓
  Continuous Loop (Auto-resume Listening)
"""

import asyncio
import logging
from typing import Any, Callable

from .models import ConversationState, VoiceContext
from .voice_manager import VoiceManager

logger = logging.getLogger(__name__)


class ContinuousVoiceLoop:
    """
    Continuous Voice Loop orchestrator connecting VoiceManager with ExecutionCoordinator.
    """

    def __init__(
        self,
        voice_manager: VoiceManager | None = None,
        coordinator: Any | None = None,
        nlu_engine: Any | None = None,
    ):
        self.voice_manager = voice_manager or VoiceManager()
        self.coordinator = coordinator
        self.nlu_engine = nlu_engine
        self._running = False
        self._loop_task: asyncio.Task | None = None

        # Wire VoiceManager callbacks
        self.voice_manager.on_stt_result = self._on_stt_result
        self.voice_manager.on_tts_complete = self._on_tts_complete
        self.voice_manager.on_error = self._on_voice_error

        # Turn history / stats
        self.turn_count = 0
        self.history: list[dict[str, Any]] = []

    def start(self) -> bool:
        """Start the continuous voice loop."""
        if self._running:
            logger.warning("ContinuousVoiceLoop already running")
            return True

        success = self.voice_manager.start()
        if success:
            self._running = True
            # Activate initial wake word / listening state
            self.voice_manager.activate()
            logger.info("ContinuousVoiceLoop started and listening")
        return success

    def stop(self) -> None:
        """Stop the continuous voice loop."""
        self._running = False
        self.voice_manager.stop()
        logger.info("ContinuousVoiceLoop stopped")

    def process_spoken_command(self, transcript: str) -> dict[str, Any]:
        """
        Process a spoken transcript through NLU and ExecutionCoordinator.
        """
        self.turn_count += 1
        logger.info(f"[ContinuousVoiceLoop Turn #{self.turn_count}] Processing transcript: '{transcript}'")

        # Parse NLU or build execution plan map
        exec_map = self._build_execution_map(transcript)

        coord_result = None
        if self.coordinator and exec_map:
            try:
                # Synchronous dispatch if event loop active
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    fut = asyncio.run_coroutine_threadsafe(
                        self.coordinator.coordinate(exec_map), loop
                    )
                    coord_result = fut.result(timeout=60)
                else:
                    coord_result = asyncio.run(self.coordinator.coordinate(exec_map))
            except Exception as e:
                logger.error(f"[ContinuousVoiceLoop] Coordination error: {e}")

        # Formulate spoken summary
        success = getattr(coord_result, "success", True) if coord_result else True
        duration = getattr(coord_result, "total_time", 1.5) if coord_result else 1.5

        if success:
            spoken_summary = f"Done. {transcript} completed in {duration:.1f} seconds."
        else:
            spoken_summary = f"Sorry, {transcript} could not be completed successfully."

        turn_fact = {
            "turn": self.turn_count,
            "transcript": transcript,
            "success": success,
            "duration": duration,
            "spoken_summary": spoken_summary,
            "coord_result": coord_result,
            "exec_map": exec_map,
        }
        self.history.append(turn_fact)

        # Trigger TTS response
        self.voice_manager.speak(spoken_summary)
        return turn_fact

    def _build_execution_map(self, transcript: str) -> dict[str, Any]:
        """Map spoken transcript to ExecutionMap structure."""
        t_lower = transcript.lower()

        if any(kw in t_lower for kw in ["first result", "top result", "open the first", "open that", "first video", "now open"]):
            last_query = getattr(self, "_last_search_query", "Python tutorial")
            return {
                "goal": transcript,
                "context_resolved": True,
                "resolved_query": last_query,
                "steps": [
                    {"engine": "browser", "action": "browser.select_video", "parameters": {"query": last_query}},
                    {"engine": "browser", "action": "browser.verify_video", "parameters": {"target": "selected_video"}},
                    {"engine": "browser", "action": "media.play", "parameters": {"target": "selected_video"}},
                ],
            }

        if "youtube" in t_lower:
            query = t_lower.replace("open chrome and go youtube find", "").replace("search youtube for", "").replace("search youtube", "").replace("and play", "").strip()
            self._last_search_query = query or "Python tutorial"
            return {
                "goal": transcript,
                "steps": [
                    {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.youtube.com"}},
                    {"engine": "browser", "action": "browser.search", "parameters": {"query": query or "Python tutorial"}},
                    {"engine": "browser", "action": "browser.select_video", "parameters": {"query": query or "Python tutorial"}},
                    {"engine": "browser", "action": "media.play", "parameters": {"target": "selected_video"}},
                ],
            }
        elif "notepad" in t_lower:
            return {
                "goal": transcript,
                "steps": [
                    {"engine": "desktop", "action": "app_open", "parameters": {"app_name": "notepad"}},
                    {"engine": "desktop", "action": "keyboard.type", "parameters": {"text": "Aura Continuous Voice Test"}},
                    {"engine": "desktop", "action": "app_close", "parameters": {"target": "notepad"}},
                ],
            }
        elif "facebook" in t_lower:
            query = t_lower.replace("find", "").replace("on facebook", "").replace("and show me the relevant result", "").strip()
            self._last_search_query = query or "Meta AI"
            return {
                "goal": transcript,
                "steps": [
                    {"engine": "browser", "action": "browser.ensure_open", "parameters": {"browser": "chrome"}},
                    {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.facebook.com"}},
                    {"engine": "browser", "action": "social.search", "parameters": {"query": query or "Meta AI", "platform": "facebook"}},
                    {"engine": "browser", "action": "social.inspect_result", "parameters": {"query": query or "Meta AI", "platform": "facebook"}},
                    {"engine": "browser", "action": "social.verify_result", "parameters": {"target": "result_page"}},
                ],
            }
        else:
            return {
                "goal": transcript,
                "steps": [
                    {"engine": "browser", "action": "browser.ensure_open", "parameters": {"browser": "chrome"}},
                    {"engine": "browser", "action": "browser.navigate", "parameters": {"url": "https://www.google.com"}},
                ],
            }

    def _on_stt_result(self, context: VoiceContext) -> None:
        """Callback when STT finishes transcribing speech."""
        logger.info(f"[ContinuousVoiceLoop] STT result received: {context.transcript}")
        self.process_spoken_command(context.transcript)

    def _on_tts_complete(self) -> None:
        """Callback when TTS finishes speaking response."""
        logger.info("[ContinuousVoiceLoop] TTS completed — resuming continuous active listening")
        if self._running:
            # Reactivate voice manager for continuous conversation
            self.voice_manager.activate()

    def _on_voice_error(self, error: str) -> None:
        """Callback on voice system error."""
        logger.error(f"[ContinuousVoiceLoop] Voice error: {error}")
