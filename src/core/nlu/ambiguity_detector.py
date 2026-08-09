"""
NLU Ambiguity Detector
Location: src/core/nlu/ambiguity_detector.py

Evaluates perception confidence and detects ambiguous user requests
(e.g., destructive actions without target entities, unresolvable commands).
Constructs structured clarification prompts for DMM to ask the user.
"""

from typing import Any

from .models import NLUResult


class AmbiguityDetector:
    """Detects ambiguities in user input perception."""

    def evaluate(
        self,
        raw_text: str,
        normalized_text: str,
        intent_hint: str,
        entities: dict[str, Any],
        confidence: float,
        context: dict[str, Any] | None = None,
    ) -> NLUResult:
        """
        Evaluate normalized text, intent, and entities for ambiguity.

        Returns an NLUResult with is_ambiguous and clarification_prompt populated
        if clarification is required.
        """
        norm_lower = normalized_text.lower().strip()
        ctx = context or {}
        is_ambiguous = False
        clarification_prompt = None

        # 1. Contextual Pronouns & Follow-Ups ("play the first result", "click that")
        relative_phrases = ["first result", "first video", "first candidate", "first one", "first result", "play the first", "open the first"]
        has_relative_phrase = any(p in norm_lower for p in relative_phrases)

        if has_relative_phrase:
            active_cands = ctx.get("last_search_candidates") or ctx.get("active_candidates") or []
            if active_cands:
                entities["resolved_candidate"] = active_cands[0]
                is_ambiguous = False
            else:
                is_ambiguous = True
                clarification_prompt = "Which result or video would you like me to play?"

        # 2. Unresolvable Generic Targets ("open the file", "edit the document", "send it")
        if not is_ambiguous:
            if norm_lower in ("open the file", "open file", "edit the document", "edit document"):
                avail_files = ctx.get("available_files", [])
                if len(avail_files) > 1 or not ctx.get("active_file"):
                    is_ambiguous = True
                    clarification_prompt = "Which file or document would you like me to open?"
            elif norm_lower in ("send it", "send message", "send document"):
                if not entities.get("recipient") and not ctx.get("active_message"):
                    is_ambiguous = True
                    clarification_prompt = "What message or document should I send and to whom?"

        # 3. Low Confidence Threshold (< 0.6)
        if not is_ambiguous and confidence < 0.6:
            is_ambiguous = True
            clarification_prompt = (
                f"I'm not completely sure what you mean by '{raw_text}'. "
                "Could you please clarify what action or tool you'd like me to run?"
            )

        # 4. Destructive Actions Without Specific Target Entities
        if not is_ambiguous:
            destructive_verbs = ["delete", "remove", "erase", "drop", "purge", "clear"]
            has_destructive_verb = any(v in norm_lower for v in destructive_verbs)

            if has_destructive_verb:
                target_file = entities.get("file_path") or entities.get("file_name")
                target_dir = entities.get("directory")
                target_app = entities.get("app_name")

                if not (target_file or target_dir or target_app):
                    is_ambiguous = True
                    clarification_prompt = (
                        f"Which specific file, folder, or resource would you like me to {norm_lower.split()[0]}? "
                        "Please provide the exact name or path."
                    )

        # 5. High-Risk System Commands Without Parameters
        if not is_ambiguous:
            if norm_lower in ("close app", "close application", "kill process", "stop service"):
                is_ambiguous = True
                clarification_prompt = (
                    f"Which application or process would you like me to {norm_lower}? "
                    "Please specify the name."
                )

        return NLUResult(
            raw_text=raw_text,
            normalized_text=normalized_text,
            intent_hint=intent_hint,
            entities=entities,
            confidence=confidence,
            is_ambiguous=is_ambiguous,
            clarification_prompt=clarification_prompt,
            metadata={"evaluated_by": "AmbiguityDetector"},
        )
