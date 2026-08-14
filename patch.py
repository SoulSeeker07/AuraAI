import re

with open('src/voice/stt_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

stabilizer_code = """
from dataclasses import dataclass
import threading
import time
from concurrent.futures import ThreadPoolExecutor

@dataclass
class StabilizedResult:
    confirmed_text: str
    tentative_text: str
    newly_confirmed: str

class LocalAgreementStabilizer:
    def __init__(self):
        self._confirmed_words: list[str] = []
        self._previous_hypothesis_words: list[str] = []
        self.confirmed_audio_offset_s: float = 0.0

    def reset(self) -> None:
        self._confirmed_words.clear()
        self._previous_hypothesis_words.clear()
        self.confirmed_audio_offset_s = 0.0

    def update(self, words_with_timestamps: list[tuple[str, float, float]]) -> StabilizedResult:
        current_words = [w for w, _, _ in words_with_timestamps]
        
        current_tail = current_words[len(self._confirmed_words):]
        previous_tail = self._previous_hypothesis_words[len(self._confirmed_words):]
        agreement_len = self._common_prefix_len(current_tail, previous_tail)

        newly_confirmed = words_with_timestamps[
            len(self._confirmed_words): len(self._confirmed_words) + agreement_len
        ]
        if newly_confirmed:
            self._confirmed_words.extend(w for w, _, _ in newly_confirmed)
            self.confirmed_audio_offset_s = newly_confirmed[-1][2]

        tentative_words = current_words[len(self._confirmed_words):]
        self._previous_hypothesis_words = current_words

        return StabilizedResult(
            confirmed_text=" ".join(self._confirmed_words),
            tentative_text=" ".join(tentative_words),
            newly_confirmed=" ".join(w for w, _, _ in newly_confirmed),
        )

    @staticmethod
    def _common_prefix_len(a: list[str], b: list[str]) -> int:
        n = 0
        for wa, wb in zip(a, b):
            if wa != wb:
                break
            n += 1
        return n

class FasterWhisperSTTEngine(STTEngine):
"""

content = content.replace("class FasterWhisperSTTEngine(STTEngine):", stabilizer_code)
with open('src/voice/stt_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
