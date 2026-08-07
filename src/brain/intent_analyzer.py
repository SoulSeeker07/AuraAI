from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ai.models import ChatRequest
from ai.provider_manager import ProviderManager


@dataclass
class IntentAnalysis:
    """Result of intent analysis with confidence scores."""

    intent: str
    confidence: float
    subintent: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    needs_web_search: bool = False
    needs_deep_research: bool = False
    specialized_sources: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


class IntentAnalyzer:
    """
    AI-powered intent analyzer that classifies user queries.
    Uses Groq to detect the user's intent instead of hardcoded keywords.
    """

    INTENT_SYSTEM_PROMPT = """You are an intent analyzer for Aura AI, an intelligent assistant.
Your job is to classify user queries into intents with confidence scores.

Available intent categories:
1. GENERAL_CHAT: Casual conversation, questions about Aura, chit-chat
2. LIVE_INFORMATION: Real-time facts (weather, scores, stock prices, news)
3. KNOWLEDGE_REQUEST: Educational questions, explanations, how-to guides
4. PROGRAMMING: Coding questions, debugging, API usage
5. NETWORKING: Network concepts, certifications, routing, switching
6. MEDICAL: Health questions, medical information (avoid diagnosis)
7. RESEARCH: Deep dive topics, comparisons, multi-source research
8. REMEMBER_FACT: User wants to save information for later
9. TIME_DATE: Date/time related queries
10. SETTINGS: Configuration and system-related queries
11. VISION: Screen capture and analysis requests
12. TASK_EXECUTION: Requests to perform actions
13. SPECIALIZED_ASK: Questions for specific domains
14. BROWSER_WEBSITE: Open websites, navigate pages, web interactions
15. MEDIA_CONTROL: Play, pause, resume, next, previous, seek, volume control
16. PRODUCT_SHOPPING: Product search, spec filtering, comparison, ratings
17. REVIEWS_COMMENTS: Inspecting, reading, and summarizing user comments and customer reviews
18. CART_CHECKOUT: Adding to cart, managing cart items, proceeding to checkout

Return JSON with:
- intent: the primary intent category (choose most appropriate)
- confidence: float between 0.0-1.0 (how sure you are)
- subintent: more specific category within the main intent (optional)
- category: mapped domain category (for routing)
- needs_web_search: true if this needs live web search
- needs_deep_research: true if this requires reading multiple sources
- specialized_sources: list of domains to prioritize (e.g., ["microsoft.com", "github.com"])
- data: any additional context extracted from the query

If unsure, set confidence to 0.3 or lower and include reasoning in metadata."""

    def __init__(
        self, provider_manager: ProviderManager, model: str = "llama3-70b-8192"
    ):
        self.provider_manager = provider_manager
        self.model = model

    def analyze(self, user_input: str) -> IntentAnalysis:
        """Analyze the user's intent using AI."""
        try:
            system_prompt = self.INTENT_SYSTEM_PROMPT

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]

            request = ChatRequest(
                messages=messages, model=self.model, temperature=0.1, max_tokens=300
            )

            response = self.provider_manager.chat(request)
            result = json.loads(response.text)

            return IntentAnalysis(
                intent=result.get("intent", "GENERAL_CHAT"),
                confidence=float(result.get("confidence", 0.5)),
                subintent=result.get("subintent"),
                category=result.get("category"),
                metadata={
                    "raw_response": result,
                    "reasoning": result.get("metadata", {}).get("reasoning", ""),
                },
                needs_web_search=bool(result.get("needs_web_search", False)),
                needs_deep_research=bool(result.get("needs_deep_research", False)),
                specialized_sources=result.get("specialized_sources", []),
                data=result.get("data", {}),
            )
        except json.JSONDecodeError:
            # Fallback to simple keyword-based analysis
            return self._fallback_analysis(user_input)
        except Exception:
            # Return general chat as fallback
            return IntentAnalysis(
                intent="GENERAL_CHAT", confidence=0.3, category="general"
            )

    def _fallback_analysis(self, user_input: str) -> IntentAnalysis:
        """Simple keyword-based fallback analysis when AI is unavailable."""
        input_lower = user_input.lower()

        # Check for specialized domains
        networking_keywords = [
            "network",
            "router",
            "switch",
            "ccna",
            "ccnp",
            "jncia",
            "juniper",
            "cisco",
            "firewall",
            "palo alto",
            "fortinet",
        ]
        programming_keywords = [
            "python",
            "java",
            "javascript",
            "react",
            "django",
            "api",
            "function",
            "code",
            "programming",
            "debug",
        ]
        medical_keywords = [
            "health",
            "symptom",
            "diagnosis",
            "doctor",
            "medicine",
            "medical",
            "covid",
        ]

        # Check for real-time information
        if any(
            word in input_lower
            for word in ["weather", "score", "stock", "price", "news"]
        ):
            return IntentAnalysis(
                intent="LIVE_INFORMATION", confidence=0.7, category="live"
            )

        # Check for research/education
        if any(
            word in input_lower
            for word in [
                "explain",
                "how",
                "why",
                "what",
                "compare",
                "difference",
                "vs",
                "tutorial",
                "guide",
            ]
        ):
            return IntentAnalysis(
                intent="KNOWLEDGE_REQUEST", confidence=0.8, category="knowledge"
            )

        # Check for specialized domains
        if any(word in input_lower for word in networking_keywords):
            return IntentAnalysis(
                intent="NETWORKING",
                confidence=0.9,
                category="networking",
                specialized_sources=["cisco.com", "microsoft.com", "juniper.net"],
            )

        if any(word in input_lower for word in programming_keywords):
            return IntentAnalysis(
                intent="PROGRAMMING",
                confidence=0.9,
                category="programming",
                specialized_sources=["github.com", "stackoverflow.com", "python.org"],
            )

        if any(word in input_lower for word in medical_keywords):
            return IntentAnalysis(
                intent="MEDICAL",
                confidence=0.7,
                category="medical",
                specialized_sources=["who.int", "mayoclinic.org", "cdc.gov"],
            )

        # Default to general chat
        return IntentAnalysis(intent="GENERAL_CHAT", confidence=0.5, category="general")
