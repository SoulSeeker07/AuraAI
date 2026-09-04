"""
LLM-Based Intent Classification
Location: src/brain/intent_classifier.py

Provides schema-bound, LLM-driven intent classification bound directly
to the live Universal Capability Registry (CapabilityRegistry).

Features:
- Live capability introspection (derived at runtime from CapabilityRegistry.list(require_live=True))
- Enforces tool_choice='required' with strict structured output parsing
- Async non-blocking execution wrapped via asyncio.to_thread & timeout protection
- Structured fallback: fails closed on low confidence, API errors, or schema validation failures
- Telemetry & eval corpus logging for all classification outcomes
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import Capability
from ai.provider_manager import ProviderManager

logger = logging.getLogger(__name__)

DEFAULT_CLASSIFIER_MODEL: str | None = None
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_RETRIES = 1


class ClassificationOutcome(str, Enum):
    RESOLVED = "resolved"
    NEEDS_CLARIFICATION = "needs_clarification"
    FAILED_CLOSED = "failed_closed"


@dataclass
class Intent:
    """Matches the shape consumed by ConversationEngine and downstream orchestrators."""
    name: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResult:
    """Structured result of an intent classification attempt."""
    outcome: ClassificationOutcome
    intent: Intent | None
    confidence: float
    raw_llm_output: str | None
    capability_name: str | None
    clarification_prompt: str | None = None


@dataclass
class ParsedToolCall:
    is_valid: bool
    capability_name: str | None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    error: str | None = None


class IntentClassifier:
    """
    Tier 1 Intent Classifier: LLM-driven, schema-bound to the live CapabilityRegistry.
    Tier 0 (wake words, emergency stops, cancel) remains upstream.
    """

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        provider_manager: ProviderManager | None = None,
        model: str = DEFAULT_CLASSIFIER_MODEL,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._registry = registry or CapabilityRegistry.get_instance()
        self._provider_manager = provider_manager
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.timeout_seconds = timeout_seconds

    def _get_provider_manager(self) -> ProviderManager:
        if self._provider_manager is None:
            import os
            from ai.registry import build_provider_manager
            self._provider_manager = build_provider_manager(dict(os.environ))
        return self._provider_manager

    # Baseline anchor capability patterns always retained in candidate set
    _CORE_ANCHOR_PATTERNS: tuple[str, ...] = (
        "system.shell",
        "desktop.app_open",
        "app_open",
        "coding.generate_code",
        "browser.navigate",
        "memory.search",
        "terminal.execute",
    )

    # Lightweight domain synonyms to prevent lexical pruning misses
    # Systematic domain taxonomy synonyms to prevent pruning misses on indirect phrasings
    _SYNONYM_MAP: dict[str, tuple[str, ...]] = {
        # Execution & Process
        "launch": ("open", "app", "window", "start"),
        "start": ("open", "app", "launch", "run"),
        "run": ("execute", "terminal", "shell", "command"),
        "exec": ("execute", "run", "command", "terminal"),
        "kill": ("terminate", "stop", "close", "process"),
        "stop": ("kill", "terminate", "close", "pause"),
        # Audio, Speech & Voice
        "speak": ("tts", "voice", "audio", "narrate", "read"),
        "read": ("speak", "tts", "voice", "narrate", "words"),
        "aloud": ("speak", "tts", "voice", "audio"),
        "words": ("speak", "tts", "voice", "read"),
        "louder": ("volume", "audio", "sound"),
        "quieter": ("volume", "audio", "sound", "mute"),
        "mute": ("volume", "audio", "silence", "sound"),
        # Vision, Camera & Display
        "snapshot": ("camera", "capture", "photo", "screen"),
        "screenshot": ("capture", "screen", "display", "image"),
        "capture": ("screenshot", "record", "camera", "photo"),
        # Filesystem & Storage
        "directory": ("folder", "files", "path", "storage"),
        "folder": ("directory", "files", "storage", "path"),
        "clean": ("cleanup", "cache", "temp", "storage", "delete"),
        "erase": ("delete", "remove", "trash", "clear"),
        "storage": ("disk", "space", "files", "drive"),
        # Network & Connectivity
        "internet": ("network", "wifi", "browser", "web", "connection"),
        "wifi": ("network", "internet", "wireless", "connection"),
        "webpage": ("browser", "url", "navigate", "page", "site"),
        "website": ("browser", "url", "navigate", "site"),
        # Development, Git & Shell
        "history": ("log", "git", "commits", "timeline"),
        "diff": ("changes", "git", "modified", "compare"),
        "editor": ("notepad", "code", "text", "app"),
        "code": ("develop", "script", "program", "function"),
        "write": ("generate", "create", "code", "implement"),
        "fix": ("refactor", "debug", "code", "patch"),
        # System State, Power & Metrics
        "battery": ("power", "charge", "energy", "status"),
        "reboot": ("restart", "power", "system"),
        "shutdown": ("power", "turnoff", "system", "halt"),
        # Smart Home & Environment
        "precipitate": ("rain", "weather", "forecast", "precipitation"),
        "weather": ("forecast", "rain", "temperature", "climate"),
        "darker": ("dim", "light", "bulb", "brightness"),
        "brighter": ("light", "bulb", "brightness", "illumination"),
        "lights": ("bulb", "illumination", "brightness", "dim"),
    }

    def _select_candidate_capabilities(
        self, utterance: str, all_caps: list[Capability], max_candidates: int = 40
    ) -> list[Capability]:
        """
        Select top-K relevant capabilities based on lexical token overlap, synonym expansion,
        and domain relevance. Ensures tools list stays well under the 128 ceiling while
        preserving routing accuracy for non-exact phrasing.
        """
        if len(all_caps) <= max_candidates:
            return all_caps

        import re
        raw_tokens = set(re.findall(r"\w+", utterance.lower()))
        
        # Expand synonyms
        expanded_tokens = set(raw_tokens)
        for t in raw_tokens:
            if t in self._SYNONYM_MAP:
                expanded_tokens.update(self._SYNONYM_MAP[t])

        scored: list[tuple[float, Capability]] = []
        anchor_caps: list[Capability] = []

        for cap in all_caps:
            # Check if anchor
            if any(anchor in cap.name.lower() for anchor in self._CORE_ANCHOR_PATTERNS):
                anchor_caps.append(cap)

            score = 0.0
            cap_text = f"{cap.name} {cap.domain} {cap.category} {cap.description} {' '.join(cap.tags)}".lower()
            cap_tokens = set(re.findall(r"\w+", cap_text))
            
            # Exact token overlaps
            overlap = raw_tokens.intersection(cap_tokens)
            if overlap:
                score += len(overlap) * 3.0

            # Synonym overlaps
            syn_overlap = expanded_tokens.intersection(cap_tokens)
            if syn_overlap:
                score += len(syn_overlap) * 1.5
            
            # Substring match on capability name
            for t in expanded_tokens:
                if len(t) >= 3 and t in cap.name.lower():
                    score += 4.0

            scored.append((score, cap))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Merge top scored with anchor capabilities (deduplicated)
        selected_map: dict[str, Capability] = {}
        
        # Add high-scoring candidates first
        for score, cap in scored:
            if len(selected_map) >= max_candidates:
                break
            selected_map[cap.name] = cap

        # Ensure anchor capabilities are present if room permits
        for cap in anchor_caps:
            if len(selected_map) >= max_candidates:
                break
            if cap.name not in selected_map:
                selected_map[cap.name] = cap

        return list(selected_map.values())

    def _build_tool_schema(self, capabilities: list[Capability]) -> list[dict[str, Any]]:
        """
        Derive tool function schemas from live capabilities, plus universal chat and clarification tools.
        """
        tools: list[dict[str, Any]] = []

        # 1. Registered live capabilities
        for cap in capabilities:
            fn_name = cap.name.replace(".", "__")
            description = cap.description or f"Execute {cap.name} capability in domain {cap.domain}"
            params = cap.input_schema if cap.input_schema else {"type": "object", "properties": {}}

            tools.append({
                "type": "function",
                "function": {
                    "name": fn_name,
                    "description": f"[{cap.domain.upper()}] {description} (Risk: {cap.risk_level.value})",
                    "parameters": params,
                },
            })

        # 2. Universal general conversation tool
        tools.append({
            "type": "function",
            "function": {
                "name": "conversation__general_chat",
                "description": "Engage in general conversation, answer general knowledge queries, greetings, or chit-chat that does not require executing a system capability.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Brief topic or summary of the conversational query"},
                    },
                },
            },
        })

        # 3. Universal clarification tool (for ambiguous or incomplete user requests)
        tools.append({
            "type": "function",
            "function": {
                "name": "system__clarification",
                "description": "Ask the user for clarification when the request is ambiguous, underspecified, or refers to unknown entities/actions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Clarification question to present to the user"},
                    },
                    "required": ["question"],
                },
            },
        })

        return tools

    def _build_system_prompt(self, capabilities: list[Capability]) -> str:
        return (
            "You are the AuraAI Intent Classification Engine. "
            "Your task is to select the single best matching capability tool that satisfies the user's intent. "
            "You must invoke the appropriate tool with accurate arguments extracted from the user's request. "
            "If the request is general conversation or knowledge QA, invoke 'conversation__general_chat'. "
            "Ambiguity Rule: When the user's intent is incomplete, refers to unspecified entities or pronouns ('it', 'that', 'this', 'them') without clear antecedent, "
            "or could reasonably apply to multiple different capabilities or targets, you MUST invoke 'system__clarification' to ask for clarification rather than assuming or guessing an action."
        )

    async def classify(
        self,
        utterance: str,
        conversation_context: list[dict] | None = None,
    ) -> ClassificationResult:
        """
        Classify user utterance into a registered capability intent.
        """
        # Pull active, operational capabilities only
        all_live = self._registry.list(require_live=True)
        if not all_live:
            logger.warning("[IntentClassifier] No live capabilities found in registry.")
            return self._fail_closed(utterance, reason="no_live_capabilities")

        # Select relevant candidates to stay well under API ceilings (max 40)
        capabilities = self._select_candidate_capabilities(utterance, all_live, max_candidates=40)

        cap_map = {cap.name.replace(".", "__"): cap for cap in capabilities}
        cap_map_canonical = {cap.name: cap for cap in capabilities}
        tools = self._build_tool_schema(capabilities)

        messages = [
            {"role": "system", "content": self._build_system_prompt(capabilities)},
        ]
        if conversation_context:
            messages.extend(conversation_context)
        messages.append({"role": "user", "content": utterance})

        raw_output: str | None = None
        parsed: ParsedToolCall | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await self._call_llm(messages, tools, timeout=self.timeout_seconds)
                raw_output = str(response)
                parsed = self._validate(response, cap_map, cap_map_canonical)

                if parsed.is_valid and parsed.confidence >= self.confidence_threshold:
                    self._log_for_corpus(utterance, raw_output, parsed, validated=True)

                    # Explicit clarification tool invocation
                    if parsed.capability_name == "system.clarification":
                        question = parsed.parameters.get("question") or self._build_clarification(utterance, parsed)
                        return ClassificationResult(
                            outcome=ClassificationOutcome.NEEDS_CLARIFICATION,
                            intent=None,
                            confidence=parsed.confidence,
                            raw_llm_output=raw_output,
                            capability_name=None,
                            clarification_prompt=question,
                        )

                    return ClassificationResult(
                        outcome=ClassificationOutcome.RESOLVED,
                        intent=Intent(name=parsed.capability_name or "", data=parsed.parameters),
                        confidence=parsed.confidence,
                        raw_llm_output=raw_output,
                        capability_name=parsed.capability_name,
                    )

                if attempt < MAX_RETRIES:
                    logger.debug(
                        "[IntentClassifier] Validation failed on attempt %d (%s), retrying with feedback.",
                        attempt + 1,
                        parsed.error,
                    )
                    messages.append({
                        "role": "system",
                        "content": f"The previous tool call had an error: {parsed.error}. Please select a valid tool and parameters.",
                    })
                    continue

            except asyncio.TimeoutError:
                logger.warning("[IntentClassifier] LLM call timed out after %0.2fs", self.timeout_seconds)
                return self._fail_closed(utterance, reason="timeout")
            except Exception as exc:
                logger.error("[IntentClassifier] LLM execution error: %s", exc)
                return self._fail_closed(utterance, reason=f"llm_error:{type(exc).__name__}")

        # Retries exhausted without valid resolution -> fail closed to clarification
        self._log_for_corpus(utterance, raw_output, parsed, validated=False)
        return ClassificationResult(
            outcome=ClassificationOutcome.NEEDS_CLARIFICATION,
            intent=None,
            confidence=parsed.confidence if parsed else 0.0,
            raw_llm_output=raw_output,
            capability_name=None,
            clarification_prompt=self._build_clarification(utterance, parsed),
        )

    async def _call_llm(self, messages: list[dict], tools: list[dict], timeout: float) -> Any:
        pm = self._get_provider_manager()
        # Clamp timeout to 200ms floor to guarantee transport buffer exceeds Windows timer resolution (~15.6ms)
        effective_timeout = max(0.2, timeout)
        transport_timeout = max(0.1, effective_timeout * 0.90)
        return await asyncio.wait_for(
            asyncio.to_thread(
                pm.chat_with_tools,
                messages=messages,
                tools=tools,
                model=self.model,
                temperature=0.0,
                tool_choice="required",
                timeout=transport_timeout,
            ),
            timeout=effective_timeout,
        )

    def _validate(
        self,
        response: Any,
        cap_map: dict[str, Capability],
        cap_map_canonical: dict[str, Capability],
    ) -> ParsedToolCall:
        """Extract and validate tool call against registered capabilities."""
        tool_calls = None

        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
        elif isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                tool_calls = msg.get("tool_calls")
        elif hasattr(response, "tool_calls"):
            tool_calls = response.tool_calls

        if not tool_calls:
            return ParsedToolCall(
                is_valid=False,
                capability_name=None,
                error="No tool calls emitted by model.",
                confidence=0.0,
            )

        tc = tool_calls[0]
        fn = getattr(tc, "function", tc.get("function") if isinstance(tc, dict) else None)
        if not fn:
            return ParsedToolCall(is_valid=False, capability_name=None, error="Malformed tool call object.")

        fn_name = getattr(fn, "name", fn.get("name") if isinstance(fn, dict) else "")
        raw_args = getattr(fn, "arguments", fn.get("arguments") if isinstance(fn, dict) else {})

        # Parse arguments
        args_dict: dict[str, Any] = {}
        if isinstance(raw_args, str):
            try:
                args_dict = json.loads(raw_args) if raw_args.strip() else {}
            except Exception as e:
                return ParsedToolCall(
                    is_valid=False,
                    capability_name=fn_name,
                    error=f"Invalid JSON arguments: {e}",
                    confidence=0.2,
                )
        elif isinstance(raw_args, dict):
            args_dict = raw_args

        # Handle built-in general conversation tool
        if fn_name in ("conversation__general_chat", "conversation.general_chat", "general_chat"):
            return ParsedToolCall(
                is_valid=True,
                capability_name="provider_chat",
                parameters=args_dict,
                confidence=1.0,
            )

        # Handle built-in clarification tool
        if fn_name in ("system__clarification", "system.clarification", "clarification"):
            return ParsedToolCall(
                is_valid=True,
                capability_name="system.clarification",
                parameters=args_dict,
                confidence=1.0,
            )

        # Resolve capability
        matched_cap = cap_map.get(fn_name) or cap_map_canonical.get(fn_name)
        if not matched_cap:
            canonical_name = fn_name.replace("__", ".")
            matched_cap = cap_map_canonical.get(canonical_name)

        if not matched_cap:
            return ParsedToolCall(
                is_valid=False,
                capability_name=fn_name,
                error=f"Tool '{fn_name}' does not correspond to any registered live capability.",
                confidence=0.0,
            )

        # Validate required parameters if schema provides required list
        schema = matched_cap.input_schema or {}
        required_fields = schema.get("required", [])
        for field_name in required_fields:
            if field_name not in args_dict:
                return ParsedToolCall(
                    is_valid=False,
                    capability_name=matched_cap.name,
                    error=f"Missing required parameter '{field_name}' for capability '{matched_cap.name}'.",
                    confidence=0.3,
                )

        return ParsedToolCall(
            is_valid=True,
            capability_name=matched_cap.name,
            parameters=args_dict,
            confidence=1.0,
        )

    def _build_clarification(self, utterance: str, parsed: ParsedToolCall | None) -> str:
        return f"I'm not quite sure how to handle '{utterance}'. Could you clarify what you'd like to do?"

    def _fail_closed(self, utterance: str, reason: str) -> ClassificationResult:
        self._log_for_corpus(utterance, raw_output=None, parsed=None, validated=False, fail_reason=reason)
        return ClassificationResult(
            outcome=ClassificationOutcome.FAILED_CLOSED,
            intent=None,
            confidence=0.0,
            raw_llm_output=None,
            capability_name=None,
            clarification_prompt="I couldn't process that request right now. Please try again.",
        )

    def _log_for_corpus(
        self,
        utterance: str,
        raw_output: str | None,
        parsed: ParsedToolCall | None,
        validated: bool,
        fail_reason: str | None = None,
    ) -> None:
        """Log classification event to corpus / telemetry."""
        logger.info(
            "intent_classification",
            extra={
                "utterance": utterance,
                "raw_llm_output": raw_output,
                "chosen_capability": parsed.capability_name if parsed else None,
                "confidence": parsed.confidence if parsed else 0.0,
                "validated": validated,
                "fail_reason": fail_reason or (parsed.error if parsed and not parsed.is_valid else None),
                "timestamp": time.time(),
            },
        )
