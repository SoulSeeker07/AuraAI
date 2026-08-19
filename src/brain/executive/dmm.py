"""
Layer 1: Decision Making Module (DMM) — The Executive
=====================================================

The DMM is responsible for understanding the user's intention,
not classifying keywords.

For every request it answers:
    What is the user's goal?
    ↓
    What information do I already know?
    ↓
    Do I have enough information?
    ↓
    Can I infer the missing details?
    ↓
    Should I ask a clarification?
    ↓
    Which capabilities are required?
    ↓
    Build an execution map.

The DMM never executes anything. It only thinks.
Its output is an ExecutionMap (or an AskUser request).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .execution_map import (
    Capability,
    ExecutionMap,
    ExecutionStep,
    FallbackOption,
    StepType,
    SuccessCriteria,
)

logger = logging.getLogger(__name__)


class ClarificationRequest:
    """DMM output when it needs more information from the user."""

    def __init__(
        self, question: str, missing: list[str], suggestions: list[str] | None = None
    ):
        self.question = question
        self.missing = missing
        self.suggestions = suggestions or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "clarification",
            "question": self.question,
            "missing": self.missing,
            "suggestions": self.suggestions,
        }


# ── Intent Templates ─────────────────────────────────────────────────────────
# Fixed, deterministic intent builders — the DMM maps understood goals
# onto structured execution maps, not free-form instructions.

_APP_ALIASES: dict[str, str] = {
    "notepad": "notepad",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "spotify": "spotify",
    "calculator": "calc",
    "calc": "calc",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "browser": "chrome",
    "web browser": "chrome",
}

_BROWSER_URLS: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "amazon": "https://www.amazon.com",
    "stackoverflow": "https://stackoverflow.com",
    "google drive": "https://drive.google.com",
    "netflix": "https://www.netflix.com",
}

_BROWSER_APPS = {"chrome", "msedge", "firefox", "opera", "brave"}


class DecisionMakingModule:
    """
    The Executive. Understands goals, selects capabilities, builds ExecutionMaps.

    This module does NOT execute anything. It only produces ExecutionMaps
    or ClarificationRequests.
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        memory: Any | None = None,
        workspace: Any | None = None,
    ):
        """
        Initialize the DMM.

        Args:
            llm_client: Optional Groq/LLM client for natural language understanding.
            memory: Optional memory manager for context recall.
            workspace: Optional workspace manager for workspace awareness.
        """
        self.llm_client = llm_client
        self.memory = memory
        self.workspace = workspace

    # ── Public API ──────────────────────────────────────────────────────────

    def analyze(
        self, user_input: str, context: dict[str, Any] | None = None
    ) -> ExecutionMap | ClarificationRequest:
        """
        Analyze a user request and produce an ExecutionMap or ClarificationRequest.

        This is the ONLY public entry point. The DMM never executes — it thinks.

        Args:
            user_input: The user's raw text request.
            context: Optional context dict (workspace state, memory, etc.)

        Returns:
            ExecutionMap or ClarificationRequest
        """
        context = context or {}
        text = user_input.strip()

        # 1. Understand the goal
        goal, modifiers = self._understand_goal(text, context)

        # 2. Check learned behavior rules (consult before planning)
        learned_rule = self._consult_learned_rules(text, context)
        if learned_rule:
            logger.info(f"DMM consulting learned rule: {learned_rule}")
            goal = learned_rule.get("resolved_goal", goal)

        # 3. Build the execution map
        execution_map = self._build_execution_map(goal, text, modifiers, context)

        # 4. Validate the map
        valid, errors = execution_map.validate()
        if not valid:
            logger.warning(f"DMM produced invalid ExecutionMap: {errors}")
            # Fallback to a safe provider-based map
            return self._fallback_provider_map(text, errors)

        logger.info(f"DMM produced {execution_map.log_summary()}")
        return execution_map

    # ── Goal Understanding ──────────────────────────────────────────────────

    def _understand_goal(
        self, text: str, context: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """
        Understand what the user is trying to accomplish.

        Returns:
            (goal, modifiers) — goal is the normalized intent,
            modifiers contains inferred parameters.
        """
        text_lower = text.lower()
        modifiers: dict[str, Any] = {}

        # ── Desktop App Launch ──────────────────────────────────────────────
        # "Open YouTube in Chrome" → goal="launch_app", app="chrome",
        #                             navigate="youtube"
        for alias, app in _APP_ALIASES.items():
            if alias in text_lower:
                modifiers["app"] = app
                modifiers["app_alias"] = alias
                # Check for "another instance" modifier
                if "another" in text_lower or "new instance" in text_lower:
                    modifiers["new_instance"] = True
                break

        # ── Browser Navigation ──────────────────────────────────────────────
        # "Open YouTube in Chrome" → also need to navigate to youtube
        for site, url in _BROWSER_URLS.items():
            if site in text_lower and any(
                w in text_lower
                for w in [
                    "open",
                    "go to",
                    "navigate",
                    "browse",
                    "visit",
                    "take me to",
                    "load",
                ]
            ):
                modifiers["url"] = url
                modifiers["site"] = site
                break

        # Direct URL
        url_match = re.search(r"(?:https?://|data:text/html)[^\s,]+", text)
        if url_match:
            modifiers["url"] = url_match.group(0)

        # ── Research / Search ───────────────────────────────────────────────
        research_indicators = [
            "research",
            "search for",
            "look up",
            "find information",
            "find out",
            "conversion rate",
            "exchange rate",
            "currency",
            "usd to inr",
        ]
        
        # Don't classify as research if they just want the definition
        is_definition = any(
            w in text_lower for w in ["what does", "what is the meaning of", "mean?", " mean"]
        ) and not any(
            w in text_lower for w in ["current", "today", "now", "latest"]
        )
        
        if not is_definition and any(ind in text_lower for ind in research_indicators):
            # Extract the topic
            for ind in research_indicators:
                if ind in text_lower:
                    if ind in ["conversion rate", "exchange rate", "currency", "usd to inr", "rate"]:
                        topic = text_lower.strip('?.,')
                    else:
                        topic = text_lower.split(ind, 1)[1].strip()
                        # Clean up trailing punctuation like ?
                        topic = topic.strip('?.,')
                        if not topic:
                            # If the indicator is at the end, use the whole query as the topic
                            topic = text_lower.strip('?.,')
                    modifiers["research_topic"] = topic
                    break

        # ── Engineering / Coding ────────────────────────────────────────────
        coding_indicators = [
            "implement",
            "code",
            "refactor",
            "fix bug",
            "unit test",
            "debug",
            "create function",
            "write script",
            "build feature",
        ]
        if any(ind in text_lower for ind in coding_indicators):
            modifiers["engineering"] = True
            modifiers["task"] = text

        # ── Session Summary ─────────────────────────────────────────────────
        if any(
            w in text_lower
            for w in [
                "summarize today's session",
                "summarize session",
                "session summary",
            ]
        ):
            modifiers["session_summary"] = True

        # ── Memory / Fact Recall ────────────────────────────────────────────
        if any(
            w in text_lower
            for w in [
                "remember",
                "what do you know",
                "my facts",
                "preferences",
                "profile",
            ]
        ):
            modifiers["memory_op"] = "recall"

        if any(
            w in text_lower for w in ["remember that", "store this", "save in memory"]
        ):
            modifiers["memory_op"] = "write"

        # ── Chat / casual conversation ──────────────────────────────────────
        if not modifiers:
            modifiers["chat"] = True

        return text, modifiers

    # ── Execution Map Builder ───────────────────────────────────────────────

    def _build_execution_map(
        self,
        goal: str,
        original_text: str,
        modifiers: dict[str, Any],
        context: dict[str, Any],
    ) -> ExecutionMap:
        """Build a structured execution map from understood goal and modifiers."""

        # ── Desktop + Browser: "Open YouTube in Chrome" ────────────────────
        if modifiers.get("app") and modifiers.get("url"):
            return self._map_browser_navigation(modifiers, original_text)

        # ── Desktop App Launch ──────────────────────────────────────────────
        if modifiers.get("app") and not modifiers.get("url"):
            return self._map_app_launch(modifiers, original_text)

        # ── Direct browser navigation ───────────────────────────────────────
        if modifiers.get("url") and not modifiers.get("app"):
            return self._map_direct_url(modifiers, original_text)

        # ── Research ────────────────────────────────────────────────────────
        if modifiers.get("research_topic"):
            return self._map_research(modifiers, original_text)

        # ── Engineering / Coding ────────────────────────────────────────────
        if modifiers.get("engineering"):
            return self._map_engineering(modifiers, original_text)

        # ── Session Summary ─────────────────────────────────────────────────
        if modifiers.get("session_summary"):
            return self._map_session_summary(modifiers, original_text)

        # ── Memory operations ───────────────────────────────────────────────
        if modifiers.get("memory_op") == "recall":
            return self._map_memory_recall(modifiers, original_text)

        if modifiers.get("memory_op") == "write":
            return self._map_memory_write(modifiers, original_text)

        # ── Chat / General conversation ─────────────────────────────────────
        return self._map_chat(modifiers, original_text)

    # ── Specific Map Builders ───────────────────────────────────────────────

    def _map_browser_navigation(
        self, modifiers: dict[str, Any], original: str
    ) -> ExecutionMap:
        """Open a browser and navigate to a URL."""
        app = modifiers.get("app", "chrome")
        url = modifiers.get("url", "https://www.google.com")
        site = modifiers.get("site", url)
        new_instance = modifiers.get("new_instance", False)

        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.CHECK,
                description=f"Check if {app} is already running",
                capability=Capability.DESKTOP,
                parameters={"app_name": app, "operation": "check_running"},
                retries=0,
                timeout=5,
            ),
            ExecutionStep(
                step_type=StepType.LAUNCH,
                description=(
                    f"Launch {app}"
                    if new_instance
                    else f"Launch {app} if not already running"
                ),
                capability=Capability.DESKTOP,
                parameters={
                    "app_name": app,
                    "operation": "launch",
                    "new_instance": new_instance,
                },
                retries=1,
                timeout=15,
            ),
            ExecutionStep(
                step_type=StepType.WAIT,
                description=f"Wait for {app} window to appear",
                capability=Capability.DESKTOP,
                parameters={"app_name": app, "wait_for": "window", "timeout": 10},
                retries=1,
                timeout=10,
            ),
            ExecutionStep(
                step_type=StepType.NAVIGATE,
                description=f"Navigate to {site}",
                capability=Capability.BROWSER,
                parameters={"url": url, "operation": "navigate", "app_name": app},
                retries=1,
                timeout=30,
            ),
            ExecutionStep(
                step_type=StepType.VERIFY,
                description=f"Verify page loaded: {site}",
                capability=Capability.BROWSER,
                parameters={"operation": "verify", "expect": site},
                retries=1,
                timeout=15,
            ),
        ]

        return ExecutionMap(
            goal=f"Open {site} in {app}",
            required_capabilities=[Capability.DESKTOP, Capability.BROWSER],
            execution_plan=steps,
            expected_result=f"{app} displays the {site} homepage",
            verification=SuccessCriteria(
                checks=[
                    f"{app} window exists",
                    f"Navigation to {site} succeeded",
                ],
                require_all=True,
            ),
            fallbacks=[
                FallbackOption(
                    trigger=f"{app} not found",
                    action=f"Try launching {app} via alternate path",
                    description="App launch failed — attempt alternate launcher",
                ),
                FallbackOption(
                    trigger="Navigation failed",
                    action=f"Retry navigating to {url}",
                    description="Browser navigation failed — retry once",
                ),
            ],
            metadata={"original_request": original, "site": site, "app": app},
        )

    def _map_app_launch(self, modifiers: dict[str, Any], original: str) -> ExecutionMap:
        """Launch a desktop application."""
        app = modifiers.get("app", "")
        new_instance = modifiers.get("new_instance", False)

        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.CHECK,
                description=f"Check if {app} is already running",
                capability=Capability.DESKTOP,
                parameters={"app_name": app, "operation": "check_running"},
                retries=0,
                timeout=5,
            ),
            ExecutionStep(
                step_type=StepType.LAUNCH,
                description=(
                    f"Launch a new instance of {app}"
                    if new_instance
                    else f"Launch {app}"
                ),
                capability=Capability.DESKTOP,
                parameters={
                    "app_name": app,
                    "operation": "launch",
                    "new_instance": new_instance,
                },
                retries=1,
                timeout=15,
            ),
            ExecutionStep(
                step_type=StepType.VERIFY,
                description=f"Verify {app} window exists",
                capability=Capability.DESKTOP,
                parameters={"app_name": app, "operation": "verify_window"},
                retries=1,
                timeout=10,
            ),
        ]

        return ExecutionMap(
            goal=f"Launch {app}",
            required_capabilities=[Capability.DESKTOP],
            execution_plan=steps,
            expected_result=f"{app} window is visible",
            verification=SuccessCriteria(
                checks=[f"{app} window exists"],
                require_all=True,
            ),
            fallbacks=[
                FallbackOption(
                    trigger=f"{app} not found",
                    action="Search for alternate executable path",
                    description="App not found at default path",
                ),
                FallbackOption(
                    trigger="Launch failed",
                    action=f"Retry launching {app}",
                    description="Launch failed — retry once",
                ),
            ],
            metadata={"original_request": original, "app": app},
        )

    def _map_direct_url(self, modifiers: dict[str, Any], original: str) -> ExecutionMap:
        """Navigate to a URL using the default browser."""
        url = modifiers.get("url", "")

        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.LAUNCH,
                description="Open default browser",
                capability=Capability.DESKTOP,
                parameters={"app_name": "browser", "operation": "launch_default_browser"},
                retries=1,
                timeout=15,
            ),
            ExecutionStep(
                step_type=StepType.NAVIGATE,
                description=f"Navigate to {url}",
                capability=Capability.BROWSER,
                parameters={"url": url, "operation": "navigate"},
                retries=1,
                timeout=30,
            ),
            ExecutionStep(
                step_type=StepType.VERIFY,
                description="Verify page loaded",
                capability=Capability.BROWSER,
                parameters={"operation": "verify", "expect": url},
                retries=1,
                timeout=15,
            ),
        ]

        return ExecutionMap(
            goal=f"Navigate to {url}",
            required_capabilities=[Capability.BROWSER, Capability.DESKTOP],
            execution_plan=steps,
            expected_result=f"Browser displays {url}",
            verification=SuccessCriteria(
                checks=["Browser window exists", f"Navigation to {url} succeeded"],
                require_all=True,
            ),
            fallbacks=[
                FallbackOption(
                    trigger="Navigation failed",
                    action=f"Retry navigating to {url}",
                    description="Navigation failed — retry once",
                )
            ],
            metadata={"original_request": original, "url": url},
        )

    def _map_research(self, modifiers: dict[str, Any], original: str) -> ExecutionMap:
        """Research a topic."""
        topic = modifiers.get("research_topic", original)

        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.SEARCH,
                description=f"Research topic: {topic}",
                capability=Capability.RESEARCH,
                parameters={"query": topic, "mode": "standard"},
                retries=1,
                timeout=60,
            ),
            ExecutionStep(
                step_type=StepType.GENERATE,
                description="Synthesize research findings",
                capability=Capability.PROVIDER,
                parameters={"task": "synthesize", "topic": topic},
                retries=0,
                timeout=30,
            ),
            ExecutionStep(
                step_type=StepType.VERIFY,
                description="Verify research results are relevant",
                capability=Capability.RESEARCH,
                parameters={"operation": "verify_results", "topic": topic},
                retries=0,
                timeout=10,
            ),
        ]

        return ExecutionMap(
            goal=f"Research: {topic}",
            required_capabilities=[Capability.RESEARCH, Capability.PROVIDER],
            execution_plan=steps,
            expected_result=f"Comprehensive research summary on {topic}",
            verification=SuccessCriteria(
                checks=["Research results found", "Summary generated"],
                require_all=True,
            ),
            fallbacks=[
                FallbackOption(
                    trigger="Search failed",
                    action="Retry with different search terms",
                    description="Initial search failed — retry with refined query",
                )
            ],
            metadata={"original_request": original, "topic": topic},
        )

    def _map_engineering(
        self, modifiers: dict[str, Any], original: str
    ) -> ExecutionMap:
        """Engineering / coding task."""
        task = modifiers.get("task", original)

        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.CHECK,
                description="Inspect workspace structure",
                capability=Capability.FILESYSTEM,
                parameters={"operation": "inspect_workspace"},
                retries=0,
                timeout=10,
            ),
            ExecutionStep(
                step_type=StepType.EXECUTE,
                description=f"Execute engineering task: {task}",
                capability=Capability.ENGINEERING,
                parameters={"task": task, "operation": "execute_engineering"},
                retries=1,
                timeout=120,
            ),
            ExecutionStep(
                step_type=StepType.VERIFY,
                description="Verify engineering result",
                capability=Capability.ENGINEERING,
                parameters={"operation": "verify_result"},
                retries=1,
                timeout=30,
            ),
        ]

        return ExecutionMap(
            goal=f"Engineering: {task}",
            required_capabilities=[Capability.ENGINEERING, Capability.FILESYSTEM],
            execution_plan=steps,
            expected_result=f"Engineering task completed: {task}",
            verification=SuccessCriteria(
                checks=["Engineering task executed", "Result verified"],
                require_all=True,
            ),
            fallbacks=[
                FallbackOption(
                    trigger="Engineering failed",
                    action="Retry with adjusted parameters",
                    description="Engineering task failed — retry",
                )
            ],
            metadata={"original_request": original, "task": task},
        )

    def _map_session_summary(
        self, modifiers: dict[str, Any], original: str
    ) -> ExecutionMap:
        """Summarize the session."""
        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.READ,
                description="Read session history",
                capability=Capability.MEMORY,
                parameters={"operation": "read_session_history"},
                retries=0,
                timeout=10,
            ),
            ExecutionStep(
                step_type=StepType.GENERATE,
                description="Generate session summary",
                capability=Capability.PROVIDER,
                parameters={"task": "summarize_session"},
                retries=0,
                timeout=30,
            ),
        ]

        return ExecutionMap(
            goal="Summarize today's session",
            required_capabilities=[Capability.MEMORY, Capability.PROVIDER],
            execution_plan=steps,
            expected_result="A summary of everything we worked on today",
            verification=SuccessCriteria(
                checks=["Session history read", "Summary generated"],
                require_all=True,
            ),
            fallbacks=[],
            metadata={"original_request": original},
        )

    def _map_memory_recall(
        self, modifiers: dict[str, Any], original: str
    ) -> ExecutionMap:
        """Recall facts from memory."""
        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.READ,
                description="Search memory for relevant facts",
                capability=Capability.MEMORY,
                parameters={"operation": "search", "query": original},
                retries=0,
                timeout=10,
            ),
        ]

        return ExecutionMap(
            goal=f"Recall memory: {original}",
            required_capabilities=[Capability.MEMORY],
            execution_plan=steps,
            expected_result="Relevant facts from memory",
            verification=SuccessCriteria(
                checks=["Memory searched"],
                require_all=True,
            ),
            fallbacks=[],
            metadata={"original_request": original},
        )

    def _map_memory_write(
        self, modifiers: dict[str, Any], original: str
    ) -> ExecutionMap:
        """Write facts to memory."""
        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.WRITE,
                description=f"Store in memory: {original}",
                capability=Capability.MEMORY,
                parameters={"operation": "remember", "value": original},
                retries=0,
                timeout=10,
            ),
        ]

        return ExecutionMap(
            goal=f"Remember: {original}",
            required_capabilities=[Capability.MEMORY],
            execution_plan=steps,
            expected_result="Fact stored in memory",
            verification=SuccessCriteria(
                checks=["Memory write succeeded"],
                require_all=True,
            ),
            fallbacks=[],
            metadata={"original_request": original},
        )

    def _map_chat(self, modifiers: dict[str, Any], original: str) -> ExecutionMap:
        """General conversation."""
        steps: list[ExecutionStep] = [
            ExecutionStep(
                step_type=StepType.CALL,
                description="Generate conversational response",
                capability=Capability.PROVIDER,
                parameters={"task": "chat", "message": original},
                retries=0,
                timeout=30,
            ),
        ]

        return ExecutionMap(
            goal=f"Respond to: {original}",
            required_capabilities=[Capability.PROVIDER],
            execution_plan=steps,
            expected_result="A natural, helpful response",
            verification=SuccessCriteria(
                checks=["Response generated"],
                require_all=True,
            ),
            fallbacks=[],
            metadata={"original_request": original},
        )

    def _fallback_provider_map(self, text: str, errors: list[str]) -> ExecutionMap:
        """Build a safe fallback map when the DMM can't produce a valid map."""
        logger.warning(f"DMM fallback for invalid map: {errors}")
        return ExecutionMap(
            goal=f"Respond to: {text}",
            required_capabilities=[Capability.PROVIDER],
            execution_plan=[
                ExecutionStep(
                    step_type=StepType.CALL,
                    description="Generate conversational response",
                    capability=Capability.PROVIDER,
                    parameters={"task": "chat", "message": text},
                    retries=0,
                    timeout=30,
                )
            ],
            expected_result="A natural, helpful response",
            verification=SuccessCriteria(
                checks=["Response generated"],
                require_all=True,
            ),
            fallbacks=[],
            metadata={"dmm_error": errors},
        )

    # ── Learned Rules Consultation ──────────────────────────────────────────

    def _consult_learned_rules(
        self, text: str, context: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Check if a learned behavior rule applies to this request.

        The Learning Engine stores behavior rules that the DMM consults
        before planning.

        Example:
            User: "When I ask 'Summarize today's session', summarize everything we worked on."
            Stored: {trigger: "Summarize today's session", action: "Summarize RuntimeSession"}
        """
        try:
            from core.learning.rule_matcher import RuleMatcher

            store = context.get("behavior_store")
            if store:
                matcher = RuleMatcher(store)
                rule = matcher.match(text)
                if rule:
                    return {
                        "rule_id": rule.rule_id,
                        "resolved_goal": (
                            rule.behavior.get("action", rule.trigger)
                            if isinstance(rule.behavior, dict)
                            else rule.trigger
                        ),
                    }
        except Exception as e:
            logger.debug(f"Learned rules consultation skipped: {e}")

        return None

    def register_rules_store(self, store: Any) -> None:
        """Register a behavior store for learned rules consultation."""
        self._rules_store = store


__all__ = ["DecisionMakingModule", "ClarificationRequest"]
