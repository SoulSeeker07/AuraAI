"""
Example wiring: microphone audio -> Groq Whisper (STT) -> MemoryManager
-> your TTS of choice -> speaker.

This is illustrative - swap in your actual audio capture/playback code
(e.g. sounddevice for mic input, whatever TTS engine you're using).
"""

import os

from groq import Groq

from memory_manager import MemoryManager

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
manager = MemoryManager(groq_client=groq_client)


def transcribe(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        transcript = groq_client.audio.transcriptions.create(
            file=f,
            model="whisper-large-v3-turbo",  # fastest/cheapest STT on Groq
        )
    return transcript.text


def speak(text: str) -> None:
    # Plug in real TTS here - Groq's Orpheus (console.groq.com/docs/text-to-speech),
    # ElevenLabs, pyttsx3, whatever you've already got in AuraAI.
    print(f"AURA: {text}")


def run_one_turn(audio_path: str) -> None:
    user_text = transcribe(audio_path)
    print(f"YOU: {user_text}")

    reply = manager.handle_user_turn(user_text)
    speak(reply)


if __name__ == "__main__":
    # Example: run_one_turn("input.wav")
    # In a real loop you'd capture audio on voice-activity-detection
    # boundaries and call run_one_turn() per detected utterance.
    pass
