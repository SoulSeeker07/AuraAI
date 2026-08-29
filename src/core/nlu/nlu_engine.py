"""
NLU Engine (Stage 0 Perception Layer)
Location: src/core/nlu/nlu_engine.py

Pure perception layer ("What did the human mean?").
Performs text normalization, typo correction, shorthand expansion, entity extraction,
and ambiguity detection, producing a structured NLUResult for DMM.

Architectural Rule:
    NLU is Perception, NOT Decision-Making.
    NLU does NOT call backends, execute actions, or bypass DMM.
"""

import difflib
import logging
import re
from typing import Any

from .ambiguity_detector import AmbiguityDetector
from .entity_extractor import EntityExtractor
from .models import NLUResult

logger = logging.getLogger(__name__)

# Core vocabulary set for dynamic fuzzy matching
_VOCABULARY = {
    "open", "chrome", "google", "youtube", "tutorial", "video", "videos",
    "notepad", "vscode", "sublime", "search", "find", "delete", "remove",
    "close", "minimize", "maximize", "restore", "play", "select",
    "version", "hardware", "weather", "temperature", "diagnostics",
    "capabilities", "limitations", "planners", "backends", "memory",
    "workspace", "tokens", "button", "hallucination", "mistake", "grammar",
    "thought", "update", "system", "command", "desktop", "browser", "browse",
    "conversion", "exchange", "currency", "rate", "dollar", "dollars", "rupee", "rupees",
    "research", "synthesize", "analyze", "navigate", "extract", "document", "summarize",
    "terminal", "code", "refactor", "benchmark", "execution", "orchestration", "reasoning",
    "findings", "advancements", "neuromorphic", "computing"
}

# Common shorthand, STT noise, and typos mapped to clean English
_TYPO_MAP = {
    "opn": "open",
    "oepn": "open",
    "openup": "open",
    "chorme": "chrome",
    "chrm": "chrome",
    "crom": "chrome",
    "gogle": "google",
    "googl": "google",
    "youtub": "youtube",
    "yutub": "youtube",
    "tutrial": "tutorial",
    "tutoral": "tutorial",
    "vid": "video",
    "vids": "videos",
    "notpad": "notepad",
    "vsc": "vscode",
    "vScode": "vscode",
    "vs code": "vscode",
    "sublm": "sublime",
    "plz": "please",
    "pls": "please",
    "u": "you",
    "ur": "your",
    "r": "are",
    "n": "and",
    "wat": "what",
    "wats": "what is",
    "whats": "what is",
    "showme": "show me",
    "gimme": "give me",
    "deleteit": "delete it",
    "openit": "open it",
    "cant": "can not",
    "wont": "will not",
    "dont": "do not",
    "didnt": "did not",
    "did'nt": "did not",
    "couldnt": "could not",
    "wouldnt": "would not",
    "isnt": "is not",
    "arent": "are not",
    "im": "i am",
    "doller": "dollar",
    "dollers": "dollars",
    "covertion": "conversion",
    "convertion": "conversion",
    "calculater": "calculator",
    "verison": "version",
    "versin": "version",
    "vrsion": "version",
    "verision": "version",
    "capabilites": "capabilities",
    "capabiltes": "capabilities",
    "capabilties": "capabilities",
    "featurs": "features",
    "weater": "weather",
    "wether": "weather",
    "temprature": "temperature",
    "tempratur": "temperature",
    "hardwaer": "hardware",
    "hardwere": "hardware",
    "diagnotics": "diagnostics",
    "diagnstics": "diagnostics",
    "workspce": "workspace",
    "wrkspace": "workspace",
    "memry": "memory",
    "memor": "memory",
    "memori": "memory",
    "plannr": "planner",
    "planers": "planners",
    "plannrs": "planners",
    "tokn": "token",
    "tokns": "tokens",
    "mistke": "mistake",
    "mistk": "mistake",
    "grammer": "grammar",
    "grammr": "grammar",
    "thoght": "thought",
    "thot": "thought",
    "halusination": "hallucination",
    "halucination": "hallucination",
    "serch": "search",
    "buttion": "button",
    "buton": "button",
    "updat": "update",
    "updte": "update",
}


