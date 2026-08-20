"""
Task Decomposer
Location: src/core/orchestration/task_decomposer.py

Decomposes goals into a Directed Acyclic Graph (DAG) of subtasks with capability tags.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PlannerRole(str, Enum):
    """Role-based domain planner identifiers."""

    DESKTOP = "desktop"
    RESEARCH = "research"
    CODING = "coding"
    BROWSER = "browser"
    MEMORY = "memory"


@dataclass
class SubTask:
    """Represents a single node in a Task Graph."""

    task_id: str
    title: str
    required_role: PlannerRole
    capability: str
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None


@dataclass
class TaskGraph:
    """Directed Acyclic Graph (DAG) of subtasks representing a user goal."""

    goal: str
    subtasks: dict[str, SubTask] = field(default_factory=dict)
    execution_order: list[list[str]] = field(default_factory=list)

    def add_task(self, subtask: SubTask) -> None:
        self.subtasks[subtask.task_id] = subtask


class TaskDecomposer:
    """
    Decomposes user goals into structured subtasks with capability mappings.
    """

    def decompose(self, goal: str, decision: Any | None = None) -> TaskGraph:
        graph = TaskGraph(goal=goal)
        goal_trimmed = goal.strip()

        # Direct Capability Dispatch: check if goal is an exact registered capability name
        from core.capabilities.capability_registry import CapabilityRegistry
        cap_candidate = goal_trimmed
        if cap_candidate.lower().startswith("execute capability "):
            cap_candidate = cap_candidate[19:].strip()
        elif cap_candidate.lower().startswith("execute "):
            cap_candidate = cap_candidate[8:].strip()

        cap_obj = CapabilityRegistry.get_instance().get(cap_candidate) or CapabilityRegistry.get_instance().get(goal_trimmed)
        if cap_obj is not None:
            role_map = {
                "desktop": PlannerRole.DESKTOP,
                "coding": PlannerRole.CODING,
                "browser": PlannerRole.BROWSER,
                "research": PlannerRole.RESEARCH,
                "memory": PlannerRole.DESKTOP,
                "multimodal": PlannerRole.DESKTOP,
                "vision": PlannerRole.DESKTOP,
                "voice": PlannerRole.DESKTOP,
            }
            subtask = SubTask(
                task_id="task_1",
                title=f"Execute {cap_obj.name}",
                required_role=role_map.get(cap_obj.domain, PlannerRole.DESKTOP),
                capability=cap_obj.name,
                description=f"Execute capability '{cap_obj.name}'",
                parameters={"goal": goal},
                dependencies=[],
            )
            graph.add_task(subtask)
            self._compute_execution_levels(graph)
            logger.info(
                f"Direct capability dispatch: '{cap_obj.name}' mapped to role '{subtask.required_role.value}'"
            )
            return graph

        goal_lower = goal.lower()

        subtask_specs = self._analyze_goal_clauses(goal_lower, goal, decision)
        for spec in subtask_specs:
            graph.add_task(spec)

        self._compute_execution_levels(graph)
        logger.info(
            f"Decomposed goal into {len(graph.subtasks)} subtasks across {len(graph.execution_order)} levels."
        )
        return graph

    def _analyze_goal_clauses(
        self, goal_lower: str, raw_goal: str, decision: Any | None = None
    ) -> list[SubTask]:
        is_browser_flow = (
            any(u in goal_lower for u in ["https://", "http://", "www."])
            or (
                "navigate" in goal_lower
                and any(k in goal_lower for k in ["click", "type", "extract", "fill", "submit", "button", "scrape"])
            )
        )
        # Check if this is a multi-stage research + persistence + launch task or browser flow, which shouldn't be split
        is_multi_stage = is_browser_flow or (
            any(
                w in goal_lower
                for w in ["research", "search web", "look up", "find papers"]
            )
            and any(w in goal_lower for w in ["save", "create", "write", "summary"])
            and any(
                w in goal_lower
                for w in ["open", "launch", "in vs code", "in notepad", "in code"]
            )
        )
        # Check for implicit "type/write <text> in/into <app>" pattern without explicit "and"
        # Example: "type test successful in notepad" -> [app_open(notepad), keyboard.type(test successful)]
        if not is_multi_stage:
            import re

            m_implicit = re.search(
                r"^(?:please\s+)?(type|write|enter|input)\s+(.+?)\s+(?:in|into|on)\s+([a-zA-Z0-9_\-\.\s]+)$",
                raw_goal.strip(),
                re.IGNORECASE,
            )
            if m_implicit:
                text_to_type = m_implicit.group(2).strip("'\" ")
                app_target = m_implicit.group(3).strip()

                app_target_lower = app_target.lower()
                non_app_terms = [
                    "python",
                    "javascript",
                    "c++",
                    "java",
                    "html",
                    "css",
                    "markdown",
                    "txt",
                    "english",
                    "spanish",
                    "french",
                    "capital",
                    "lowercase",
                    "uppercase",
                    "bold",
                    "italics",
                ]
                is_false_positive = any(
                    term == app_target_lower for term in non_app_terms
                ) or any(
                    f in text_to_type.lower()
                    for f in ["file", "script", "code", "document", "markdown"]
                )

                if not is_false_positive and app_target_lower:
                    for drop in ["app", "application", "window"]:
                        app_target_lower = re.sub(
                            rf"\b{drop}\b", "", app_target_lower
                        ).strip()
                    app_name_final = app_target_lower or app_target

                    t1 = SubTask(
                        task_id="task_1",
                        title=f"Launch application: {app_name_final.title()}",
                        required_role=PlannerRole.DESKTOP,
                        capability="app_open",
                        description=f"Open {app_name_final} for typing",
                        parameters={
                            "app_name": app_name_final,
                            "goal": f"open {app_name_final}",
                        },
                        dependencies=[],
                    )
                    t2 = SubTask(
                        task_id="task_2",
                        title=f"Type text: '{text_to_type}'",
                        required_role=PlannerRole.DESKTOP,
                        capability="keyboard.type",
                        description=f"Type '{text_to_type}' into {app_name_final}",
                        parameters={
                            "app_name": app_name_final,
                            "goal": f"type {text_to_type}",
                            "text": text_to_type,
                        },
                        dependencies=["task_1"],
                    )
                    return [t1, t2]

        # Check if the goal contains multiple sequential clauses separated by "and" or ";"
        # Example: "open notepad and type hello world"
        if not is_multi_stage and (" and " in goal_lower or "; " in goal_lower):
            import re

            parts = re.split(r"\band\b|;", raw_goal, flags=re.IGNORECASE)
            valid_clauses = []
            for p in parts:
                p_clean = p.strip()
                if any(
                    v in p_clean.lower()
                    for v in [
                        "open",
                        "launch",
                        "start",
                        "run",
                        "close",
                        "minimize",
                        "maximize",
                        "restore",
                        "unminimize",
                        "type",
                        "write",
                        "search",
                        "navigate",
                        "focus",
                        "activate",
                        "bring",
                        "press",
                        "hit",
                        "enter",
                        "return",
                        "click",
                        "key",
                        "hotkey",
                        "play",
                        "create",
                        "make",
                        "build",
                        "refactor",
                        "generate",
                        "implement",
                    ]
                ):
                    valid_clauses.append(p_clean)

            if len(valid_clauses) > 1:
                merged_clauses = []
                i = 0
                while i < len(valid_clauses):
                    c = valid_clauses[i]
                    if i + 1 < len(valid_clauses):
                        next_c = valid_clauses[i + 1]
                        if any(
                            s in c.lower()
                            for s in ["search", "navigate", "open", "go to"]
                        ) and any(
                            k in next_c.lower()
                            for k in ["play", "find", "for", "video", "song"]
                        ):
                            if not any(
                                a in c.lower()
                                for a in ["notepad", "calc", "cmd", "vscode"]
                            ):
                                c = f"{c} and {next_c}"
                                i += 1
                    merged_clauses.append(c)
                    i += 1
                valid_clauses = merged_clauses

                decomposed_tasks = []
                prev_task_id = None
                task_counter = 1
                last_app_name = None
                for idx, clause in enumerate(valid_clauses):
                    clause_lower = clause.lower()
                    clause_tasks = self._analyze_goal_clauses_single(
                        clause_lower, clause, None
                    )
                    for t in clause_tasks:
                        t.task_id = f"task_{task_counter}"
                        task_counter += 1
                        if prev_task_id:
                            t.dependencies = [prev_task_id]
                        if t.parameters.get("app_name") and t.parameters.get("app_name") not in (
                            "application",
                            "keyboard",
                            "desktop",
                        ):
                            last_app_name = t.parameters.get("app_name")
                        elif last_app_name and t.capability.startswith("uia.") and not t.parameters.get("window_title"):
                            t.parameters["window_title"] = last_app_name
                        prev_task_id = t.task_id
                        decomposed_tasks.append(t)
                return decomposed_tasks

        return self._analyze_goal_clauses_single(goal_lower, raw_goal, decision)


    def _resolve_youtube_watch_url(self, query: str) -> str | None:
        """Fetch top YouTube video watch URL for a search query to autoplay the video."""
        import re
        import urllib.parse
        import urllib.request

        try:
            q_enc = urllib.parse.quote_plus(query)
            search_url = f"https://www.youtube.com/results?search_query={q_enc}"
            req = urllib.request.Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                video_ids = re.findall(r"/watch\?v=([a-zA-Z0-9_-]{11})", html)
                if video_ids:
                    return f"https://www.youtube.com/watch?v={video_ids[0]}"
        except Exception:
            pass
        return None

    def _resolve_browser_target(self, raw_goal: str) -> tuple[str, str, str]:
        """
        Resolves (site_name, target_url, query) for a given browser goal string.
        """
        import re

        from browser.planner.site_registry import SiteRegistry

        goal_lower = raw_goal.lower()

        # Check for explicit HTTP/HTTPS URL
        url_match = re.search(r"https?://[^\s]+", raw_goal)
        if url_match:
            url = url_match.group(0)
            return ("custom", url, "")

        detected_site = None
        for site_name in SiteRegistry.list_sites():
            if site_name in goal_lower:
                detected_site = site_name
                break

        if not detected_site and any(
            w in goal_lower
            for w in ["video", "videos", "song", "songs", "music", "playlist", "yt"]
        ):
            detected_site = "youtube"

        if detected_site:
            profile = SiteRegistry.get_site(detected_site)
            base_url = (
                profile.base_url if profile else f"https://www.{detected_site}.com"
            )

            clean_g = raw_goal
            for prefix in [
                "search for",
                "search",
                "look up",
                "find",
                "open",
                "navigate to",
                "type",
            ]:
                if clean_g.lower().startswith(prefix):
                    clean_g = clean_g[len(prefix) :].strip()

            ignore_words = {
                detected_site,
                "open",
                "chrome",
                "edge",
                "firefox",
                "browser",
                "search",
                "look",
                "up",
                "find",
                "go",
                "to",
                "navigate",
                "type",
                "press",
                "enter",
                "and",
                "a",
                "the",
                "on",
                "in",
                "for",
                "at",
                "site",
                "app",
                "application",
                "play",
            }
            query_words = [w for w in clean_g.split() if w.lower() not in ignore_words]
            query = " ".join(query_words).strip()

            if query and profile and profile.search_url_template:
                search_url = profile.search_url_template.format(
                    query=query.replace(" ", "+")
                )
                if detected_site == "youtube" and any(
                    w in goal_lower
                    for w in [
                        "play",
                        "song",
                        "songs",
                        "video",
                        "videos",
                        "music",
                        "listen",
                    ]
                ):
                    watch_url = self._resolve_youtube_watch_url(query)
                    if watch_url:
                        search_url = watch_url
                return (detected_site, search_url, query)
            else:
                return (detected_site, base_url, query)

        clean_g = raw_goal
        for prefix in [
            "search for",
            "search",
            "look up",
            "find",
            "open",
            "navigate to",
        ]:
            if clean_g.lower().startswith(prefix):
                clean_g = clean_g[len(prefix) :].strip()
        query = clean_g.strip()
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return ("google", search_url, query)

    def _detect_action_and_capability(
        self, goal_lower: str, raw_goal: str
    ) -> tuple[str, str, dict[str, Any]]:
        """
        Classifies natural language into canonical capabilities and extracts parameters & context.
        """
        try:
            from src.browser.context_store import ContextStore
        except (ModuleNotFoundError, ImportError):
            from browser.context_store import ContextStore

        store = ContextStore.get_instance()

        # 1. Media Control capabilities
        if any(
            k in goal_lower
            for k in [
                "next video",
                "play the next",
                "play next",
                "skip this one",
                "next one",
                "play another",
                "go to the next",
            ]
        ):
            store.update_media_state("media.next", raw_goal)
            return (
                "media.next",
                "Play Next Video",
                {"action": "next", "media_context": store.media.to_dict()},
            )

        if any(
            k in goal_lower
            for k in [
                "previous video",
                "play previous",
                "previous one",
                "last video",
                "one before this",
                "go back to last",
                "play the one before",
                "go back",
            ]
        ):
            store.update_media_state("media.previous", raw_goal)
            return (
                "media.previous",
                "Play Previous Video",
                {"action": "previous", "media_context": store.media.to_dict()},
            )

        if goal_lower.strip() in ["next", "next."]:
            store.update_media_state("media.next", raw_goal)
            return (
                "media.next",
                "Play Next Video",
                {"action": "next", "media_context": store.media.to_dict()},
            )

        if goal_lower.strip() in ["previous", "previous."]:
            store.update_media_state("media.previous", raw_goal)
            return (
                "media.previous",
                "Play Previous Video",
                {"action": "previous", "media_context": store.media.to_dict()},
            )

        if any(
            k in goal_lower
            for k in ["pause", "pause the video", "stop it for now", "pause playback"]
        ) or goal_lower.strip() in ["pause", "pause."]:
            store.update_media_state("media.pause", raw_goal)
            return (
                "media.pause",
                "Pause Media Playback",
                {"action": "pause", "media_context": store.media.to_dict()},
            )

        if any(
            k in goal_lower
            for k in [
                "resume",
                "continue video",
                "play again",
                "continue playback",
                "start it",
            ]
        ) or goal_lower.strip() in ["resume", "continue"]:
            store.update_media_state("media.resume", raw_goal)
            return (
                "media.resume",
                "Resume Media Playback",
                {"action": "resume", "media_context": store.media.to_dict()},
            )

        if any(
            k in goal_lower
            for k in ["skip ", "seek ", "go forward ", "go back ", "rewind "]
        ) and any(
            w in goal_lower
            for w in ["seconds", "secs", "second", "sec", "s", "minutes", "mins"]
        ):
            store.update_media_state("media.seek", raw_goal)
            return (
                "media.seek",
                "Seek Media Timestamp",
                {
                    "action": "seek",
                    "goal": raw_goal,
                    "media_context": store.media.to_dict(),
                },
            )

        # 2. Comments & Reviews
        if any(
            k in goal_lower
            for k in [
                "check the comments",
                "read comments",
                "check comments",
                "what are people saying",
                "summarize comments",
            ]
        ):
            rel = store.resolve_relative_reference(raw_goal)
            return (
                "browser.comments",
                "Inspect & Read Comments",
                {"action": "comments", "target": rel.get("media"), "goal": raw_goal},
            )

        if any(
            k in goal_lower
            for k in [
                "check the reviews",
                "read reviews",
                "check reviews",
                "customer reviews",
                "what are people complaining about",
                "worth buying",
            ]
        ):
            rel = store.resolve_relative_reference(raw_goal)
            return (
                "shopping.reviews",
                "Inspect Customer Reviews",
                {
                    "action": "reviews",
                    "target": rel.get("product"),
                    "shopping_context": store.shopping.to_dict(),
                },
            )

        # 3. Shopping & E-Commerce
        if any(
            k in goal_lower
            for k in [
                "add to cart",
                "add it to cart",
                "put in cart",
                "add the cheapest",
            ]
        ):
            rel = store.resolve_relative_reference(raw_goal)
            prod = rel.get("product")
            return (
                "shopping.cart.add",
                "Add Product to Cart",
                {
                    "action": "add_to_cart",
                    "product": prod,
                    "shopping_context": store.shopping.to_dict(),
                },
            )

        if any(
            k in goal_lower
            for k in [
                "proceed to checkout",
                "go to checkout",
                "open checkout",
                "checkout",
            ]
        ):
            return (
                "shopping.checkout",
                "Proceed to Checkout",
                {"action": "checkout", "shopping_context": store.shopping.to_dict()},
            )

        if any(
            k in goal_lower for k in ["compare", "which one is better", "side by side"]
        ):
            return (
                "shopping.compare",
                "Compare Products Side-by-Side",
                {"action": "compare", "shopping_context": store.shopping.to_dict()},
            )

        if any(
            k in goal_lower
            for k in ["laptop", "phone", "headphones", "monitor", "shoes"]
        ) and any(w in goal_lower for w in ["find", "search", "looking for", "buy"]):
            c = store.update_shopping_constraints(raw_goal)
            return (
                "shopping.search",
                "Search Products",
                {
                    "action": "search",
                    "query": raw_goal,
                    "constraints": c.to_dict(),
                    "shopping_context": store.shopping.to_dict(),
                },
            )

        import re

        if any(
            k in goal_lower
            for k in [
                "only ",
                "filter ",
                "no ",
                "don't show",
                "remove ",
                "sort by",
                "under ",
                "below ",
                "cheapest",
            ]
        ) or re.search(r"\b(16gb|ram|ssd|oled)\b", goal_lower):
            if (
                store.shopping.products
                or store.shopping.constraints.category
                or any(w in goal_lower for w in ["laptop", "phone", "monitor"])
            ):
                c = store.update_shopping_constraints(raw_goal)
                return (
                    "shopping.filter",
                    "Filter & Sort Products",
                    {
                        "action": "filter",
                        "constraints": c.to_dict(),
                        "shopping_context": store.shopping.to_dict(),
                    },
                )

        return ("", "", {})

    def _analyze_goal_clauses_single(
        self, goal_lower: str, raw_goal: str, decision: Any | None = None
    ) -> list[SubTask]:
        subtasks: list[SubTask] = []
        task_counter = 1

        # Check for specific normalized actions first (media, shopping, comments, reviews)
        spec_cap, spec_title, spec_params = self._detect_action_and_capability(
            goal_lower, raw_goal
        )
        if spec_cap:
            return [
                SubTask(
                    task_id="task_1",
                    title=spec_title,
                    required_role=PlannerRole.BROWSER,
                    capability=spec_cap,
                    description=f"{spec_title} ({raw_goal})",
                    parameters=spec_params,
                    dependencies=[],
                )
            ]

        intent_val = (
            getattr(decision, "intent_type", None).value
            if hasattr(getattr(decision, "intent_type", None), "value")
            else str(getattr(decision, "intent_type", ""))
        )

        if intent_val == "system_query":
            return [
                SubTask(
                    task_id="task_1",
                    title="Process System Query & Self Awareness",
                    required_role=PlannerRole.DESKTOP,
                    capability="system_info",
                    description=f"Provide system identity and capability response for: {raw_goal}",
                    dependencies=[],
                )
            ]

        if intent_val == "chat":
            return [
                SubTask(
                    task_id="task_1",
                    title="Process Conversational Chat",
                    required_role=PlannerRole.DESKTOP,
                    capability="chat",
                    description=f"Respond to chat message: {raw_goal}",
                    dependencies=[],
                )
            ]

        if intent_val in ["memory", "memory_write", "memory_recall"]:
            cap = (
                getattr(decision, "capability", "memory_write")
                if decision
                else "memory_write"
            )
            # Fallback if capability not set cleanly
            if cap == "memory" or not cap:
                cap = (
                    "memory_read"
                    if any(
                        w in goal_lower
                        for w in ["recall", "what is", "retrieve", "tell me", "do you"]
                    )
                    else "memory_write"
                )
            title = (
                "Recall Facts from Memory"
                if cap == "memory_read"
                else "Remember Facts in Memory"
            )
            return [
                SubTask(
                    task_id="task_1",
                    title=title,
                    required_role=PlannerRole.MEMORY,
                    capability=cap,
                    description=raw_goal,
                    dependencies=[],
                )
            ]

        resolved_intents = {"coding", "browser", "desktop_action", "system_query", "chat", "research", "memory", "vision", "voice", "multimodal", "daemon", "scheduler"}
        intent_is_authoritative = intent_val in resolved_intents

        has_daemon = (intent_val == "daemon") or any(
            w in goal_lower
            for w in [
                "daemon.spawn",
                "daemon.status",
                "daemon.list",
                "daemon.cancel",
                "daemon.pause",
                "daemon.resume",
                "background task",
                "run in background",
                "spawn background",
                "daemon task",
            ]
        )
        has_scheduler = (intent_val == "scheduler") or any(
            w in goal_lower
            for w in [
                "scheduler.at",
                "scheduler.cron",
                "scheduler.interval",
                "scheduler.cancel",
                "schedule task",
                "every 5 minutes",
                "cron job",
                "set a timer",
                "remind me in",
            ]
        )

        has_vision = (intent_val in ("vision", "multimodal")) or any(
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
                "vision.capture",
                "vision.describe",
                "vision.ocr",
                "vision.ground_element",
            ]
        )
        has_voice = (intent_val in ("voice", "multimodal")) or any(
            w in goal_lower
            for w in [
                "voice.listen",
                "voice.transcribe",
                "voice.speak",
                "voice.process_turn",
                "speak out",
                "speak text",
                "say out loud",
                "voice command",
                "transcribe voice",
                "transcribe speech",
                "listen to speech",
                "voice turn",
            ]
        )

        has_research = (intent_val == "research") or (
            not intent_is_authoritative and any(
                w in goal_lower
                for w in ["research", "search web", "look up", "find papers"]
            )
        )
        has_coding = (intent_val == "coding") or (
            not intent_is_authoritative and any(
                w in goal_lower
                for w in [
                    "refactor",
                    "antigravity",
                    "fix bug",
                    "write code",
                    "modify code",
                    "implement feature",
                    "unit test",
                    "git commit",
                    "create",
                    "make",
                    "build",
                    "python",
                ]
            )
        )
        has_browser = (intent_val == "browser") or any(
            w in goal_lower
            for w in [
                "browse",
                "web page",
                "navigate",
                "url",
                "https://",
                "http://",
                "www.",
                "instagram",
                "github",
                "linkedin",
                "youtube",
            ]
        )

        if has_browser:
            desktop_keywords = [
                "vs code",
                "vscode",
                "workspace",
                "notepad",
                "clipboard",
                "mute",
                "volume",
                "calculator",
                "calc",
                "task manager",
                "settings",
                "cmd",
                "powershell",
            ]
            has_desktop = any(w in goal_lower for w in desktop_keywords)
        else:
            import re

            desktop_patterns = [
                r"\bopen\b",
                r"\blaunch\b",
                r"\bclose\b",
                r"\bminimize\b",
                r"\bmaximize\b",
                r"\brestore\b",
                r"\bunminimize\b",
                r"\bapp\b",
                r"\bwindow\b",
                r"\btype\b",
                r"\bwrite\b",
                r"\bpress\b",
                r"\bhit\b",
                r"\benter\b",
                r"\bvs\s*code\b",
                r"\bvscode\b",
                r"\bworkspace\b",
                r"\bnotepad\b",
                r"\bcalc\b",
                r"\bcalculator\b",
                r"\bchrome\b",
                r"\bedge\b",
                r"\bfirefox\b",
                r"\bspotify\b",
                r"\bcmd\b",
                r"\bpowershell\b",
                r"\bclipboard\b",
                r"\bmute\b",
                r"\bvolume\b",
                r"\bbluetooth\b",
                r"\bwifi\b",
                r"\bwi-fi\b",
                r"\bbrightness\b",
                r"\bclick\b",
                r"\btoggle\b",
                r"\bcheckbox\b",
                r"\binspect\b",
                r"\btree\b",
                r"\bbutton\b",
            ]
            has_desktop = (intent_val == "desktop_action") or (
                not intent_is_authoritative and any(
                    re.search(pat, goal_lower) for pat in desktop_patterns
                )
            )

        if has_coding and has_desktop and not intent_is_authoritative:
            # Prevent nouns like 'app' or 'calculator' from spuriously triggering desktop actions
            # in coding clauses, unless there is a clear desktop action verb.
            desktop_verbs = ["open", "launch", "close", "minimize", "maximize", "restore", "type", "press", "hit"]
            if not any(v in goal_lower for v in desktop_verbs):
                has_desktop = False

        if has_coding and has_research and not intent_is_authoritative:
            # Prevent nouns like 'python' or 'code' from spuriously triggering coding actions
            # in research clauses, unless there is a clear coding action verb.
            coding_verbs = ["write code", "fix", "refactor", "implement", "build", "debug", "create script", "write script"]
            if not any(v in goal_lower for v in coding_verbs):
                has_coding = False

        if has_vision and not intent_is_authoritative:
            # Prevent 'screen' or 'screenshot' from spuriously triggering app_open
            desktop_verbs = ["open", "launch", "close", "minimize", "maximize", "restore", "type", "press", "hit"]
            if not any(v in goal_lower for v in desktop_verbs):
                has_desktop = False

        if has_voice and not intent_is_authoritative:
            # Prevent voice commands from spuriously triggering app_open
            desktop_verbs = ["open", "launch", "close", "minimize", "maximize", "restore", "type", "press", "hit"]
            if not any(v in goal_lower for v in desktop_verbs):
                has_desktop = False

        # Check for multi-stage research -> document -> persist -> open DAG
        if (
            has_research
            and any(w in goal_lower for w in ["save", "create", "write", "summary"])
            and any(
                w in goal_lower
                for w in ["open", "launch", "in vs code", "in notepad", "in code"]
            )
        ):
            import re

            m_file = re.search(
                r"['\"]([a-zA-Z]:[\\/][^'\"]+\.[a-zA-Z0-9]+|[^'\"]+\.[a-zA-Z0-9]+)['\"]",
                raw_goal,
            )
            target_file_name = (
                m_file.group(1) if m_file else "python_release_summary.md"
            )

            target_app = "code"
            if "notepad" in goal_lower:
                target_app = "notepad"
            elif (
                "vs code" in goal_lower
                or "vscode" in goal_lower
                or "code" in goal_lower
            ):
                target_app = "code"

            t1_id = f"task_{task_counter}"
            task_counter += 1
            t2_id = f"task_{task_counter}"
            task_counter += 1
            t3_id = f"task_{task_counter}"
            task_counter += 1
            t4_id = f"task_{task_counter}"
            task_counter += 1

            # Stage 1: Research — produces raw structured research data
            t1 = SubTask(
                task_id=t1_id,
                title="Conduct Research & Synthesize Knowledge",
                required_role=PlannerRole.RESEARCH,
                capability="research",
                description=f"Gather information for: {raw_goal}",
                output_artifacts=["art_research_data"],
            )
            # Stage 2: Document Generation — transforms research into markdown
            t2 = SubTask(
                task_id=t2_id,
                title="Generate Markdown Document from Research",
                required_role=PlannerRole.DESKTOP,
                capability="document.generate",
                description=f"Transform research data into formatted markdown document: {target_file_name}",
                input_artifacts=["art_research_data"],
                output_artifacts=["art_markdown_doc"],
                parameters={"format": "markdown", "target_filename": target_file_name},
                dependencies=[t1_id],
            )
            # Stage 3: File Persistence — writes markdown content to disk
            t3 = SubTask(
                task_id=t3_id,
                title=f"Persist Artifact: {target_file_name}",
                required_role=PlannerRole.DESKTOP,
                capability="file.create",
                description=f"Save markdown document as '{target_file_name}'",
                input_artifacts=["art_markdown_doc"],
                output_artifacts=["art_saved_file"],
                parameters={"file_path": target_file_name, "goal": raw_goal},
                dependencies=[t2_id],
            )
            # Stage 4: Open in Application — launches the saved file
            t4 = SubTask(
                task_id=t4_id,
                title=f"Open Artifact in {target_app.title()}: {target_file_name}",
                required_role=PlannerRole.DESKTOP,
                capability="app_open",
                description=f"Open artifact '{target_file_name}' using {target_app.title()}",
                input_artifacts=["art_saved_file"],
                parameters={
                    "app_name": target_app,
                    "file_path": target_file_name,
                    "target_file": target_file_name,
                    "goal": raw_goal,
                },
                dependencies=[t3_id],
            )
            return [t1, t2, t3, t4]

        prev_id: str | None = None

        if has_research:
            is_deep = any(
                k in goal_lower
                for k in [
                    "deep research",
                    "deeply research",
                    "in-depth research",
                    "investigate",
                ]
            )
            is_pure_search = any(
                k in goal_lower
                for k in [
                    "search web",
                    "search for",
                    "google for",
                    "look up",
                    "find articles",
                    "find sources",
                ]
            ) and not any(
                k in goal_lower
                for k in [
                    "synthesize",
                    "summarize",
                    "analyze",
                    "and summarize",
                    "and synthesize",
                    "and report",
                ]
            )

            if is_deep:
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Conduct Deep Autonomous Research",
                        required_role=PlannerRole.RESEARCH,
                        capability="research.deep_query",
                        description=f"Deep research: {raw_goal}",
                        parameters={"question": raw_goal},
                        dependencies=[prev_id] if prev_id else [],
                    )
                )
                prev_id = t_id
            elif is_pure_search:
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Search Web Knowledge Sources",
                        required_role=PlannerRole.RESEARCH,
                        capability="research.search",
                        description=f"Search web for: {raw_goal}",
                        output_artifacts=["art_search_results"],
                        parameters={"query": raw_goal},
                        dependencies=[prev_id] if prev_id else [],
                    )
                )
                prev_id = t_id
            else:
                # Multi-step Research DAG: search -> synthesize
                t1_id = f"task_{task_counter}"
                task_counter += 1
                t2_id = f"task_{task_counter}"
                task_counter += 1

                subtasks.append(
                    SubTask(
                        task_id=t1_id,
                        title="Query Research Evidence Sources",
                        required_role=PlannerRole.RESEARCH,
                        capability="research.search",
                        description=f"Search web for: {raw_goal}",
                        output_artifacts=["art_search_results"],
                        parameters={"query": raw_goal},
                        dependencies=[prev_id] if prev_id else [],
                    )
                )
                subtasks.append(
                    SubTask(
                        task_id=t2_id,
                        title="Synthesize Evidence & Citations",
                        required_role=PlannerRole.RESEARCH,
                        capability="research.synthesize",
                        description=f"Synthesize research findings for: {raw_goal}",
                        input_artifacts=["art_search_results"],
                        parameters={"topic": raw_goal},
                        dependencies=[t1_id],
                    )
                )
                prev_id = t2_id


        if has_desktop:
            t_id = f"task_{task_counter}"
            task_counter += 1

            # Infer specific capability and app target from goal
            cap = "app_open"
            app_target = "application"
            title_text = f"Execute desktop action: {raw_goal}"

            # 1. Check for UIA capability intents first
            from desktop.planner.goal_parser import GoalParser

            parsed_goal = GoalParser().parse(raw_goal)
            is_write_cmd = any(
                k in goal_lower
                for k in ["type ", "type", "write text", "enter text", "input text"]
            ) or (
                any(w in goal_lower for w in ["write ", "write"])
                and not any(
                    f in goal_lower
                    for f in [
                        "write file",
                        "write code",
                        "write script",
                        "write document",
                        "write summary",
                        "write a file",
                        "write markdown",
                    ]
                )
            )

            if (
                parsed_goal.explicit_capability
                and parsed_goal.explicit_capability.startswith("uia.")
            ):
                cap = parsed_goal.explicit_capability
                params = dict(parsed_goal.parameters)
                params["goal"] = raw_goal
                elem_name = (
                    params.get("name")
                    or params.get("window_title")
                    or "element"
                )
                title_text = f"UI Action ({cap}): {elem_name}"
                app_target = params.get("window_title") or "desktop"
                params["app_name"] = app_target
            elif is_write_cmd:
                cap = "keyboard.type"
                app_target = "keyboard"
                text_to_type = raw_goal
                for prefix in [
                    "type text ",
                    "type ",
                    "write text ",
                    "write ",
                    "enter text ",
                    "enter ",
                    "input ",
                ]:
                    if text_to_type.lower().startswith(prefix):
                        text_to_type = text_to_type[len(prefix) :]
                        break
                text_to_type = text_to_type.strip("'\" ")
                params = {
                    "app_name": "keyboard",
                    "goal": raw_goal,
                    "text": text_to_type,
                }
                title_text = f"Type text: '{text_to_type}'"
            elif any(
                k in goal_lower
                for k in [
                    "press enter",
                    "hit enter",
                    "press return",
                    "hit return",
                    "press tab",
                    "press esc",
                    "press escape",
                ]
            ) or (
                any(w in goal_lower for w in ["press", "hit"])
                and any(
                    k in goal_lower
                    for k in [
                        "enter",
                        "return",
                        "tab",
                        "esc",
                        "escape",
                        "space",
                        "backspace",
                    ]
                )
            ):
                cap = "keyboard.press"
                app_target = "keyboard"
                key_name = "enter"
                for k in [
                    "enter",
                    "return",
                    "tab",
                    "esc",
                    "escape",
                    "space",
                    "backspace",
                ]:
                    if k in goal_lower:
                        key_name = k
                        break
                params = {"app_name": "keyboard", "goal": raw_goal, "key": key_name}
                title_text = f"Press key: '{key_name.title()}'"
            elif any(
                k in goal_lower
                for k in [
                    "create file",
                    "write file",
                    "save file",
                    "make file",
                    "create a file",
                ]
            ):
                cap = "file.create"
                title_text = f"Create and write file: {raw_goal}"
            elif any(k in goal_lower for k in ["bluetooth", "bt radio"]) and any(
                k in goal_lower
                for k in ["on", "off", "enable", "disable", "turn", "toggle"]
            ):
                cap = "bluetooth_control"
                app_target = "bluetooth"
                enable = not any(k in goal_lower for k in ["off", "disable"])
                params = {"enable": enable, "goal": raw_goal}
                title_text = "Enable Bluetooth" if enable else "Disable Bluetooth"
            elif any(
                k in goal_lower for k in ["wifi", "wi-fi", "wireless", "internet"]
            ) and any(
                k in goal_lower
                for k in ["on", "off", "enable", "disable", "turn", "toggle"]
            ):
                cap = "wifi_control"
                app_target = "wifi"
                enable = not any(k in goal_lower for k in ["off", "disable"])
                params = {"enable": enable, "goal": raw_goal}
                title_text = "Enable Wi-Fi" if enable else "Disable Wi-Fi"
            elif any(k in goal_lower for k in ["mute", "unmute", "toggle mute"]):
                cap = "toggle_mute"
                app_target = "audio"
                is_mute = "unmute" not in goal_lower
                params = {"mute": is_mute, "goal": raw_goal}
                title_text = "Mute system audio" if is_mute else "Unmute system audio"
            elif any(
                k in goal_lower for k in ["volume", "sound level", "sound volume"]
            ):
                cap = "set_volume"
                app_target = "audio"
                import re

                # Verbal level shortcuts
                _verbal = {
                    "max": 100.0,
                    "maximum": 100.0,
                    "highest": 100.0,
                    "full": 100.0,
                    "min": 0.0,
                    "minimum": 0.0,
                    "lowest": 0.0,
                    "zero": 0.0,
                    "mute": 0.0,
                    "half": 50.0,
                    "medium": 50.0,
                    "mid": 50.0,
                    "low": 25.0,
                    "quiet": 25.0,
                    "high": 80.0,
                    "loud": 80.0,
                }
                level = None
                for word, val in _verbal.items():
                    if word in goal_lower:
                        level = val
                        break
                if level is None:
                    vol_match = re.search(r"\b(\d{1,3})\b", goal_lower)
                    level = float(vol_match.group(1)) if vol_match else 50.0
                params = {"level": level, "volume": level, "goal": raw_goal}
                title_text = f"Set system volume to {int(level)}%"
            else:
                import re

                m = re.search(
                    r"\b(open|launch|start|run|close|minimize|maximize|restore|unminimize|focus|activate|switch to)\s+([a-zA-Z0-9_\-\.\s]+)\b",
                    goal_lower,
                )
                if m:
                    action_verb = m.group(1).lower()
                    raw_target = m.group(2).strip()
                    for sep in [" and ", " then ", " to ", " search", " play", " for "]:
                        if sep in raw_target.lower():
                            raw_target = raw_target.lower().split(sep)[0].strip()
                    app_target = raw_target
                    for mod in [
                        "another",
                        "new",
                        "second",
                        "extra",
                        "a",
                        "the",
                        "instance of",
                        "instance",
                        "window",
                    ]:
                        app_target = re.sub(
                            rf"\b{mod}\b", "", app_target, flags=re.IGNORECASE
                        ).strip()
                    if not app_target:
                        app_target = raw_target

                    if action_verb in ["open", "launch", "start", "run"]:
                        cap = "app_open"
                        title_text = f"Launch application: {app_target.title()}"
                    elif action_verb in ["minimize"]:
                        cap = "window.minimize"
                        title_text = f"Minimize window for: {app_target.title()}"
                    elif action_verb in ["maximize"]:
                        cap = "window.maximize"
                        title_text = f"Maximize window for: {app_target.title()}"
                    elif action_verb in ["restore", "unminimize"]:
                        cap = "window.restore"
                        title_text = f"Restore window for: {app_target.title()}"
                    elif action_verb in ["close"]:
                        cap = "app_close"
                        title_text = f"Close application: {app_target.title()}"
                    elif action_verb in ["focus", "activate", "switch to"]:
                        cap = "window.activate"
                        title_text = f"Focus window for: {app_target.title()}"
                elif any(w in goal_lower for w in ["battery", "charging", "battery status", "power status"]):
                    cap = "power.battery"
                    app_target = "battery"
                    title_text = "Check battery status"
                elif any(w in goal_lower for w in ["power plan", "power scheme"]):
                    cap = "power.power_plan"
                    app_target = "power"
                    title_text = "Check power plan"
                elif any(w in goal_lower for w in ["volume", "audio", "mute", "unmute"]):
                    cap = "audio.volume"
                    app_target = "audio"
                    title_text = "Check audio volume"
                else:
                    # Fallback: if no verb matches but a known app name is present, treat as open
                    known_apps = [
                        "notepad",
                        "calc",
                        "calculator",
                        "chrome",
                        "cmd",
                        "powershell",
                        "spotify",
                        "code",
                        "vscode",
                        "vs code",
                        "visual studio code",
                    ]
                    matched_known = False
                    for app in known_apps:
                        if app in goal_lower:
                            app_target = app
                            cap = "app_open"
                            title_text = f"Launch application: {app_target.title()}"
                            matched_known = True
                            break
                    if not matched_known:
                        cap = "unknown_action"
                        app_target = raw_goal
                        title_text = f"Unknown desktop action: {raw_goal}"
                params = {"app_name": app_target, "goal": raw_goal}

            is_web_target = app_target.lower() in [
                "application",
                "instagram",
                "youtube",
                "github",
                "gmail",
                "google",
                "twitter",
                "reddit",
                "linkedin",
                "facebook",
                "amazon",
                "netflix",
            ]
            if not (has_browser and is_web_target):
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title=title_text,
                        required_role=PlannerRole.DESKTOP,
                        capability=cap,
                        description=f"{title_text} ({raw_goal})",
                        parameters=params,
                        dependencies=[],
                    )
                )

        if (
            has_browser
            and not has_research
        ):
            site_name, target_url, query = self._resolve_browser_target(raw_goal)

            # Multi-step goal-oriented browser decomposition
            t1_id = f"task_{task_counter}"
            task_counter += 1

            # Check if browser is already running from decision/world_state
            is_chrome_open = False
            if (
                decision
                and hasattr(decision, "world_state")
                and isinstance(getattr(decision, "world_state"), dict)
            ):
                procs = decision.world_state.get("running_processes", [])
                is_chrome_open = any("chrome" in p for p in procs)

            subtasks.append(
                SubTask(
                    task_id=t1_id,
                    title="Ensure Browser Instance Active",
                    required_role=PlannerRole.BROWSER,
                    capability="browser.open",
                    description="Launch or verify browser instance",
                    dependencies=[],
                    status="skipped" if is_chrome_open else "pending",
                )
            )

            t2_id = f"task_{task_counter}"
            task_counter += 1
            subtasks.append(
                SubTask(
                    task_id=t2_id,
                    title=f"Navigate to {site_name.title() if site_name != 'custom' else 'URL'}",
                    required_role=PlannerRole.BROWSER,
                    capability="browser.navigate",
                    description=f"Navigate to {target_url}",
                    parameters={
                        "url": target_url,
                        "target_url": target_url,
                        "site": site_name,
                        "goal": raw_goal,
                    },
                    dependencies=[t1_id],
                )
            )

            is_extract = any(
                k in goal_lower
                for k in ["extract", "scrape", "get text", "read page", "content"]
            )
            is_click = any(
                k in goal_lower
                for k in ["click", "press link", "follow link", "button"]
            ) and not ("play" in goal_lower)
            is_type = any(
                k in goal_lower for k in ["type ", "fill ", "enter "]
            )

            if is_extract:
                t3_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t3_id,
                        title="Extract Page Content",
                        required_role=PlannerRole.BROWSER,
                        capability="browser.extract",
                        description=f"Extract content from {target_url}",
                        output_artifacts=["art_browser_content"],
                        parameters={"url": target_url},
                        dependencies=[t2_id],
                    )
                )
            elif is_click:
                import re

                m_sel = re.search(r"['\"]([^'\"]+)['\"]", raw_goal)
                sel = m_sel.group(1) if m_sel else "button"
                t3_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t3_id,
                        title="Click DOM Element",
                        required_role=PlannerRole.BROWSER,
                        capability="browser.click",
                        description=f"Click element '{sel}' on {target_url}",
                        parameters={"selector": sel, "url": target_url},
                        dependencies=[t2_id],
                    )
                )
            elif is_type:
                import re

                quotes = re.findall(r"['\"]([^'\"]+)['\"]", raw_goal)
                text = quotes[0] if quotes else "test"
                sel = quotes[1] if len(quotes) > 1 else "input"
                t3_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t3_id,
                        title="Type Text Into DOM Element",
                        required_role=PlannerRole.BROWSER,
                        capability="browser.type",
                        description=f"Type '{text}' into '{sel}' on {target_url}",
                        parameters={"selector": sel, "text": text, "url": target_url},
                        dependencies=[t2_id],
                    )
                )
            else:
                t3_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t3_id,
                        title="Verify Authentication & Session",
                        required_role=PlannerRole.BROWSER,
                        capability="browser.check_auth",
                        description="Check login state and user session",
                        dependencies=[t2_id],
                    )
                )

                t4_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t4_id,
                        title="Fulfill Page Goal",
                        required_role=PlannerRole.BROWSER,
                        capability="browser.navigate_goal",
                        description=f"Fulfill page goal for: {raw_goal}",
                        parameters={
                            "url": target_url,
                            "target_url": target_url,
                            "site": site_name,
                            "query": query,
                            "goal": raw_goal,
                        },
                        dependencies=[t3_id],
                    )
                )

                if "play" in goal_lower:
                    t5_id = f"task_{task_counter}"
                    task_counter += 1
                    subtasks.append(
                        SubTask(
                            task_id=t5_id,
                            title="Play Video Media",
                            required_role=PlannerRole.BROWSER,
                            capability="media.play",
                            description=f"Play top video result for: {query or raw_goal}",
                            parameters={
                                "query": query,
                                "goal": raw_goal,
                                "site": site_name,
                            },
                            dependencies=[t4_id],
                        )
                    )

        if has_coding or (not subtasks and intent_val == "coding"):
            t_id = f"task_{task_counter}"
            task_counter += 1
            deps = [prev_id] if prev_id else []
            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title="Execute Code Operation",
                    required_role=PlannerRole.CODING,
                    capability="coding",
                    description=raw_goal,
                    dependencies=deps,
                )
            )

        # ── Multimodal (Vision & Voice) Subtask Generation ───────────────
        if has_vision and not subtasks:
            if "ocr" in goal_lower or "read" in goal_lower:
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Extract Text with OCR",
                        required_role=PlannerRole.DESKTOP,
                        capability="vision.ocr",
                        description=f"OCR screen perception for: {raw_goal}",
                        parameters={"target_text": raw_goal},
                        dependencies=[],
                    )
                )
            elif "ground" in goal_lower or "find element" in goal_lower:
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Ground UI Element Coordinates",
                        required_role=PlannerRole.DESKTOP,
                        capability="vision.ground_element",
                        description=f"Ground UI element coordinates for: {raw_goal}",
                        parameters={"description": raw_goal},
                        dependencies=[],
                    )
                )
            elif any(w in goal_lower for w in ["screenshot", "capture screen", "vision.capture"]):
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Capture Screen Frame",
                        required_role=PlannerRole.DESKTOP,
                        capability="vision.capture",
                        description=f"Capture screen frame: {raw_goal}",
                        parameters={"capture_type": "full_screen"},
                        dependencies=[],
                    )
                )
            else:
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Perceive Desktop Visuals",
                        required_role=PlannerRole.DESKTOP,
                        capability="vision.describe",
                        description=f"Analyze visual desktop context for: {raw_goal}",
                        parameters={"query": raw_goal},
                        dependencies=[],
                    )
                )

        if has_voice and not subtasks:
            if any(w in goal_lower for w in ["speak", "say out"]):
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Synthesize Spoken Response",
                        required_role=PlannerRole.DESKTOP,
                        capability="voice.speak",
                        description=f"Speak response: {raw_goal}",
                        parameters={"text": raw_goal},
                        dependencies=[],
                    )
                )
            elif any(w in goal_lower for w in ["listen", "record audio"]):
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Capture Microphone Audio",
                        required_role=PlannerRole.DESKTOP,
                        capability="voice.listen",
                        description=f"Capture audio input for: {raw_goal}",
                        parameters={"duration_seconds": 3.0},
                        dependencies=[],
                    )
                )
            elif any(w in goal_lower for w in ["transcribe", "stt"]):
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Transcribe Voice Speech",
                        required_role=PlannerRole.DESKTOP,
                        capability="voice.transcribe",
                        description=f"Transcribe speech input: {raw_goal}",
                        parameters={"audio_data": raw_goal},
                        dependencies=[],
                    )
                )
            else:
                t_id = f"task_{task_counter}"
                task_counter += 1
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Process Voice Interaction Turn",
                        required_role=PlannerRole.DESKTOP,
                        capability="voice.process_turn",
                        description=f"Process voice turn for: {raw_goal}",
                        parameters={"audio_input": raw_goal},
                        dependencies=[],
                    )
                )

        if has_daemon and not subtasks:
            t_id = f"task_{task_counter}"
            task_counter += 1
            if any(w in goal_lower for w in ["daemon.status", "status of job", "status of task", "job status", "check status", "task status"]):
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Query Daemon Job Status",
                        required_role=PlannerRole.DESKTOP,
                        capability="daemon.status",
                        description=f"Query daemon status for: {raw_goal}",
                        parameters={"goal": raw_goal},
                        dependencies=[],
                    )
                )
            elif "list" in goal_lower:
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="List Daemon Jobs",
                        required_role=PlannerRole.DESKTOP,
                        capability="daemon.list",
                        description=f"List daemon jobs for: {raw_goal}",
                        parameters={},
                        dependencies=[],
                    )
                )
            elif "cancel" in goal_lower:
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Cancel Daemon Job",
                        required_role=PlannerRole.DESKTOP,
                        capability="daemon.cancel",
                        description=f"Cancel daemon job for: {raw_goal}",
                        parameters={"goal": raw_goal},
                        dependencies=[],
                    )
                )
            else:
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Spawn Autonomous Background Task",
                        required_role=PlannerRole.DESKTOP,
                        capability="daemon.spawn",
                        description=f"Spawn background task for: {raw_goal}",
                        parameters={"goal": raw_goal, "name": raw_goal},
                        dependencies=[],
                    )
                )

        if has_scheduler and not subtasks:
            t_id = f"task_{task_counter}"
            task_counter += 1
            if "cron" in goal_lower:
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Schedule Recurring Cron Task",
                        required_role=PlannerRole.DESKTOP,
                        capability="scheduler.cron",
                        description=f"Schedule cron job for: {raw_goal}",
                        parameters={"action": raw_goal, "cron_expression": "* * * * *"},
                        dependencies=[],
                    )
                )
            elif "interval" in goal_lower or "every" in goal_lower:
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Schedule Recurring Interval Task",
                        required_role=PlannerRole.DESKTOP,
                        capability="scheduler.interval",
                        description=f"Schedule interval task for: {raw_goal}",
                        parameters={"action": raw_goal, "interval_seconds": 60.0},
                        dependencies=[],
                    )
                )
            else:
                subtasks.append(
                    SubTask(
                        task_id=t_id,
                        title="Schedule One-Time Timer Task",
                        required_role=PlannerRole.DESKTOP,
                        capability="scheduler.at",
                        description=f"Schedule timer task for: {raw_goal}",
                        parameters={"action": raw_goal, "delay_seconds": 60.0},
                        dependencies=[],
                    )
                )

        if not subtasks:
            # Fallback for unrecognized action goals — default to DESKTOP action
            t_id = f"task_{task_counter}"
            subtasks.append(
                SubTask(
                    task_id=t_id,
                    title=f"Execute desktop action: {raw_goal}",
                    required_role=PlannerRole.DESKTOP,
                    capability="app_open",
                    description=raw_goal,
                    dependencies=[],
                )
            )

        return subtasks

    def _compute_execution_levels(self, graph: TaskGraph) -> None:
        completed: set[str] = set()
        remaining = set(graph.subtasks.keys())
        levels: list[list[str]] = []

        while remaining:
            current_level = []
            for t_id in list(remaining):
                subtask = graph.subtasks[t_id]
                if all(dep in completed for dep in subtask.dependencies):
                    current_level.append(t_id)

            if not current_level:
                unresolved = {
                    t_id: [d for d in graph.subtasks[t_id].dependencies if d not in completed]
                    for t_id in remaining
                }
                raise ValueError(
                    f"Cyclic or unresolvable dependencies detected in TaskGraph for goal '{graph.goal}'. "
                    f"Stuck subtasks: {unresolved}"
                )

            levels.append(current_level)
            for t_id in current_level:
                completed.add(t_id)
                remaining.remove(t_id)

        graph.execution_order = levels
