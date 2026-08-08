"""
Layer 4: Execution Map Generator (Groq)
=======================================

This is the heart of Aura.

Instead of asking Groq "Answer this user", Aura asks:

    "You are AuraBrain.
     Below is the Context Manager output.
     Below is the World Model.
     Below are available capabilities.
     Create ONLY a JSON Execution Map.
     Do NOT answer the user.
     Do NOT explain.
     Return valid JSON."

Groq is thinking. Aura is executing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .capability_selector import CapabilitySelection
from .context_manager import ContextSnapshot
from .goal_analyzer import GoalAnalysis
from .world_model import WorldState

logger = logging.getLogger(__name__)

# ── System Prompt for Groq ──────────────────────────────────────────────────

_EXECUTION_MAP_SYSTEM_PROMPT = """You are AuraBrain, the Executive Runtime of Aura — an AI Operating System.

Your ONLY job is to produce a structured JSON Execution Map.
You do NOT answer the user.
You do NOT explain.
You do NOT generate code.
You ONLY return valid JSON.

The Execution Map schema is:
{
  "goal": "string — the user's primary goal",
  "capabilities": ["string — required engines: desktop, browser, research, engineering, memory, voice, provider"],
  "steps": [
    {
      "engine": "string — which engine executes this step",
      "action": "string — the action to perform",
      "parameters": { "key": "value" }
    }
  ],
  "verification": ["string — success criteria"],
  "fallbacks": [
    {
      "trigger": "string — error condition",
      "action": "string — recovery action"
    }
  ]
}

Rules:
1. Use ONLY the capabilities provided below.
2. Every step must reference a real engine.
3. Every action must be a real action that engine supports.
4. Include verification criteria for every goal.
5. Include fallbacks for likely failure modes.
6. Return ONLY valid JSON. No markdown. No comments."""


class ExecutionMapGenerator:
    """
    Generates structured Execution Maps using Groq.

    Groq is thinking. Aura is executing.
    """

    def __init__(self, llm_client: Any | None = None):
        """
        Initialize the Execution Map Generator.

        Args:
            llm_client: Optional Groq LLM client.
        """
        self.llm_client = llm_client

    def generate(
        self,
        user_input: str,
        context: ContextSnapshot,
        world_state: WorldState,
        goal_analysis: GoalAnalysis,
        capability_selection: CapabilitySelection,
    ) -> dict[str, Any]:
        """
        Generate a structured Execution Map.

        Priority:
        1. Use Groq LLM to generate the map (if available)
        2. Fallback to deterministic template-based generation

        Args:
            user_input: The user's raw request.
            context: Context snapshot from Context Manager.
            world_state: World state from World Model.
            goal_analysis: Goals from Goal Analyzer.
            capability_selection: Capabilities from Capability Selector.

        Returns:
            Execution Map as a dict.
        """
        # 1. Try Groq LLM generation
        if self.llm_client is not None:
            try:
                execution_map = self._generate_via_llm(
                    user_input,
                    context,
                    world_state,
                    goal_analysis,
                    capability_selection,
                )
                if execution_map:
                    return execution_map
            except Exception as e:
                logger.warning(f"LLM Execution Map generation failed: {e}")

        # 2. Fallback to deterministic template generation
        logger.info("Using deterministic Execution Map generation")
        return self._generate_deterministic(
            user_input, goal_analysis, capability_selection
        )

    # ── LLM Generation ──────────────────────────────────────────────────────

    def _generate_via_llm(
        self,
        user_input: str,
        context: ContextSnapshot,
        world_state: WorldState,
        goal_analysis: GoalAnalysis,
        capability_selection: CapabilitySelection,
    ) -> dict[str, Any] | None:
        """Generate an Execution Map using Groq."""
        # Build the prompt
        capabilities_desc = "\n".join(
            f"- {c.capability}: {c.action} ({c.description})"
            for c in capability_selection.capabilities
        )

        user_prompt = f"""USER REQUEST: {user_input}

CONTEXT:
{context.summarize()}

WORLD STATE:
{world_state.summarize()}

AVAILABLE CAPABILITIES:
{capabilities_desc}

