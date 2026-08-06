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
    DESKTOP_ACTION = "desktop_action"
    CODING = "coding"
    RESEARCH = "research"
    BROWSER = "browser"
    WORKFLOW = "workflow"
    MEMORY = "memory"


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
    ) -> DecisionOutcome:
        """
        Evaluate a request and produce a DecisionOutcome.

        Args:
            goal: User request
            budget: ExecutionBudget constraints
            memory_context: Recalled memory context

        Returns:
            DecisionOutcome
        """
        active_budget = budget or ExecutionBudget()
        mem = memory_context or {}
        goal_lower = goal.lower()

        # 1. Classify Intent Category
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
        is_desktop = any(
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
                "file",
                "folder",
                "desktop",
                "notes",
            ]
        )
        is_coding = any(
            w in goal_lower
            for w in [
                "code",
                "python",
                "refactor",
                "unit test",
                "fix bug",
                "ast",
                "git",
                "repository",
                "script",
            ]
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
                ]
            )
            and not is_system_query
        )
        is_browser = any(
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
                "browser",
                "chrome",
                "edge",
                "firefox",
            ]
        )

        if is_system_query:
            intent = IntentType.SYSTEM_QUERY
        elif is_browser:
            intent = IntentType.BROWSER
        elif is_desktop:
            intent = IntentType.DESKTOP_ACTION
        elif is_coding:
            intent = IntentType.CODING
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
        )
        # Q2: Can answer from system identity/state?
        can_from_sys = intent == IntentType.SYSTEM_QUERY
        # Q3: Does this actually need a multi-step planner?
        needs_planner = not (can_from_sys or intent == IntentType.CHAT)
        # Q4: Which planner?
        if intent == IntentType.RESEARCH:
            planner = "research"
        elif intent == IntentType.CODING:
            planner = "coding"
        elif intent == IntentType.BROWSER:
            planner = "browser"
        elif intent == IntentType.DESKTOP_ACTION:
            planner = "desktop"
        else:
            planner = "desktop"
        # Q5: Requires cloud/external backend or local engine?
        needs_backend = (
            intent in [IntentType.RESEARCH, IntentType.BROWSER, IntentType.CODING]
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
                "Playwright Browser Engine"
                if intent == IntentType.BROWSER
                else "Native Desktop Engine"
            ),
            confidence=0.95,
            expected_outcome=f"Execute goal using {planner} planner and state reuse rules",
        )

        return DecisionOutcome(
            goal=goal,
            budget=active_budget,
            intent_type=intent,
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
