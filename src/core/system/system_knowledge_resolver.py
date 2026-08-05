"""
System Knowledge Resolver
Location: src/core/system/system_knowledge_resolver.py

Resolves system self-knowledge queries (identity, capabilities, planners, backends,
limitations, commands) deterministically directly from platform registries without calling external LLMs.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.backends.backend_registry import BackendRegistry
from src.core.orchestration.planner_registry import PlannerRegistry

logger = logging.getLogger(__name__)


class SystemKnowledgeResolver:
    """
    Deterministic self-knowledge answer engine for Aura AI.
    """

    @classmethod
    def resolve(cls, query: str, context: dict[str, Any] | None = None) -> str:
        q = query.lower().strip()

        # 1. Limitations Queries ("What can't you do?")
        if any(w in q for w in ["can't you do", "cannot do", "limitation", "what can you not"]):
            return (
                "Here are my current system limitations and unsupported domains:\n\n"
                "  • Android & iOS mobile automation\n"
                "  • Physical hardware & robotics interaction\n"
                "  • 3D CAD modeling & CAD software editing\n"
                "  • Unconnected email accounts or external services requiring 2FA without credentials\n"
                "  • Desktop applications not installed on this Windows machine"
            )

        # 2. Capabilities Queries ("What can you do?", "What are your capabilities?")
        if any(w in q for w in ["capability", "capabilities", "what can you do", "features"]):
            backend_registry = BackendRegistry.get_instance()
            backends = backend_registry.list_all_backends()
            total_caps = sum(len(b.get("capabilities", [])) for b in backends) if isinstance(backends, list) else 0

            return (
                f"I currently support {total_caps} registered capabilities across 4 core domains:\n\n"
                "🖥️ Desktop Automation:\n"
                "  • Application launch, focus, and state reuse\n"
                "  • Window management (restore, minimize, activate)\n"
                "  • Audio controls (volume, mute, unmute)\n"
                "  • Clipboard monitoring and system metrics\n\n"
                "🌐 Browser & E-Commerce Intelligence:\n"
                "  • Tab navigation, focus, and single tab-level closing\n"
                "  • Playwright automation & infinite scrolling\n"
                "  • Shopping search, price comparison, cart & checkout safety gates\n"
                "  • Semantic tab grouping (documentation, shopping, social)\n\n"
                "📚 Research & Knowledge:\n"
                "  • Multi-provider search (Tavily, Wikipedia, GitHub)\n"
                "  • Deep evidence extraction and citation merging\n\n"
                "💻 Autonomous Coding:\n"
                "  • Code analysis, refactoring, AST inspection, unit test generation"
            )

        # 3. Planners Queries ("What planners do you have?")
        if "planner" in q:
            planners = PlannerRegistry.get_instance().list_planners()
            if isinstance(planners, list):
                p_names = [p.title() if isinstance(p, str) else p.get("role", "").title() for p in planners]
                planner_str = "\n".join(f"  • {p} Planner" for p in p_names)
            else:
                planner_str = "\n".join(f"  • {k.title()} Planner" for k in planners.keys())
            return f"I have active role planners registered:\n\n{planner_str}"

        # 4. Backends Queries ("What backends do you have?")
        if "backend" in q:
            backends = BackendRegistry.get_instance().list_all_backends()
            b_lines = []
            if isinstance(backends, list):
                for b_info in backends:
                    if isinstance(b_info, dict):
                        caps = b_info.get("capabilities", [])
                        caps_str = ", ".join(caps[:6]) + ("..." if len(caps) > 6 else "")
                        b_lines.append(f"  • {b_info.get('name', 'Backend')} ({len(caps)} capabilities)\n    [{caps_str}]")
                    else:
                        b_lines.append(f"  • {b_info}")
            elif isinstance(backends, dict):
                for b_id, b_info in backends.items():
                    caps = b_info.get("capabilities", []) if isinstance(b_info, dict) else []
                    caps_str = ", ".join(caps[:6]) + ("..." if len(caps) > 6 else "")
                    b_lines.append(f"  • {b_info.get('name', b_id) if isinstance(b_info, dict) else b_id} ({len(caps)} capabilities)\n    [{caps_str}]")
            return f"I have registered execution backends:\n\n" + "\n\n".join(b_lines)

        # 5. Identity Queries ("Who are you?", "What are you?")
        if any(w in q for w in ["who are you", "what are you", "tell me about yourself", "who am i"]):
            return (
                "I am Aura, an AI Operating System designed to manage desktop state, "
                "browser operations, and cognitive workflows. I inspect your world state before acting, "
                "route tasks through specialized role planners (desktop, browser, coding, research), "
                "and execute operations via native backends while tracking resource ownership."
            )

        # Default fallback self-summary
        return (
            "I am Aura AI v17.0. All my capabilities, planners, backends, "
            "and execution policies are registered in my self-knowledge catalog."
        )