Create the Execution Map JSON now."""

        response = self.llm_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": _EXECUTION_MAP_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )

        content = response.choices[0].message.content.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        execution_map = json.loads(content)
        logger.info(
            f"LLM generated Execution Map: {execution_map.get('goal', 'unknown')}"
        )
        return execution_map

    # ── Deterministic Generation ────────────────────────────────────────────

    def _generate_deterministic(
        self,
        user_input: str,
        goal_analysis: GoalAnalysis,
        capability_selection: CapabilitySelection,
    ) -> dict[str, Any]:
        """Generate an Execution Map using deterministic templates."""
        modifiers = goal_analysis.modifiers

        # ── Browser navigation ──────────────────────────────────────────────
        if modifiers.get("site") and modifiers.get("browser"):
            site = modifiers["site"]
            browser = modifiers["browser"]
            url = modifiers.get("url", f"https://www.{site}.com")
            return {
                "goal": f"Open {site} in {browser}",
                "capabilities": ["desktop", "browser"],
                "steps": [
                    {
                        "engine": "desktop",
                        "action": "check_running",
                        "parameters": {"application": browser},
                    },
                    {
                        "engine": "desktop",
                        "action": "launch_application",
                        "parameters": {"application": browser},
                    },
                    {
                        "engine": "browser",
                        "action": "navigate",
                        "parameters": {"url": url},
                    },
                    {
                        "engine": "browser",
                        "action": "verify",
                        "parameters": {"expect": site},
                    },
                ],
                "verification": [
                    f"{browser} window exists",
                    f"Navigation to {site} succeeded",
                ],
                "fallbacks": [
                    {
                        "trigger": f"{browser} not found",
                        "action": f"Try launching {browser} via alternate path",
                    },
                    {
                        "trigger": "Navigation failed",
                        "action": f"Retry navigating to {url}",
                    },
                ],
            }

        # ── App launch ──────────────────────────────────────────────────────
        if modifiers.get("app"):
            app = modifiers["app"]
            new_instance = modifiers.get("new_instance", False)
            return {
                "goal": f"Launch {app}",
                "capabilities": ["desktop"],
                "steps": [
                    {
                        "engine": "desktop",
                        "action": "check_running",
                        "parameters": {"application": app},
                    },
                    {
                        "engine": "desktop",
                        "action": "launch_application",
                        "parameters": {
                            "application": app,
                            "new_instance": new_instance,
                        },
                    },
                    {
                        "engine": "desktop",
                        "action": "verify_window",
                        "parameters": {"application": app},
                    },
                ],
                "verification": [f"{app} window exists"],
                "fallbacks": [
                    {
                        "trigger": f"{app} not found",
                        "action": "Search for alternate executable path",
                    }
                ],
            }

        # ── Research ────────────────────────────────────────────────────────
        if modifiers.get("research_topic"):
            topic = modifiers["research_topic"]
            return {
                "goal": f"Research: {topic}",
                "capabilities": ["research", "provider"],
                "steps": [
                    {
                        "engine": "research",
                        "action": "search",
                        "parameters": {"query": topic},
                    },
                    {
                        "engine": "provider",
                        "action": "synthesize",
                        "parameters": {"task": "synthesize", "topic": topic},
                    },
                ],
                "verification": ["Research results found", "Summary generated"],
                "fallbacks": [
                    {
                        "trigger": "Search failed",
                        "action": "Retry with different search terms",
                    }
                ],
            }

        # ── Engineering ─────────────────────────────────────────────────────
        if modifiers.get("engineering"):
            task = modifiers.get("task", user_input)
            return {
                "goal": f"Engineering: {task}",
                "capabilities": ["engineering", "filesystem"],
                "steps": [
                    {
                        "engine": "filesystem",
                        "action": "inspect_workspace",
                        "parameters": {},
                    },
                    {
                        "engine": "engineering",
                        "action": "execute",
                        "parameters": {"task": task},
                    },
                    {
                        "engine": "engineering",
                        "action": "verify",
                        "parameters": {},
                    },
                ],
                "verification": ["Engineering task executed", "Result verified"],
                "fallbacks": [
                    {
                        "trigger": "Engineering failed",
                        "action": "Retry with adjusted parameters",
                    }
                ],
            }

        # ── Session summary ─────────────────────────────────────────────────
        if modifiers.get("session_summary"):
            return {
                "goal": "Summarize today's session",
                "capabilities": ["memory", "provider"],
                "steps": [
                    {
                        "engine": "memory",
                        "action": "read_session_history",
                        "parameters": {},
                    },
                    {
                        "engine": "provider",
                        "action": "summarize",
                        "parameters": {"task": "summarize_session"},
                    },
                ],
                "verification": ["Session history read", "Summary generated"],
                "fallbacks": [],
            }

        # ── Memory operations ───────────────────────────────────────────────
        if modifiers.get("memory_op"):
            op = modifiers["memory_op"]
            return {
                "goal": f"Memory {op}",
                "capabilities": ["memory"],
                "steps": [
                    {
                        "engine": "memory",
                        "action": "search" if op == "recall" else "remember",
                        "parameters": {"query": user_input},
                    }
                ],
                "verification": ["Memory operation completed"],
                "fallbacks": [],
            }

        # ── Chat / general ──────────────────────────────────────────────────
        return {
            "goal": f"Respond to: {user_input}",
            "capabilities": ["provider"],
            "steps": [
                {
                    "engine": "provider",
                    "action": "chat",
                    "parameters": {"message": user_input},
                }
            ],
            "verification": ["Response generated"],
            "fallbacks": [],
        }


__all__ = ["ExecutionMapGenerator"]
