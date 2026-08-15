import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .agent_session import ExecutionBudget

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Primary intent categories for Aura DecisionEngine."""

    SYSTEM_QUERY = "system_query"
    CHAT = "chat"
    VISION = "vision"
    DESKTOP_ACTION = "desktop_action"
    CODING = "coding"
    RESEARCH = "research"
    BROWSER = "browser"
    WORKFLOW = "workflow"
    MEMORY = "memory"
    SESSION = "session"
    LEARNING = "learning"


@dataclass
class DecisionTrace:
    """Detailed reasoning trace explaining WHY a decision was made."""

    goal: str
    reasoning_steps: list[str] = field(default_factory=list)
    policy_applied: str = ""
    chosen_planner: str = ""
    chosen_backend: str = ""
    confidence: float = 0.95
    expected_outcome: str = ""
    actual_outcome: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "reasoning_steps": self.reasoning_steps,
            "policy_applied": self.policy_applied,
            "chosen_planner": self.chosen_planner,
            "chosen_backend": self.chosen_backend,
            "confidence": self.confidence,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
        }


@dataclass
class DecisionOutcome:
    """Outcome produced by DecisionEngine to direct the AgentSession."""

    goal: str
    budget: ExecutionBudget
    intent_type: IntentType = IntentType.CHAT
    capability: str = ""
    can_answer_from_memory: bool = False
    can_answer_from_system: bool = False
    needs_planner: bool = True
    preferred_planner: str = (
        "desktop"  # 'desktop', 'research', 'coding', 'browser', 'none'
    )
    needs_backend: bool = False
    should_parallel: bool = True
    should_ask_user: bool = False
    should_search_first: bool = False
    should_remember: bool = True
    should_verify: bool = True
    should_refuse: bool = False
    refusal_reason: str = ""
    decision_summary: str = ""
    memory_context: dict[str, Any] = field(default_factory=dict)
    trace: DecisionTrace | None = None


class DecisionEngine:
    """
    Executive decision engine evaluating reasoning, risk, budget, policies,
    and the 5-question planner decision tree.
    """

    def evaluate(
        self,
        goal: str,
        budget: ExecutionBudget | None = None,
        memory_context: dict[str, Any] | None = None,
        context: Any = None,
    ) -> DecisionOutcome:
        """
        Evaluate a request and produce a DecisionOutcome.

        Args:
            goal: User request
            budget: ExecutionBudget constraints
            memory_context: Recalled memory context
            context: Optional conversational PendingQuestion context

        Returns:
            DecisionOutcome
        """
        active_budget = budget or ExecutionBudget()
        mem = memory_context or {}
        goal_lower = goal.lower()

        # Check if context is a pending question
        is_pending_question = context is not None and (
            hasattr(context, "slot") or context.__class__.__name__ == "PendingQuestion"
        )

        is_session_summary = any(
            w in goal_lower
            for w in [
                "summarize today's session",
                "summarize session",
                "session summary",
                "summarize what we did today",
                "what have we done today",
                "what we worked on today",
            ]
        )

        # Separate Memory Recall vs Memory Write
        is_memory_recall = any(
            w in goal_lower
            for w in [
                "what is my",
                "what's my",
                "do you remember",
                "which is my",
                "tell me my",
                "who is",
                "where is my",
            ]
        ) or (
            any(
                w in goal_lower
                for w in ["favorite", "favourite", "preference", "preferences"]
            )
            and any(
                w in goal_lower
                for w in ["what", "which", "where", "tell me", "do you know", "show"]
            )
        )

        is_memory_write = not is_memory_recall and (
            is_pending_question
            or any(
                w in goal_lower
                for w in [
                    "remember",
                    "recall",
                    "forget",
                    "memorize",
                    "store in memory",
                    "save in memory",
                ]
            )
            or any(
                w in goal_lower
                for w in ["my favorite", "my favourite", "i like", "i prefer"]
            )
        )

        is_system_query = any(
            w in goal_lower
            for w in [
                "what are you",
                "who are you",
                "capabilities you currently have",
                "what capabilities",
                "what can you do",
                "can't you do",
                "cannot do",
                "limitation",
                "limitations",
                "what planners",
                "what backends",
                "what commands",
                "tell me about yourself",
                "your status",
                "system status",
                "architecture",
            ]
        )
        # Desktop window control / app management takes precedence over browsing
        app_verbs = [
            "open",
            "launch",
            "start",
            "bring",
            "focus",
            "close",
            "activate",
            "maximize",
            "minimize",
            "restore",
            "switch to",
        ]
        app_names = [
            "chrome",
            "google chrome",
            "edge",
            "msedge",
            "firefox",
            "browser",
            "notepad",
            "calc",
            "calculator",
            "vscode",
            "vs code",
            "visual studio code",
            "spotify",
            "word",
            "excel",
            "powerpoint",
            "paint",
            "mspaint",
            "cmd",
            "powershell",
        ]

        has_app_verb = any(v in goal_lower for v in app_verbs)
        has_app_name = any(a in goal_lower for a in app_names)
        has_web_target = any(
            site in goal_lower
            for site in [
                "youtube",
                "github",
                "gmail",
                "google.com",
                "twitter",
                "reddit",
                "linkedin",
                "facebook",
                "instagram",
                "amazon",
                "netflix",
                "http://",
                "https://",
                "www.",
            ]
        )

        # Check if the utterance is a standalone application name (e.g. "Google Chrome", "Notepad", "WhatsApp")
        clean_goal_name = goal_lower.strip(". ,!?:;")
        is_standalone_app = clean_goal_name in app_names or any(
            clean_goal_name == f"open {a}" or clean_goal_name == f"launch {a}" for a in app_names
        )

        is_window_control = (
            is_standalone_app
            or (has_app_verb and has_app_name and not has_web_target)
            or any(
                w in goal_lower
                for w in [
                "bring to front",
                "bring chrome",
                "bring edge",
                "bring browser",
                "bring window",
                "focus chrome",
                "focus edge",
                "focus firefox",
                "focus window",
                "open chrome",
                "open edge",
                "open firefox",
                "open browser",
                "close chrome",
                "close edge",
                "close firefox",
                "close browser",
                "maximize",
                "minimize",
                "activate",
                "launch chrome",
                "launch edge",
            ])
        )

        is_desktop = is_window_control or any(
            w in goal_lower
            for w in [
                "open",
                "close",
                "minimize",
                "restore",
                "volume",
                "mute",
                "unmute",
                "clipboard",
                "monitor",
                "resolution",
                "battery",
                "charging",
                "network",
                "ip",
                "notepad",
                "create file",
                "write file",
                "folder",
                "desktop",
                "notes",
                "calc",
                "calculator",
                "chrome",
                "spotify",
                "vscode",
                "vs code",
                "visual studio code",
                # Keyboard input
                "type",
                "press",
                "hit",
                "write",
                # System radio / hardware controls
                "bluetooth",
                "wifi",
                "wi-fi",
                "airplane mode",
                "dark mode",
                "night light",
                "brightness",
                "turn off",
                "turn on",
                "enable",
                "disable",
            ]
        )

        # Refined coding detection: ignore IDE names when classifying coding intent
        clean_goal_for_coding = goal_lower
        for ide in [
            "vs code",
            "vscode",
            "visual studio code",
            "notepad",
            "sublime",
            "atom",
        ]:
            clean_goal_for_coding = clean_goal_for_coding.replace(ide, "")

        is_coding = (
            any(
                w in clean_goal_for_coding
                for w in [
                    "refactor",
                    "unit test",
                    "fix bug",
                    "ast",
                    "git",
                    "repository",
                    "script",
                    "code.analyze",
                    "code.edit",
                    "code.report",
                    "python script",
                    "write python",
                    "create python",
                    "generate python",
                ]
            )
            or (
                "code" in clean_goal_for_coding
                and any(
                    v in clean_goal_for_coding
                    for v in [
                        "write",
                        "create",
                        "implement",
                        "refactor",
                        "fix",
                        "test",
                        "modify",
                        "update",
                        "generate",
                        "run",
                        "add",
                        "change",
                        "synthesis",
                        "analyze",
                        "inspect",
                        "debug",
                        "explain",
                        "review",
                        "in",
                    ]
                )
            )
            or (
                "python" in clean_goal_for_coding
                and any(
                    v in clean_goal_for_coding
                    for v in [
                        "write",
                        "create",
                        "implement",
                        "refactor",
                        "fix",
                        "test",
                        "modify",
                        "update",
                        "generate",
                        "run",
                        "add",
                        "change",
                        "script",
                        "code",
                        "sort",
                        "analyze",
                    ]
                )
            )
        )

        is_definition = any(
            w in goal_lower for w in ["what does", "what is the meaning of", "mean?", " mean"]
        ) and not any(
            w in goal_lower for w in ["current", "today", "now", "latest"]
        )

        is_research = (
            any(
                w in goal_lower
                for w in [
                    "research",
                    "search web",
                    "look up",
                    "find papers",
                    "oauth2",
                    "release",
                    "conversion rate",
                    "exchange rate",
                    "currency",
                    "usd",
                    "inr",
                    " rate",
                ]
            )
            and not is_system_query
            and not is_definition
        )
        is_browser = not is_window_control and any(
            w in goal_lower
            for w in [
                "browse",
                "web page",
                "navigate",
                "url",
                "playwright",
                "instagram",
                "github",
                "amazon",
                "chatgpt",
                "youtube",
                "twitter",
                "reddit",
                "facebook",
                "linkedin",
                "shopping",
                "cart",
                "buy",
                "tab",
                "website",
                "http",
                "https",
                "site",
                "chrome",
                "browser",
                "edge",
                "firefox",
                "next",
                "previous",
                "pause",
                "resume",
                "seek",
                "skip",
                "filter",
                "comment",
                "comments",
                "review",
                "reviews",
                "checkout",
                "compare",
                "play",
                "video",
                "videos",
                "song",
                "songs",
                "music",
                "playlist",
            ]
        )

        is_vision_query = any(
            w in goal_lower
            for w in [
                "what's on my screen",
                "what is on my screen",
                "whats on my screen",
                "see my screen",
                "read my screen",
                "look at my screen",
                "on my screen",
                "take a screenshot",
                "capture screen",
                "describe screen",
                "what is visible on screen",
                "read the screen",
            ]
        )

        intent_capability = ""
        if is_session_summary:
            intent = IntentType.SESSION
            intent_capability = "session_summary"
        elif is_memory_write:
            intent = IntentType.MEMORY
            intent_capability = "memory_write"
        elif is_memory_recall:
            intent = IntentType.MEMORY
            intent_capability = "memory_read"
        elif is_vision_query:
            intent = IntentType.VISION
            intent_capability = "screen_vision"
        elif is_system_query:
            intent = IntentType.SYSTEM_QUERY
        elif is_coding:
            intent = IntentType.CODING
        elif is_browser:
            intent = IntentType.BROWSER
        elif is_desktop:
            intent = IntentType.DESKTOP_ACTION
        elif is_research:
            intent = IntentType.RESEARCH
        else:
            intent = IntentType.CHAT

        # 2. Evaluate 5 Decision Questions
        # Q1: Can answer from memory?
        can_from_mem = bool(
            mem.get("recalled_memories")
            and any(
                w in goal_lower
                for w in ["remember", "recall", "my name", "preferences"]
            )
        ) or (intent == IntentType.MEMORY)
        # Q2: Can answer from system identity/state?
        can_from_sys = intent == IntentType.SYSTEM_QUERY or intent == IntentType.SESSION
        # Q3: Does this actually need a multi-step planner?
        needs_planner = not (
            can_from_sys
            or intent == IntentType.CHAT
            or intent == IntentType.VISION
            or (intent == IntentType.SESSION and intent_capability == "session_summary")
        )
        # Q4: Which planner?
        if intent == IntentType.RESEARCH:
            planner = "research"
        elif intent == IntentType.CODING:
            planner = "coding"
        elif intent == IntentType.BROWSER:
            planner = "browser"
        elif intent == IntentType.DESKTOP_ACTION:
            planner = "desktop"
        elif intent == IntentType.MEMORY:
            planner = "memory"
        elif intent == IntentType.VISION:
            planner = "none"
        else:
            planner = "desktop"
        # Q5: Requires cloud/external backend or local engine?
        needs_backend = (
            intent
            in [
                IntentType.RESEARCH,
                IntentType.BROWSER,
                IntentType.CODING,
                IntentType.MEMORY,
            ]
        ) and not (active_budget.local_only or active_budget.offline_mode)

        should_search = (intent == IntentType.RESEARCH) and needs_backend
        should_parallel = active_budget.allow_parallel and any(
            w in goal_lower for w in ["and", ",", "while", "create", "open"]
        )

        # Local-only & Offline budget enforcement
        if active_budget.local_only or active_budget.offline_mode:
            should_search = False

        summary = (
            f"DecisionEngine evaluated goal [{intent.value}]: Memory={can_from_mem}, "
            f"System={can_from_sys}, NeedsPlanner={needs_planner}, Planner={planner}, "
            f"Backend={needs_backend}, Search={should_search}."
        )

        logger.info(summary)

        reasoning_steps = [
            f"Intent classified as '{intent.value}' based on prompt keywords.",
            f"Evaluated memory recall: can_from_memory={can_from_mem}.",
            f"Evaluated system identity: can_from_system={can_from_sys}.",
            f"Evaluated planner requirement: needs_planner={needs_planner}, selected planner='{planner}'.",
            "Evaluated execution policy: State Reuse Policy & Ownership Protection active.",
        ]

        trace = DecisionTrace(
            goal=goal,
            reasoning_steps=reasoning_steps,
            policy_applied="Inspect World -> Reuse State -> Protect User Resources",
            chosen_planner=planner,
            chosen_backend=(
                "MemoryBackend"
                if intent == IntentType.MEMORY
                else (
                    "Playwright Browser Engine"
                    if intent == IntentType.BROWSER
                    else "Native Desktop Engine"
                )
            ),
            confidence=0.95,
            expected_outcome=f"Execute goal using {planner} planner and state reuse rules",
        )

        import os
        verbosity = os.environ.get("AURA_VERBOSITY", "normal")
        if verbosity in ("developer", "debug", "trace"):
            print("\n" + "=" * 60)
            print("AURA ROUTING TRACE")
            print("=" * 60)
            print(f"Input       : {goal}")
            print(f"DMM intent  : {intent.value}")
            print(f"Decision    : {intent.value}")
            print(f"Planner     : {planner}")
            print(f"Backend     : {needs_backend}")
            print(f"Capability  : {intent_capability}")
            print("=" * 60 + "\n")

        return DecisionOutcome(
            goal=goal,
            budget=active_budget,
            intent_type=intent,
            capability=intent_capability,
            can_answer_from_memory=can_from_mem,
            can_answer_from_system=can_from_sys,
            needs_planner=needs_planner,
            preferred_planner=planner,
            needs_backend=needs_backend,
            should_parallel=should_parallel,
            should_ask_user=False,
            should_search_first=should_search,
            should_remember=True,
            should_verify=True,
            should_refuse=False,
            decision_summary=summary,
            memory_context=mem,
            trace=trace,
        )
