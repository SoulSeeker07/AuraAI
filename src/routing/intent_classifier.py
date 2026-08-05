"""
Intent Classifier (Level 2)

Uses AI to classify requests when keyword matching fails.

This is Level 2 of the three-level routing system.
It uses the LLM to understand the request intent.

Responsibility:
    - Determine which capability is best suited for complex requests
    - Not to execute the request, just to classify it
"""

import logging
from typing import Any

from .capability_types import CapabilityType
from .routing_result import RoutingResult

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    AI-based intent classifier for complex requests.

    This class uses the LLM to classify requests that don't match
    simple keyword patterns. It's Level 2 in the routing hierarchy.
    """

    def __init__(self, provider_manager=None):
        """
        Initialize intent classifier.

        Args:
            provider_manager: LLM provider for intent classification
        """
        self.provider_manager = provider_manager
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for intent classification.

        Returns:
            System prompt string
        """
        return """
You are an intent classifier for an AI operating system. Your job is to classify user requests
into appropriate capability types. Do not execute the request, only classify it.

Available capabilities:
- desktop: Window management, application launch/quit
- filesystem: File operations (create, delete, move, rename, read, write)
- browser: Web browsing, searching, navigation
- vision: Image analysis, OCR, visual recognition
- memory: Remembering facts, storing information
- knowledge: Information retrieval, summarization, explanation
- provider: LLM-based text generation and processing
- agent: Complex task execution by agents
- workflow: Multi-step workflows and orchestrations

Classification rules:
1. If the request is about operating the system (windows, apps), use DESKTOP
2. If the request is about files and folders, use FILESYSTEM
3. If the request is about web browsing, use BROWSER
4. If the request involves images/screenshots, use VISION
5. If the request asks Aura to remember something, use MEMORY
6. If the request asks for information or explanation, use KNOWLEDGE
7. If the request is for AI text generation, use PROVIDER
8. If the request is complex and requires agent execution, use AGENT
9. If the request involves multiple steps or workflows, use WORKFLOW

Respond in this exact format (JSON only, no additional text):
{"capability": "capability_type", "confidence": 0.0-1.0, "reasoning": "brief explanation"}
"""

    def classify(self, text: str) -> RoutingResult | None:
        """
        Classify a request using AI.

        Args:
            text: User request text

        Returns:
            RoutingResult if classification successful, None otherwise
        """
        if not self.provider_manager:
            logger.debug("No provider_manager available, returning None")
            return None

        try:
            # Call the LLM for classification
            response = self.provider_manager.generate(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=150,
            )

            # Parse the response
            result = self._parse_classification_response(response)

            if result:
                routing_result = RoutingResult(
                    capability=result["capability"],
                    confidence=result["confidence"],
                    priority="medium",  # AI classification is medium confidence
                )
                routing_result.metadata["classification_reason"] = result.get(
                    "reasoning", ""
                )
                routing_result.metadata["routing_level"] = "level2"  # AI-based routing

                return routing_result

        except Exception as e:
            logger.error(f"Intent classification error: {e}", exc_info=True)

        return None

    def _parse_classification_response(self, response: str) -> dict[str, Any] | None:
        """
        Parse the LLM's classification response.

        Args:
            response: LLM response string

        Returns:
            Parsed classification dictionary or None
        """
        try:
            # Extract JSON from response
            # The LLM should return JSON, but we'll handle various formats
            import json

            # Try to find JSON in the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                # Validate and return
                if "capability" in data and "confidence" in data:
                    capability_value = data["capability"].lower()
                    confidence = float(data["confidence"])

                    # Map capability string to enum
                    capability_map = {
                        "desktop": CapabilityType.DESKTOP,
                        "filesystem": CapabilityType.FILESYSTEM,
                        "browser": CapabilityType.BROWSER,
                        "vision": CapabilityType.VISION,
                        "memory": CapabilityType.MEMORY,
                        "knowledge": CapabilityType.KNOWLEDGE,
                        "provider": CapabilityType.PROVIDER,
                        "agent": CapabilityType.AGENT,
                        "workflow": CapabilityType.WORKFLOW,
                    }

                    if capability_value in capability_map:
                        return {
                            "capability": capability_map[capability_value],
                            "confidence": min(confidence, 1.0),
                            "reasoning": data.get("reasoning", ""),
                        }

            # If parsing fails, return None
            logger.warning(
                f"Failed to parse classification response: {response[:100]}..."
            )

        except Exception as e:
            logger.error(f"Error parsing classification response: {e}")

        return None