class NLUEngine:
    """
    Stage 0 Perception Layer.

    Normalizes user input, extracts entities, and scores intent confidence
    without making execution decisions.
    """

    def __init__(self):
        self.entity_extractor = EntityExtractor()
        self.ambiguity_detector = AmbiguityDetector()

    def process(self, raw_text: str, context: dict[str, Any] | None = None) -> NLUResult:
        """
        Process raw user text through the NLU perception pipeline.

        Returns structured NLUResult containing normalized text, extracted entities,
        non-binding intent hint, perception confidence score, and ambiguity prompt if needed.
        """
        if not raw_text or not raw_text.strip():
            return NLUResult(
                raw_text="",
                normalized_text="",
                confidence=0.0,
                is_ambiguous=True,
                clarification_prompt="I didn't receive any input. How can I help you?",
            )

        # 1. Fast Path: Text Normalization & Typo/Shorthand Correction
        normalized_text, typos_fixed = self.normalize_text(raw_text)

        # 2. Entity Extraction
        entities = self.entity_extractor.extract_entities(normalized_text)

        # 3. Non-binding Intent Hint Generation
        intent_hint, intent_confidence = self._infer_intent_hint(normalized_text, entities)

        # Overall Perception Confidence
        overall_confidence = round(
            0.6 * intent_confidence + (0.4 if entities else 0.3), 2
        )
        if typos_fixed:
            overall_confidence = max(0.75, overall_confidence)

        # 4. Ambiguity Assessment
        nlu_result = self.ambiguity_detector.evaluate(
            raw_text=raw_text,
            normalized_text=normalized_text,
            intent_hint=intent_hint,
            entities=entities,
            confidence=overall_confidence,
            context=context,
        )
        nlu_result.metadata["typos_fixed"] = typos_fixed

        logger.debug(f"[NLU] raw='{raw_text}' → norm='{normalized_text}' intent='{intent_hint}' conf={overall_confidence}")
        return nlu_result

    def normalize_text(self, text: str) -> tuple[str, list[str]]:
        """
        Normalize text: lowercasing, expanding shorthand, fixing common typos,
        cleaning punctuation.

        Returns (normalized_text, list_of_typos_fixed).
        """
        # Clean extra spaces & trailing punctuation except ?
        cleaned = re.sub(r"\s+", " ", text.strip())
        words = cleaned.split()
        normalized_words = []
        typos_fixed = []

        for word in words:
            word_clean = word.strip(".,!;:'\"")
            word_lower = word_clean.lower()
            if word_lower in _TYPO_MAP:
                replacement = _TYPO_MAP[word_lower]
                normalized_words.append(replacement)
                typos_fixed.append(f"'{word_clean}'→'{replacement}'")
            elif word_lower not in _VOCABULARY and len(word_lower) >= 4:
                matches = difflib.get_close_matches(word_lower, list(_VOCABULARY), n=1, cutoff=0.82)
                if matches and abs(len(word_lower) - len(matches[0])) <= 2:
                    replacement = matches[0]
                    normalized_words.append(replacement)
                    typos_fixed.append(f"Fuzzy '{word_clean}'→'{replacement}'")
                else:
                    normalized_words.append(word_clean)
            else:
                normalized_words.append(word_clean)

        normalized = " ".join(normalized_words)

        # STT and Grammar Multi-word phrase cleanup
        grammar_phrases = [
            (r"\byou\s+tube\b", "youtube"),
            (r"\ban\s+(search|find|open|play)\b", r"and \1"),
            (r"\b(whats|what's|wats)\s+is\b", "what is"),
            (r"\b(who's|whos)\s+is\b", "who is"),
            (r"\b(where's|wheres)\s+is\b", "where is"),
            (r"\bhow\s+search\s+(?:work|works)\b", "how does search work"),
            (r"\bhow\s+memory\s+(?:work|works)\b", "how does memory work"),
            (r"\bwhat\s+this\s+memory\b", "what is this memory"),
            (r"\bi\s+thoght\s+we\s+did\s+something\s+to\s+halusination\b", "how does anti-hallucination work"),
            (r"\bwhy\s+its\s+telling\s+lie\b", "why did it hallucinate"),
        ]
        for pat, repl in grammar_phrases:
            if re.search(pat, normalized, flags=re.IGNORECASE):
                normalized = re.sub(pat, repl, normalized, flags=re.IGNORECASE)
                typos_fixed.append(f"Grammar/Phrase '{pat}'→'{repl}'")

        # Handle conversational prefixes like "can u open", "please open", "show me"
        normalized = re.sub(
            r"^(can|could|would|will)\s+(you|u)\s+(please|plz\s+)?",
            "",
            normalized,
            flags=re.IGNORECASE,
        ).strip()
        normalized = re.sub(r"^(please|plz)\s+", "", normalized, flags=re.IGNORECASE).strip()

        return normalized, typos_fixed

    def _infer_intent_hint(
        self, normalized_text: str, entities: dict[str, Any]
    ) -> tuple[str, float]:
        """
        Infer a non-binding intent hint for DMM.

        Returns (intent_hint_string, confidence_score).
        """
        norm_lower = normalized_text.lower()

        # Desktop Action
        if entities.get("app_name") or re.search(
            r"\b(open|launch|start|close|minimize|focus|bring)\b", norm_lower
        ):
            return "desktop_action", 0.95

        # Research / Search
        if entities.get("search_query") or re.search(
            r"\b(search|look up|find|google|weather|what is|who is|where is|conversion rate|exchange rate|currency|usd|inr|rate)\b", norm_lower
        ):
            return "research", 0.90

        # Coding
        if re.search(
            r"\b(code|python|script|refactor|ast|git|bug|test|function|repository)\b", norm_lower
        ):
            return "coding", 0.90

        # Memory / Recall
        if re.search(
            r"\b(remember|recall|favorite|my name|what did we do|summarize session)\b", norm_lower
        ):
            return "memory", 0.90

        # System Query
        if re.search(
            r"\b(system info|cpu|ram|battery|status|version)\b", norm_lower
        ):
            return "system_query", 0.90

        # Default Chat / Conversation
        return "chat", 0.70
