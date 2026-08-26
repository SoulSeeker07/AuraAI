from __future__ import annotations

import os
import re

from brain.models import ConversationAttachment, Intent
from brain.research_decision import ResearchDecision, SearchMode
from Memory import Memory, MemoryFact


class IntentRouter:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.research_decision = ResearchDecision()

    def detect(
        self, user_input: str, attachments: list[ConversationAttachment] | None = None
    ) -> Intent:
        normalized = user_input.lower().strip(" ?!.`'\"~@#$%^&*()_+-=[]{}|;:,<>/\t\r\n")
        attachments = attachments or []

        import logging

        logger = logging.getLogger(__name__)

        if attachments and any(
            attachment.mime_type.startswith("image/") for attachment in attachments
        ):
            logger.info("[IntentRouter] Intent detected: vision")
            return Intent("vision")

        if self._asks_for_screen_vision(normalized):
            logger.info("[IntentRouter] Intent detected: vision")
            return Intent("vision", {"query": user_input, "normalized": normalized})

        if self._asks_about_realtime_capability(normalized):
            logger.info("[IntentRouter] Intent detected: capability_status")
            return Intent("capability_status")

        facts = self.memory.extract_facts(user_input)
        logger.info(f"[IntentRouter] Extracted facts: {facts}")
        if facts and self._is_memory_statement(user_input):
            logger.info(
                "[IntentRouter] Memory statement detected, returning remember_fact intent"
            )
            return Intent("remember_fact", {"facts": facts})

        if normalized in {
            "summarize me",
            "summarize my memory",
            "what do you remember",
        }:
            logger.info("[IntentRouter] Intent detected: memory_summary")
            return Intent("memory_summary")

        if self._asks_for_restart(normalized):
            logger.info("[IntentRouter] Intent detected: restart_aura")
            return Intent("restart_aura", {"raw": user_input})

        if self._asks_for_time_or_date(normalized):
            logger.info("[IntentRouter] Intent detected: local_time")
            return Intent("local_time")

        if self._asks_for_weather(normalized):
            logger.info("[IntentRouter] Intent detected: live_weather")
            return Intent("live_weather")

        if self._asks_for_rag_query(normalized):
            logger.info("[IntentRouter] Intent detected: rag_query")
            return Intent("rag_query", {"query": user_input, "normalized": normalized})

        if self._asks_for_profile_lookup(normalized):
            logger.info("[IntentRouter] Intent detected: profile_lookup")
            return Intent("profile_lookup")

        if self._asks_for_projects_lookup(normalized):
            logger.info("[IntentRouter] Intent detected: projects_lookup")
            return Intent("projects_lookup")

        if self._asks_for_skills_lookup(normalized):
            logger.info("[IntentRouter] Intent detected: skills_lookup")
            return Intent(
                "skills_lookup",
                {"wants_count": "how many" in normalized or "count" in normalized},
            )

        if self._asks_for_goals_lookup(normalized):
            logger.info("[IntentRouter] Intent detected: goals_lookup")
            return Intent("goals_lookup")

        if self._asks_for_preferences_lookup(normalized):
            logger.info("[IntentRouter] Intent detected: preferences_lookup")
            key = self._parse_specific_preference(normalized)
            return Intent("preferences_lookup", {"key": key, "raw": user_input, "normalized": normalized})

        if self._asks_for_doc_update(normalized):
            logger.info("[IntentRouter] Intent detected: project_doc_update")
            return Intent("project_doc_update", {"query": user_input, "normalized": normalized})

        if self._asks_for_engineering_task(normalized):
            logger.info("[IntentRouter] Intent detected: autonomous_engineering")
            return Intent("autonomous_engineering", {"goal": user_input, "normalized": normalized})

        if self._asks_for_document_creation(normalized):
            logger.info("[IntentRouter] Intent detected: document_creation")
            return Intent("document_creation", {"query": user_input})

        if any(w in normalized for w in ("battery", "battery status", "battery level", "battery percentage", "charging status")):
            logger.info("[IntentRouter] Intent detected: battery_status")
            return Intent("battery_status")

        if self._asks_for_smarthome(normalized):
            logger.info("[IntentRouter] Intent detected: smarthome_control")
            return Intent("smarthome_control", {"raw": user_input, "normalized": normalized})

        if "brightness" in normalized:
            logger.info("[IntentRouter] Intent detected: brightness_control")
            return Intent("brightness_control", {"raw": user_input, "normalized": normalized})

        if any(w in normalized for w in ("mute", "unmute", "volume", "sound level", "audio level", "sound volume")):
            logger.info("[IntentRouter] Intent detected: audio_control")
            return Intent("audio_control", {"raw": user_input, "normalized": normalized})

        if self._asks_for_hud_overlay(normalized):
            overlay_type = self._parse_hud_overlay(normalized)
            logger.info(f"[IntentRouter] Intent detected: hud_overlay ({overlay_type})")
            return Intent("hud_overlay", {"overlay_type": overlay_type, "raw": user_input, "query": user_input})

        if self._asks_for_voice_control(normalized):
            logger.info("[IntentRouter] Intent detected: voice_control")
            action = self._parse_voice_control_action(normalized)
            return Intent("voice_control", {"action": action, "raw": user_input})

        if self._asks_to_say_phrase(normalized):
            logger.info("[IntentRouter] Intent detected: say_phrase")
            phrase = self._extract_phrase_to_say(user_input, normalized)
            return Intent("say_phrase", {"phrase": phrase, "raw": user_input})

        if self._asks_for_open_file(normalized):
            logger.info("[IntentRouter] Intent detected: open_file")
            target = self._extract_file_target(user_input, normalized)
            return Intent("open_file", {"target": target, "raw": user_input})

        if self._asks_for_rag_query(normalized):
            logger.info("[IntentRouter] Intent detected: rag_query")
            return Intent("rag_query", {"query": user_input, "normalized": normalized})

        if self._asks_for_folder_creation(normalized):
            logger.info("[IntentRouter] Intent detected: folder_creation")
            folder_name, parent_loc = self._parse_folder_creation(normalized, user_input)
            return Intent("folder_creation", {"folder_name": folder_name, "location": parent_loc, "raw": user_input})

        confirm_m = re.search(r"\b(?:confirm|approve|authorize)\s+((?:AUTH|TICK)-[A-F0-9]{4,12})\b", normalized, re.IGNORECASE)
        if confirm_m:
            ticket_id = confirm_m.group(1).upper()
            logger.info(f"[IntentRouter] Intent detected: confirm_ticket ({ticket_id})")
            return Intent("confirm_ticket", {"ticket_id": ticket_id, "raw": user_input})

        if any(w in normalized for w in ("aura resume", "resume browser", "continue browser", "solved captcha", "captcha solved", "i solved the captcha")):
            logger.info("[IntentRouter] Intent detected: resume_browser")
            return Intent("resume_browser", {"raw": user_input})

        if self._asks_for_autonomous_browser(normalized):
            logger.info("[IntentRouter] Intent detected: autonomous_browser")
            return Intent("autonomous_browser", {"goal": user_input})

        if self._asks_for_hud_overlay(normalized):
            overlay_type = self._parse_hud_overlay(normalized)
            logger.info(f"[IntentRouter] Intent detected: hud_overlay ({overlay_type})")
            return Intent("hud_overlay", {"overlay_type": overlay_type, "raw": user_input})

        if self._asks_for_desktop_action(normalized):
            logger.info("[IntentRouter] Intent detected: desktop_action")
            verb, target = self._parse_desktop_action(normalized)
            return Intent("desktop_action", {"verb": verb, "target": target, "raw": user_input})

        if any(w in normalized for w in ("restart", "reboot", "reload aura", "respawn aura")):
            logger.info("[IntentRouter] Intent detected: restart_aura")
            return Intent("restart_aura")

        # Use ResearchDecision to determine if research is needed
        needs_research, reason, search_mode = self.research_decision.analyze(user_input)

        logger.info(
            f"[IntentRouter] ResearchDecision - Needs research: {needs_research}, Reason: {reason}, Mode: {search_mode.value}"
        )

        if needs_research:
            intent_type = (
                "web_search"
                if search_mode == SearchMode.QUICK
                else (
                    "deep_research" if search_mode == SearchMode.DEEP else "web_search"
                )
            )
            logger.info(f"[IntentRouter] Intent detected: {intent_type}")
            return Intent(intent_type, {"mode": search_mode.value})

        logger.info("[IntentRouter] Intent detected: provider_chat")
        return Intent("provider_chat")

    def remember_detected_facts(self, facts: list[MemoryFact]) -> None:
        for fact in facts:
            self.memory.upsert_fact(fact.category, fact.key, fact.value)

    def _asks_for_profile_lookup(self, normalized: str) -> bool:
        return any(
            phrase in normalized
            for phrase in ("who am i", "what is my name", "what's my name", "do you know my name", "what is my profile", "what's my profile")
        ) or (normalized in {"my name", "my profile"})

    def _asks_for_projects_lookup(self, normalized: str) -> bool:
        # Action keywords disqualify pure memory lookup
        if any(w in normalized for w in ("update", "fix", "clean", "run", "build", "test", "create", "open", "modify", "edit", "write", "generate", "deploy", "git", "commit")):
            return False
        # Must be a question or lookup phrase
        lookup_triggers = (
            "what are my projects", "what is my project", "what's my project", "which projects",
            "list my projects", "show my projects", "tell me my projects", "what projects",
            "what am i working on", "what am i building", "projects i remember", "do you remember my project"
        )
        return any(t in normalized for t in lookup_triggers) or normalized in {"my projects", "my project list"}

    def _asks_for_skills_lookup(self, normalized: str) -> bool:
        if any(w in normalized for w in ("learn", "study", "improve", "practice", "how to")):
            return False
        lookup_triggers = (
            "what are my skills", "what's my skill", "what is my skill", "which skills",
            "list my skills", "show my skills", "tell me my skills", "how many skills",
            "skills i remember", "do you remember my skills"
        )
        return any(t in normalized for t in lookup_triggers) or normalized in {"my skills", "my skill list"}

    def _asks_for_goals_lookup(self, normalized: str) -> bool:
        lookup_triggers = (
            "what are my goals", "what is my goal", "what's my goal", "which goals",
            "list my goals", "show my goals", "tell me my goals", "goals i remember",
            "do you remember my goals"
        )
        return any(t in normalized for t in lookup_triggers) or normalized in {"my goals", "my goal list"}

    def _asks_for_preferences_lookup(self, normalized: str) -> bool:
        lookup_triggers = (
            "what are my preferences", "what is my preference", "what's my preference",
            "list my preferences", "show my preferences", "tell me my preferences",
            "preferences i remember", "do you remember my preferences",
            "what is my favorite", "what's my favorite", "whats my favorite",
            "what is my favourite", "what's my favourite", "whats my favourite",
            "what is my preferred", "what's my preferred", "whats my preferred",
            "what is my editor", "what's my editor", "whats my editor",
            "what is my language", "what's my language", "whats my language",
            "do you remember my favorite", "do you know my favorite"
        )
        return any(t in normalized for t in lookup_triggers) or normalized in {"my preferences", "my preference list"}

    def _parse_specific_preference(self, normalized: str) -> str:
        import re
        m = re.search(r"(?:favorite|favourite|preferred)\s+(.+?)(?:\?|$)", normalized, re.IGNORECASE)
        if m:
            sub = m.group(1).strip()
            return re.sub(r"[^a-zA-Z0-9_]+", "_", sub).strip("_")
        if "editor" in normalized or "ide" in normalized:
            return "editor"
        if "programming language" in normalized or "language" in normalized:
            return "programming_language"
        return ""

    def _asks_for_restart(self, normalized: str) -> bool:
        clean = re.sub(r"^aura\s+", "", normalized).strip()
        triggers = (
            "restart aura", "restart aura ai", "restart", "reboot aura", "reboot",
            "restart app", "restart the app", "restart application", "restart yourself",
            "reload aura", "relaunch aura", "restart system", "reboot system",
            "graceful restart", "restart now", "please restart", "aura restart"
        )
        if clean in triggers or normalized in triggers:
            return True
        if any(clean.startswith(t) for t in ("restart aura", "reboot aura", "relaunch aura", "reload aura")):
            return True
        return False

    def _asks_for_time_or_date(self, normalized: str) -> bool:
        # Prevent freshness constraints like "today's exchange rate" from matching
        if any(w in normalized for w in ("rate", "exchange", "conversion", "price")):
            return False
            
        time_words = ("time", "date")
        has_time_word = any(word in normalized for word in time_words)
        
        # Explicitly asking for time or date
        if has_time_word and any(
            phrase in normalized
            for phrase in (
                "what is",
                "what's",
                "tell me",
                "current",
                "what time",
                "what date",
                "todays",
                "today's",
                "today",
            )
        ):
            return True
            
        return False

    def _asks_for_weather(self, normalized: str) -> bool:
        if "weather" in normalized or "temperature" in normalized:
            # If asking for general current weather or current place
            if any(
                p in normalized
                for p in ("what is", "what's", "how is", "tell me", "current", "today", "now", "check")
            ):
                # If a specific remote city is explicitly specified (e.g. "weather in tokyo"), let web_search handle it
                if " in " not in normalized and " for " not in normalized:
                    return True
                if "in my" in normalized or "in here" in normalized or "for me" in normalized:
                    return True
        return False

    def _asks_for_doc_update(self, normalized: str) -> bool:
        triggers = (
            "update doc", "update docs", "update document", "update documents", "update documentation",
            "update milestone", "update milestones", "update readme", "update roadmap",
            "sync doc", "sync docs", "sync document", "sync documents", "sync documentation",
            "generate docs", "generate documentation", "create documentation", "refresh docs",
            "refresh documents", "refresh documentation"
        )
        return any(t in normalized for t in triggers) or (
            any(w in normalized for w in ("update", "sync", "refresh", "generate"))
            and any(dt in normalized for dt in ("docs", "document", "documents", "documentation", "milestone", "milestones", "readme", "roadmap"))
        )

    def _asks_for_engineering_task(self, normalized: str) -> bool:
        if normalized.startswith(("what is", "how does", "explain", "why", "tell me about")):
            return False

        if self._asks_for_folder_creation(normalized) or self._asks_for_document_creation(normalized):
            return False

        clean_norm = re.sub(r"^aura\s+", "", normalized).strip()
        verbs = ("add ", "implement ", "build ", "create ", "fix ", "repair ", "refactor ", "write code ", "write a script ", "code a ", "modify code ", "edit code ", "develop ")
        targets = ("widget", "feature", "component", "class", "function", "module", "script", "api", "endpoint", "test", "overlay", "service", "handler", "adapter", "manager", "plugin", "bug", "code", "file", ".py")

        for v in verbs:
            if clean_norm.startswith(v):
                if any(t in clean_norm for t in targets) or "to my project" in clean_norm or "in my project" in clean_norm or "for my project" in clean_norm or ".py" in clean_norm:
                    return True

        if (".py" in clean_norm or "to my project" in clean_norm or "in my project" in clean_norm) and any(v.strip() in clean_norm for v in verbs):
            return True

        return False

    def _asks_for_document_creation(self, normalized: str) -> bool:
        doc_targets = ("document", "doc", "docx", "word file", "word document", "pdf file", "text file", "leave letter document", "leave letter doc")
        create_verbs = ("create", "generate", "make", "save", "draft", "export", "build", "write and save")
        if any(dt in normalized for dt in doc_targets) and any(cv in normalized for cv in create_verbs):
            return True
        return False

    def _asks_for_overlay_toggle(self, normalized: str) -> bool:
        triggers = ("weather widget", "weather hud", "weather overlay",
                    "system monitor", "system hud", "system overlay", "resource monitor", "hardware monitor",
                    "tasks widget", "tasks overlay", "agent tasks",
                    "personal os widget", "personal os overlay", "personal os dashboard", "personal os",
                    "system status widget", "system status overlay", "chat hud", "chat overlay",
                    "jarvis rings", "jarvis widget", "rings hud", "jarvis hud", "rings overlay", "voice rings", "jarvis")
        actions = ("open", "show", "toggle", "launch", "display", "hide", "close", "bring up")
        if any(t in normalized for t in triggers):
            if any(a in normalized for a in actions) or "overlay" in normalized or "widget" in normalized or "hud" in normalized or "rings" in normalized:
                return True
        return False

    _asks_for_hud_overlay = _asks_for_overlay_toggle

    def _asks_for_voice_control(self, normalized: str) -> bool:
        start_triggers = (
            "start listening", "start voice listening", "start voice", "listen to me",
            "start continuous listening", "voice listen", "listen", "start listening mode",
            "turn on voice", "enable voice", "voice on", "voice listening on", "open listening"
        )
        stop_triggers = (
            "stop listening", "stop voice listening", "stop voice", "stop continuous listening",
            "pause listening", "turn off voice", "disable voice", "voice off",
            "voice listening off", "close listening", "cancel listening", "shut up"
        )
        status_triggers = (
            "voice status", "are you listening", "is listening on", "is voice listening on",
            "voice listening status", "listening status"
        )
        return (
            normalized in start_triggers
            or normalized in stop_triggers
            or normalized in status_triggers
            or any(normalized.startswith(t) for t in ("start listening", "stop listening", "start voice", "stop voice", "pause listening"))
            or any(normalized == t for t in ("listening", "voice listening"))
        )

    def _parse_voice_control_action(self, normalized: str) -> str:
        stop_words = ("stop", "pause", "disable", "turn off", "off", "cancel", "close", "shut up")
        status_words = ("status", "are you", "is listening", "check")
        if any(w in normalized for w in stop_words):
            return "stop"
        elif any(w in normalized for w in status_words):
            return "status"
        return "start"

    def _asks_to_say_phrase(self, normalized: str) -> bool:
        if self._asks_for_voice_control(normalized):
            return False
        return normalized.startswith(("say ", "speak ", "read aloud ", "repeat after me "))

    def _extract_phrase_to_say(self, user_input: str, normalized: str) -> str:
        for p in ("say ", "speak ", "read aloud ", "repeat after me "):
            if normalized.startswith(p):
                return user_input.strip()[len(p):].strip(" '\"")
        return user_input.strip()

    def _asks_for_open_file(self, normalized: str) -> bool:
        if self._asks_for_voice_control(normalized):
            return False
        
        # Check for explicit file open patterns
        open_verbs = ("open ", "launch ", "find and open ", "display ", "show ")
        if not normalized.startswith(open_verbs):
            return False

        # Exclude folders and apps (which are handled by desktop_action)
        clean = normalized
        for v in open_verbs:
            if clean.startswith(v):
                clean = clean[len(v):].strip()
                break

        # Remove noise words
        import re
        has_file_word = bool(re.search(r"\b(file|document|doc|pdf|txt|docx|sheet|presentation|image|photo)\b", clean, re.IGNORECASE))
        clean_target = re.sub(r"\b(my|the|a|an|file|document|doc)\b", " ", clean).strip()

        # If it matches a known folder or known app, let desktop_action handle it
        known_folders = ("documents", "downloads", "desktop", "pictures", "photos", "music", "videos", "c drive", "d drive")
        known_apps = (
            "notepad", "calculator", "calc", "chrome", "google chrome", "msedge", "edge", "microsoft edge",
            "firefox", "brave", "spotify", "cmd", "command prompt", "powershell", "terminal",
            "code", "vscode", "vs code", "visual studio code", "explorer", "file explorer",
            "task manager", "settings", "paint", "mspaint", "word", "ms word", "excel", "ms excel",
            "powerpoint", "whatsapp", "antigravity", "antigravity ide", "start menu", "start"
        )
        if clean_target.lower() in known_folders or clean_target.lower() in known_apps or clean.lower() in known_apps:
            return False

        hud_triggers = ("weather hud", "weather overlay", "weather widget", "system hud", "system monitor", "system overlay", "jarvis rings", "jarvis hud", "chat overlay", "chat hud", "task overlay", "task hud", "personal os", "matrix overlay")
        if any(ht in clean.lower() for ht in hud_triggers):
            return False

        # If user explicitly said "file" or "document" (e.g. "open importent file") -> Always file!
        if has_file_word:
            return True

        # Match file extensions
        file_exts = (".pdf", ".docx", ".doc", ".txt", ".md", ".json", ".csv", ".xlsx", ".pptx", ".py", ".html", ".png", ".jpg")
        if any(clean_target.lower().endswith(ext) for ext in file_exts):
            return True

        # Match keywords like resume, cv, report, notes, invoice, script, important
        file_keywords = ("resume", "cv", "bio", "report", "notes", "invoice", "document", "spec", "spreadsheet", "important", "importent")
        if any(k in clean_target.lower() for k in file_keywords):
            return True

        # Check if FileService can find a matching file on the user's disk
        try:
            from tools.file_service import FileService
            best_match = FileService.get_instance().find_best_file(clean_target)
            if best_match is not None:
                return True
        except Exception:
            pass

        # If it has underscores or hyphens and doesn't look like an app
        if ("_" in clean_target or "-" in clean_target) and not clean_target.startswith(("app", "window")):
            return True

        return False

    def _extract_file_target(self, user_input: str, normalized: str) -> str:
        open_verbs = ("find and open ", "open ", "launch ", "display ", "show ")
        for v in open_verbs:
            if normalized.startswith(v):
                # Preserve original casing from user_input
                return user_input.strip()[len(v):].strip(" '\"")
        return user_input.strip()

    def _asks_for_rag_query(self, normalized: str) -> bool:
        rag_triggers = (
            "in my resume", "from my resume", "about my resume", "my resume say", "check my resume",
            "in my documents", "from my documents", "search my documents", "search my files",
            "in my notes", "from my notes", "summarize my resume", "summarize my document",
            "rag query", "rag search", "ask my documents"
        )
        return any(t in normalized for t in rag_triggers)

    def _asks_for_folder_creation(self, normalized: str) -> bool:
        clean = re.sub(r"^aura\s+", "", normalized).strip()
        triggers = ("create folder", "create a folder", "create new folder", "make folder", "make a folder", "make directory", "create directory", "new folder", "mkdir ")
        if any(t in clean for t in triggers):
            return True
        if ("folder" in clean or "directory" in clean) and any(v in clean for v in ("create", "make", "build", "new")):
            return True
        return False

    def _parse_folder_creation(self, normalized: str, user_input: str) -> tuple[str, str]:
        clean = re.sub(r"^aura\s+", "", normalized).strip()
        
        # Determine location (desktop, downloads, documents, pictures, music, videos, workspace)
        loc = "desktop"
        if "in downloads" in clean or "on downloads" in clean:
            loc = "downloads"
        elif "in documents" in clean or "on documents" in clean or "in document" in clean:
            loc = "documents"
        elif "in pictures" in clean or "on pictures" in clean:
            loc = "pictures"
        elif "in workspace" in clean or "in project" in clean:
            loc = "workspace"
        elif "in desktop" in clean or "on desktop" in clean:
            loc = "desktop"

        # Extract folder name
        # e.g., "create jarvis folder in desktop" -> "jarvis"
        # e.g., "make a folder called projects on desktop" -> "projects"
        name_match = re.search(r"(?:called|named)\s+([a-zA-Z0-9_\-]+)", clean)
        if name_match:
            folder_name = name_match.group(1)
        else:
            # Pattern: (?:create|make|new)\s+(?:a\s+|new\s+)?(?:folder\s+|directory\s+)?([a-zA-Z0-9_\-]+)(?:\s+folder|\s+directory)?(?:\s+(?:in|on|at)\s+(?:the\s+)?(?:desktop|downloads|documents|pictures|workspace|project))?
            m = re.search(r"(?:create|make|new|mkdir)\s+(?:a\s+|new\s+)?(?:folder\s+|directory\s+)?([a-zA-Z0-9_\-]+)(?:\s+folder|\s+directory)?", clean)
            if m and m.group(1) not in ("folder", "directory", "new", "a", "the", "in", "on", "at", "desktop", "downloads", "documents"):
                folder_name = m.group(1)
            else:
                # Fallback: extract token before "folder"
                before_folder = re.search(r"([a-zA-Z0-9_\-]+)\s+(?:folder|directory)", clean)
                if before_folder and before_folder.group(1) not in ("create", "make", "new", "a", "the", "in", "on", "at"):
                    folder_name = before_folder.group(1)
                else:
                    folder_name = "New_Folder"

        return folder_name, loc

    def _asks_for_autonomous_browser(self, normalized: str) -> bool:
        # Autonomous browsing is currently paused per user request.
        # Set environment variable AURA_AUTONOMOUS_BROWSER_ENABLED=1 to re-enable.
        if os.environ.get("AURA_AUTONOMOUS_BROWSER_ENABLED", "0") != "1":
            return False

        clean = re.sub(r"^aura\s+", "", normalized).strip()
        site_names = (
            "wikipedia", "amazon", "google", "youtube", "github", "reddit",
            "flipkart", "ebay", "twitter", "flights", "flight", "browser",
            "website", "webpage", "web page"
        )
        browser_verbs = (
            "go to", "navigate to", "open", "browse to", "search", "find",
            "scroll", "click", "type", "add to cart", "checkout", "book", "buy"
        )
        if any(f"go to {s}" in clean for s in site_names) or any(f"navigate to {s}" in clean for s in site_names):
            return True
        if re.search(r"\bgo to\s+[a-zA-Z0-9_\-\.]+\.(com|org|net|io|in|edu|gov|co)\b", clean):
            return True
        if re.search(r"\bhttps?://[^\s]+", clean):
            return True
        if any(s in clean for s in site_names) and any(v in clean for v in browser_verbs):
            return True
        if any(clean.startswith(t) for t in (
            "browse to", "browse ", "open browser", "search web for",
            "search google for", "search wikipedia for", "search youtube for",
            "search amazon for", "find flight", "find cheapest flight", "add to cart",
            "click on screen", "look at screen"
        )):
            return True
        return False

    def _asks_for_hud_overlay(self, normalized: str) -> bool:
        clean = re.sub(r"^aura\s+", "", normalized).strip()
        triggers = (
            "weather widget", "weather hud", "weather overlay",
            "system monitor", "system hud", "system overlay", "resource monitor", "hardware monitor", "performance hud", "telemetry hud",
            "tasks widget", "tasks overlay", "agent tasks", "agent status overlay", "agent status", "task status", "task hud",
            "personal os widget", "personal os overlay", "personal os dashboard", "personal os", "dashboard overlay", "os dashboard",
            "system status widget", "system status overlay", "chat hud", "chat overlay",
            "jarvis rings", "jarvis widget", "rings hud", "jarvis hud", "rings overlay", "voice rings", "audio rings", "core rings", "jarvis",
            "matrix overlay", "matrix falling code", "matrix rain", "matrix", "cyberpunk",
            "open hud", "show hud", "launch hud", "toggle hud", "hud overlay", "open gui", "launch gui", "show gui", "control center"
        )
        actions = ("open", "show", "toggle", "launch", "display", "hide", "close", "bring up")
        if any(t in clean for t in triggers):
            if any(a in clean for a in actions) or any(k in clean for k in ("overlay", "widget", "hud", "rings", "dashboard", "monitor")):
                return True
        return False

    def _parse_hud_overlay(self, normalized: str) -> str:
        clean = normalized.lower()
        if any(w in clean for w in ("weather",)):
            return "weather_overlay"
        elif any(w in clean for w in ("jarvis", "ring", "core", "voice ring")):
            return "jarvis_rings"
        elif any(w in clean for w in ("system", "monitor", "hardware", "telemetry", "performance", "resource")):
            return "system_monitor"
        elif any(w in clean for w in ("matrix", "rain", "falling code", "cyberpunk")):
            return "matrix_overlay"
        elif any(w in clean for w in ("task", "agent status", "dag")):
            return "task_status"
        elif any(re.search(r"\b" + re.escape(w) + r"\b", clean) for w in ("personal", "dashboard", "personal os", "os dashboard")):
            return "personal_os"
        elif any(w in clean for w in ("chat",)):
            return "chat_overlay"
        return "main_hud"

    def _asks_for_desktop_action(self, normalized: str) -> bool:
        if self._asks_for_voice_control(normalized):
            return False

        known_apps = (
            "notepad", "calculator", "calc", "chrome", "edge", "spotify", "cmd", "command prompt",
            "powershell", "terminal", "code", "vscode", "vs code", "visual studio code",
            "explorer", "file explorer", "task manager", "settings", "paint", "word", "excel",
            "documents", "downloads", "pictures", "music", "videos", "desktop"
        )
        verbs = ("open ", "launch ", "start ", "run ", "close ", "kill ", "minimize ", "maximize ", "restore ", "focus ", "activate ", "switch to ", "organize ", "sort ", "clean up ", "tidy ")
        
        if normalized.startswith(verbs):
            # Ignore web searches or URLs
            if any(w in normalized for w in ("http", "www.", ".com", ".org", ".io", "search", "weather widget", "system monitor")):
                return False
            return True

        if any(a in normalized for a in known_apps) and any(v in normalized for v in ("open", "launch", "start", "run", "close", "kill", "minimize", "maximize", "focus", "organize", "sort")):
            return True

        if any(action in normalized for action in ("take a screenshot", "screenshot", "screen capture", "organize downloads", "sort downloads", "clean downloads")):
            return True

        return False

    def _parse_desktop_action(self, normalized: str) -> tuple[str, str]:
        import re
        verbs = ["switch to", "focus", "activate", "minimize", "maximize", "restore", "close", "kill", "organize", "sort", "clean up", "tidy", "open", "launch", "start", "run"]
        detected_verb = "open"
        target = normalized

        for v in verbs:
            if normalized.startswith(v):
                detected_verb = v.split()[0]
                target = normalized[len(v):].strip()
                break
            elif f" {v} " in f" {normalized} ":
                detected_verb = v.split()[0]
                parts = normalized.split(v, 1)
                target = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                break

        # Clean noise words from target
        target = re.sub(r"\b(my|the|a|an|app|application|folder|directory)\b", " ", target, flags=re.IGNORECASE)
        target = " ".join(target.split()).strip()
        return detected_verb, target

    def _is_memory_statement(self, user_input: str) -> bool:
        clean = user_input.strip()
        if clean.endswith("?"):
            return False
        lower = clean.lower()
        # Question indicators disqualify memory storage statements
        question_words = (
            "what is", "what's", "whats", "what are", "who is", "who's", "which is", "which are",
            "where is", "when is", "how is", "how are", "can you", "do you", "tell me", "show me",
            "recall", "lookup", "what do you", "do you remember", "what was", "who was"
        )
        if any(lower.startswith(qw) or f" {qw} " in f" {lower} " for qw in question_words):
            return False

        # Declarative memory triggers
        statement_triggers = (
            "remember that", "remember:", "save that", "note that", "keep in mind",
            "my favorite", "my favourite", "my preferred", "my name is", "i like", "i prefer",
            "i love", "my editor is", "my goal is", "i work on", "i am building", "set my",
            "learning", "studying", "i'm learning", "i am learning"
        )
        return any(t in lower for t in statement_triggers)

    def _needs_realtime_data(self, normalized: str) -> bool:
        realtime_terms = (
            "latest",
            "current",
            "today",
            "now",
            "news",
            "price",
            "weather",
            "score",
            "version",
            "release",
            "president",
            "ceo",
        )
        return any(term in normalized for term in realtime_terms)

    def _needs_deep_research(self, normalized: str) -> bool:
        """
        Check if the query requires deep research (multi-source, comparison, analysis).

        Args:
            normalized: Normalized user input

        Returns:
            True if deep research is needed
        """
        deep_research_patterns = (
            # Comparison queries
            "compare",
            "versus",
            "vs",
            "difference between",
            "which is better",
            "pros and cons",
            "advantages and disadvantages",
            "comparison",
            # Research and analysis queries
            "research",
            "analyze",
            "investigate",
            "study",
            # Explanation queries
            "explain how",
            "how does",
            "how to",
            "overview of",
            # Summarization from web
            "summarize from web",
            "read and summarize",
            "summarize the",
            # Read and understand
            "read and explain",
            "read and summarize",
            "read the",
        )

        return any(pattern in normalized for pattern in deep_research_patterns)

    def _asks_about_realtime_capability(self, normalized: str) -> bool:
        capability_terms = (
            "real time",
            "realtime",
            "live data",
            "web search",
            "internet",
        )
        question_terms = ("do you have", "can you", "are you able", "you have")
        return any(term in normalized for term in capability_terms) and any(
            term in normalized for term in question_terms
        )

    def _asks_for_screen_vision(self, normalized: str) -> bool:
        triggers = (
            "whats on my screen",
            "what's on my screen",
            "what is on my screen",
            "whats on screen",
            "what's on screen",
            "what is on screen",
            "whats on the screen",
            "what's on the screen",
            "what is on the screen",
            "what do you see on my screen",
            "what do you see on screen",
            "what do you see on the screen",
            "what am i looking at",
            "what is open on my screen",
            "what's open on my screen",
            "whats open on my screen",
            "what is open right now",
            "describe my screen",
            "describe what's on my screen",
            "describe whats on my screen",
            "describe the screen",
            "look at my screen",
            "see my screen",
            "can you see my screen",
            "read my screen",
            "read the screen",
            "analyze my screen",
            "check my screen",
            "inspect my screen",
            "capture screen",
            "take a screenshot and describe",
            "screenshot my screen",
            "screen vision",
        )
        if any(t in normalized for t in triggers):
            return True
        if "screen" in normalized and any(
            v in normalized
            for v in (
                "what is on",
                "whats on",
                "what's on",
                "what is visible",
                "what's visible",
                "describe",
                "see",
                "read",
                "look at",
                "analyze",
                "check",
                "inspect",
                "view",
                "show me",
                "tell me what",
            )
        ):
            return True
        return False

    def _asks_for_smarthome(self, normalized: str) -> bool:
        device_words = ("light", "lights", "bulb", "bulbs", "lamp", "lamps", "tapo", "kasa", "smart home", "smarthome")
        # Use exact word boundary matching so 'flight' or 'flights' does NOT match 'light'
        has_device = any(re.search(rf"\b{re.escape(w)}\b", normalized, re.IGNORECASE) for w in device_words)
        if not has_device:
            return False
        if any(w in normalized for w in ("traffic light", "flashlight", "highlight", "flight", "flights", "skylight")):
            return False
        return True


