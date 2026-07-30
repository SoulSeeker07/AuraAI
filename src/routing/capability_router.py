"""
Capability Router (Main Orchestration)

Main router that coordinates all three levels of routing.

This is the core of the Capability Router system. It coordinates:
- Level 1: Keyword Router (fast, local)
- Level 2: Intent Classifier (AI-based)
- Level 3: LLM Fallback (when nothing else matches)

Architecture:
    Aura Brain
         │
         ▼
    Capability Router
         │
     ┌───┼─────────────┬───────────────┬──────────────┐
     │   │             │               │              │
     ▼   ▼             ▼               ▼              ▼
  Desktop      Filesystem      Memory        Provider
  Plugin         Plugin        Manager       Manager
"""

import logging
from typing import Optional, Dict, Any, List
from .capability_types import CapabilityType, CapabilityPriority
from .routing_result import RoutingResult
from .keyword_router import KeywordRouter
from .intent_classifier import IntentClassifier

logger = logging.getLogger(__name__)


class CapabilityRouter:
    """
    Main capability router orchestrating all routing levels.

    The router answers one question: "Who should handle this request?"

    Routing Levels:
        1. Keyword Router: Fast local detection (no AI)
        2. Intent Classifier: AI-based classification
        3. LLM Fallback: General classification when needed
    """

    def __init__(self, provider_manager=None):
        """
        Initialize capability router.

        Args:
            provider_manager: LLM provider for intent classification
        """
        self.keyword_router = KeywordRouter()
        self.intent_classifier = IntentClassifier(provider_manager)

        logger.info("Capability Router initialized")

    def route(self, text: str) -> Optional[RoutingResult]:
        """
        Route request through all three levels of routing.

        This is the main entry point for routing decisions.

        Args:
            text: User request text

        Returns:
            RoutingResult with routing decision or None
        """
        logger.debug(f"Routing request: {text[:50]}...")

        # Level 1: Fast keyword-based routing
        result = self.keyword_router.route(text)
        if result:
            logger.debug(
                f"Level 1 matched: {result.capability.value} "
                f"(confidence: {result.confidence:.2f})"
            )
            return result

        # Level 2: AI-based intent classification
        logger.debug("Level 1 failed, trying Level 2 (intent classifier)")
        result = self.intent_classifier.classify(text)
        if result:
            logger.debug(
                f"Level 2 matched: {result.capability.value} "
                f"(confidence: {result.confidence:.2f})"
            )
            return result

        # Level 3: LLM fallback for general requests
        logger.debug("Level 2 failed, trying Level 3 (LLM fallback)")
        result = self._llm_fallback(text)
        if result:
            logger.debug(
                f"Level 3 matched: {result.capability.value} "
                f"(confidence: {result.confidence:.2f})"
            )
            return result

        # No match found
        logger.debug("No routing match found")
        return None

    def _llm_fallback(self, text: str) -> Optional[RoutingResult]:
        """
        LLM fallback for requests that don't match any specific pattern.

        This is Level 3 - used only when Level 1 and Level 2 fail.

        Args:
            text: User request text

        Returns:
            RoutingResult or None
        """
        # Simple heuristic: general requests go to PROVIDER (LLM)
        if self.intent_classifier.provider_manager:
            try:
                # Call LLM for general classification
                system_prompt = """
You are an AI assistant. Classify general user requests.
Most general requests should be classified as 'provider' (LLM).
Only classify specific operations into other categories.

Available categories: desktop, filesystem, browser, vision, memory, knowledge, provider, agent, workflow

Respond in JSON: {"capability": "provider", "confidence": 0.5, "reasoning": "general request"}
"""

                response = self.intent_classifier.provider_manager.generate(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.1,
                    max_tokens=100
                )

                # Parse and return result
                result = self.intent_classifier._parse_classification_response(response)
                if result:
                    routing_result = RoutingResult(
                        capability=result["capability"],
                        confidence=result["confidence"],
                        priority="low"  # LLM fallback has low confidence
                    )
                    routing_result.metadata["routing_level"] = "level3"
                    routing_result.metadata["classification_reason"] = result.get("reasoning", "")
                    return routing_result

            except Exception as e:
                logger.error(f"LLM fallback error: {e}", exc_info=True)

        # Default fallback
        return RoutingResult(
            capability=CapabilityType.PROVIDER,
            confidence=0.3,
            priority=CapabilityPriority.LOWEST
        )

    def get_supported_capabilities(self) -> List[CapabilityType]:
        """
        Get all supported capabilities.

        Returns:
            List of capability types
        """
        return [
            CapabilityType.DESKTOP,
            CapabilityType.FILESYSTEM,
            CapabilityType.TERMINAL,
            CapabilityType.BROWSER,
            CapabilityType.VISION,
            CapabilityType.VOICE,
            CapabilityType.MEMORY,
            CapabilityType.KNOWLEDGE,
            CapabilityType.PROVIDER,
            CapabilityType.AGENT,
            CapabilityType.WORKFLOW,
        ]

    def get_capability_description(self, capability_type: CapabilityType) -> str:
        """
        Get description of a capability.

        Args:
            capability_type: The capability type

        Returns:
            Description of the capability
        """
        descriptions = {
            CapabilityType.DESKTOP: "Desktop operations: window management, application launch/quit",
            CapabilityType.FILESYSTEM: "File operations: create, delete, move, rename, read, write files",
            CapabilityType.TERMINAL: "Terminal operations: command execution",
            CapabilityType.BROWSER: "Web operations: browsing, searching, navigation",
            CapabilityType.VISION: "Vision operations: image analysis, OCR, visual recognition",
            CapabilityType.VOICE: "Voice operations: speech-to-text, voice commands",
            CapabilityType.MEMORY: "Memory operations: storing and retrieving facts",
            CapabilityType.KNOWLEDGE: "Knowledge operations: information retrieval and explanation",
            CapabilityType.PROVIDER: "AI processing: text generation and LLM responses",
            CapabilityType.AGENT: "Agent operations: complex task execution by AI agents",
            CapabilityType.WORKFLOW: "Workflow operations: multi-step task orchestration",
        }

        return descriptions.get(capability_type, "Unknown capability")
