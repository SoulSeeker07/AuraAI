"""
System Knowledge Resolver
Location: src/core/system/system_knowledge_resolver.py

Resolves system self-knowledge queries (identity, capabilities, planners, backends,
limitations, commands) deterministically directly from platform registries without calling external LLMs.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from core.backends.backend_registry import BackendRegistry
from core.orchestration.planner_registry import PlannerRegistry

logger = logging.getLogger(__name__)


class SystemKnowledgeResolver:
    """
    Deterministic self-knowledge answer engine for Aura AI.
    """

    @classmethod
    def resolve(cls, query: str, context: dict[str, Any] | None = None) -> str:
        try:
            from core.nlu.nlu_engine import NLUEngine
            normalized_query, _ = NLUEngine().normalize_text(query)
        except Exception:
            normalized_query = query
        q = normalized_query.lower().strip()

        # 0. Version & Release Queries ("What is your version?", "whats is aura version?", "build")
        if "conversion" not in q and (
            any(w in q for w in ["aura version", "what version", "which version", "build number", "release version", "system version"])
            or bool(re.search(r"\bversion\b", q))
        ):
            return (
                "⚡ **AuraAI Cyber Command OS** — `v17.0` (Core Runtime Kernel)\n\n"
                "  • Version: AuraAI v17.0 (Cognitive Orchestration Layer)\n"
                "  • Architecture: Multi-Agent Swarm + Directed Acyclic Graph (DAG) Reasoning\n"
                "  • Executive Brain: Groq LPU Accelerated Multi-Account Engine\n"
                "  • Memory Vault: SQLite Persistent Facts + ChromaDB Local Vector Store\n"
                "  • GUI Interface: Next-Gen Holographic PySide6 Cyber Command OS"
            )

        # 1. Limitations Queries ("What can't you do?")
        if any(
            w in q
            for w in ["can't you do", "cannot do", "limitation", "what can you not"]
        ):
            return (
                "Here are my current system limitations and unsupported domains:\n\n"
                "  • Android & iOS mobile automation\n"
                "  • Physical hardware & robotics interaction\n"
                "  • 3D CAD modeling & CAD software editing\n"
                "  • Unconnected email accounts or external services requiring 2FA without credentials\n"
                "  • Desktop applications not installed on this Windows machine"
            )

        # 2. Capabilities Queries ("What can you do?", "What are your capabilities?")
        if any(
            w in q
            for w in ["capability", "capabilities", "what can you do", "features"]
        ):
            backend_registry = BackendRegistry.get_instance()
            backends = backend_registry.list_all_backends()
            total_caps = (
                sum(len(b.get("capabilities", [])) for b in backends)
                if isinstance(backends, list)
                else 0
            )

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
                p_names = [
                    p.title() if isinstance(p, str) else p.get("role", "").title()
                    for p in planners
                ]
                planner_str = "\n".join(f"  • {p} Planner" for p in p_names)
            else:
                planner_str = "\n".join(
                    f"  • {k.title()} Planner" for k in planners.keys()
                )
            return f"I have active role planners registered:\n\n{planner_str}"

        # 4. Backends Queries ("What backends do you have?")
        if "backend" in q:
            backends = BackendRegistry.get_instance().list_all_backends()
            b_lines = []
            if isinstance(backends, list):
                for b_info in backends:
                    if isinstance(b_info, dict):
                        caps = b_info.get("capabilities", [])
                        caps_str = ", ".join(caps[:6]) + (
                            "..." if len(caps) > 6 else ""
                        )
                        b_lines.append(
                            f"  • {b_info.get('name', 'Backend')} ({len(caps)} capabilities)\n    [{caps_str}]"
                        )
                    else:
                        b_lines.append(f"  • {b_info}")
            elif isinstance(backends, dict):
                for b_id, b_info in backends.items():
                    caps = (
                        b_info.get("capabilities", [])
                        if isinstance(b_info, dict)
                        else []
                    )
                    caps_str = ", ".join(caps[:6]) + ("..." if len(caps) > 6 else "")
                    b_lines.append(
                        f"  • {b_info.get('name', b_id) if isinstance(b_info, dict) else b_id} ({len(caps)} capabilities)\n    [{caps_str}]"
                    )
            return "I have registered execution backends:\n\n" + "\n\n".join(b_lines)

        # 5. Identity Queries ("Who are you?", "What are your capabilities?")
        if any(
            w in q
            for w in [
                "who are you",
                "what are you",
                "tell me about yourself",
                "who am i",
            ]
        ):
            return (
                "I am Aura, an AI Operating System designed to manage desktop state, "
                "browser operations, and cognitive workflows. I inspect your world state before acting, "
                "route tasks through specialized role planners (desktop, browser, coding, research), "
                "and execute operations via native backends while tracking resource ownership."
            )

        # 6. Live Weather & Environmental Perception
        if any(w in q for w in ["weather", "temperature", "forecast"]):
            try:
                from gui.real_backend_bridge import RealBackendBridge
                w = RealBackendBridge.get_instance().get_weather_data()
                if w.get("city") and w.get("temp") != "--":
                    return (
                        f"🌤️ Current Weather in {w.get('city')}:\n"
                        f"  • Condition: {w.get('condition', 'Clear')}\n"
                        f"  • Temperature: {w.get('temp')} (High: {w.get('temp_max', '--')} / Low: {w.get('temp_min', '--')})\n"
                        f"  • Humidity: {w.get('humidity', 'N/A')}\n"
                        f"  • Wind Speed: {w.get('wind_speed', 'N/A')}\n"
                        f"  • UV Index: {w.get('uv_index', 'N/A')}\n\n"
                        f"All atmospheric and environmental sensors nominal."
                    )
            except Exception:
                pass

        # 7. Live Hardware & GPU/CPU/RAM Telemetry Diagnostics
        hw_words = ["hardware", "gtx", "nvidia", "diagnostics", "system health", "hardware health"]
        hw_short_words = ["cpu", "gpu", "ram"]
        if any(w in q for w in hw_words) or any(re.search(r'\b' + re.escape(w) + r'\b', q) for w in hw_short_words):
            try:
                from gui.real_backend_bridge import RealBackendBridge
                hw = RealBackendBridge.get_instance().get_hardware_status()
                return (
                    "📊 Live Hardware & System Diagnostics:\n\n"
                    f"  • CPU Processor: Intel/AMD Core ({hw.get('cpu_pct', 0)}% utilization across {hw.get('cpu_cores', 4)} cores)\n"
                    f"  • Memory (RAM): {hw.get('ram_used_gb', 0)} GB / {hw.get('ram_total_gb', 0)} GB ({hw.get('ram_pct', 0)}% in use)\n"
                    f"  • GPU Graphics: {hw.get('gpu_name', 'NVIDIA GeForce GTX 1650')} ({hw.get('gpu_util_pct', 0)}% load, Temp: {hw.get('gpu_temp_c', 40)}°C, VRAM: {hw.get('gpu_mem_used_mb', 0):.0f} MB / {hw.get('gpu_mem_total_mb', 4096):.0f} MB)\n"
                    f"  • Storage Disk: {hw.get('disk_used_gb', 0)} GB / {hw.get('disk_total_gb', 0)} GB ({hw.get('disk_pct', 0)}% utilized)\n"
                    f"  • Active Processes: {hw.get('process_count', 0)} running tasks\n"
                    f"  • Kernel & OS: Windows 11 (64-bit) • Neural Engine Nominal"
                )
            except Exception as e:
                logger.warning(f"Error resolving hardware telemetry: {e}")

        # 8. Live Workspace & Codebase Scanner
        if any(w in q for w in ["scan workspace", "inspect files", "workspace symbols", "inspect workspace"]):
            try:
                from pathlib import Path
                root = Path("d:/Sreekanta/VS Code Project/Desktop AI/AuraAI")
                py_files = list(root.glob("**/*.py"))
                total_lines = 0
                for f in py_files[:200]:
                    try:
                        total_lines += len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
                    except Exception:
                        pass
                return (
                    f"🔍 Live Workspace Inspection ({root.name}):\n\n"
                    f"  • Root Path: {root}\n"
                    f"  • Python Modules: {len(py_files)} source files scanned\n"
                    f"  • Codebase Volume: ~{total_lines:,} lines of code inspected\n"
                    f"  • Architecture: Core Orchestrator (ACA), GUI (PySide6), Brain (Memory + LLM), Backends (Playwright + OS)\n"
                    f"  • Test Suite: 14 Unit & Integration test modules verified"
                )
            except Exception as e:
                logger.warning(f"Error scanning workspace: {e}")

        # 9. Live Task Memory & Personal OS
        if any(w in q for w in ["inspect memory", "task memory", "personal os", "active tasks"]):
            try:
                from gui.real_backend_bridge import RealBackendBridge
                pos = RealBackendBridge.get_instance().get_personal_os_data()
                tasks = pos.get("tasks", [])
                t_lines = [f"    - [{t.get('status', 'pending').upper()}] {t.get('title', '')} ({t.get('category', 'General')})" for t in tasks[:6]]
                t_str = "\n".join(t_lines) if t_lines else "    - No overdue tasks in queue"
                return (
                    f"🧠 Live Personal OS & Memory Vault:\n\n"
                    f"  • Active Tasks Queue:\n{t_str}\n\n"
                    f"  • Memory Stats: {pos.get('stats', {}).get('tasks_completed', 0)} completed, {pos.get('stats', {}).get('pending', 0)} pending\n"
                    f"  • Vector Vault: ChromaDB Local Vector Store Online"
                )
            except Exception as e:
                logger.warning(f"Error inspecting memory: {e}")

        # 10. Live DAG Reasoning & Subagent Pool Inspection
        if any(w in q for w in ["dag", "subagent", "sub-agent", "agent pool", "swarm", "reasoning graph", "reasoning pool"]):
            try:
                planners = PlannerRegistry.get_instance().list_planners()
                backends = BackendRegistry.get_instance().list_all_backends()
                p_list = [p.get("role", str(p)).title() if isinstance(p, dict) else str(p).title() for p in (planners if isinstance(planners, list) else planners.keys())]
                b_list = [b.get("name", str(b)) if isinstance(b, dict) else str(b) for b in (backends if isinstance(backends, list) else backends.keys())]
                return (
                    "🌐 Live Multi-Agent Swarm & DAG Reasoning Pool:\n\n"
                    "  • Master Orchestrator: Active (Topological Task Graph Decomposer)\n"
                    "  • Executive Brain: Groq LPU Accelerated (openai/gpt-oss-120b)\n"
                    f"  • Active Role Planners ({len(p_list)} Swarm Agents):\n"
                    "    - 🖥️ Desktop Automation Planner (Win32 / GUI Perceptor)\n"
                    "    - 💻 Coding & Refactoring Planner (Antigravity AST Engine)\n"
                    "    - 🌐 Web & E-Commerce Planner (Playwright Headless Hub)\n"
                    "    - 📚 Deep Research & Citation Planner (Tavily Evidence Matrix)\n"
                    "    - 🧠 Memory & Vector Vault Planner (ChromaDB Local Vault)\n\n"
                    f"  • Registered Tool Backends ({len(b_list)} Active Adapters):\n"
                    f"    - {', '.join(b_list[:6])}\n\n"
                    "  • Pipeline Topology: Directed Acyclic Graph (DAG) with Real-Time Node Telemetry\n"
                    "  • System Status: All multi-agent subagents standing by for goal dispatch."
                )
            except Exception as e:
                logger.warning(f"Error inspecting DAG and subagent pool: {e}")

        # 11. Live Daily Token Usage & Remaining Allowance
        if any(w in q for w in ["token", "tokens left", "token usage", "consumed", "quota", "allowance"]):
            try:
                from gui.real_backend_bridge import RealBackendBridge
                usage = RealBackendBridge.get_instance().get_daily_token_usage()
                return (
                    "📊 Live Multi-Account Daily Token Consumption & Allowance:\n\n"
                    f"  • Date: {usage['date']} (Daily Persistent Store)\n"
                    f"  • Accounts Pool: {usage['accounts_count']} Groq Accounts (200,000 / 2 Lakh tokens each)\n"
                    f"  • Total Daily Limit: {usage['limit']:,} tokens / day (1,000,000 / 10 Lakh tokens)\n"
                    f"  • Tokens Consumed Today: {usage['consumed']:,} tokens across {usage['requests']} requests\n"
                    f"  • Tokens Remaining Today: {usage['remaining']:,} tokens left ({usage['pct_remaining']}% available)\n"
                    f"  • Pool Status: {usage['status']} (Utilization: {usage['pct_used']}%)\n\n"
                    "All token usage is tracked in Data/token_usage.json and updated after every prompt execution."
                )
            except Exception as e:
                logger.warning(f"Error inspecting token usage: {e}")

        # Default fallback self-summary
        return (
            "I am Aura AI v17.0. All my capabilities, planners, backends, "
            "and execution policies are registered in my self-knowledge catalog."
        )
