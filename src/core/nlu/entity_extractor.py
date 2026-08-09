"""
NLU Entity Extractor
Location: src/core/nlu/entity_extractor.py

Extracts structured entities (app names, file paths, search queries, URLs, slots)
from normalized text.
"""

import re
from pathlib import Path
from typing import Any

# Known desktop applications mapping aliases to canonical app names
_APP_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "chorme": "Google Chrome",
    "google chorme": "Google Chrome",
    "browser": "Google Chrome",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "notepad": "Notepad",
    "text editor": "Notepad",
    "calc": "Calculator",
    "calculator": "Calculator",
    "terminal": "Windows Terminal",
    "cmd": "Command Prompt",
    "powershell": "PowerShell",
    "spotify": "Spotify",
    "edge": "Microsoft Edge",
    "ms edge": "Microsoft Edge",
    "firefox": "Firefox",
    "mozilla firefox": "Firefox",
}


class EntityExtractor:
    """Extracts entities and slots from text."""

    def extract_entities(self, text: str) -> dict[str, Any]:
        """
        Extract all entities from normalized text.

        Returns dict of extracted entities:
            - app_name: canonical application name
            - file_path: target file path or filename
            - directory_path: target directory path
            - search_query: query string for search/research
            - url: web URL if present
            - topic: topic of query
            - project_name: project name if mentioned
        """
        text_lower = text.lower().strip()
        entities: dict[str, Any] = {}

        # 1. Extract Application Name
        app_name = self._extract_app_name(text_lower)
        if app_name:
            entities["app_name"] = app_name

        # 2. Extract File Paths
        file_path = self._extract_file_path(text)
        if file_path:
            entities["file_path"] = file_path

        # 3. Extract Directory / Folder
        directory = self._extract_directory(text_lower)
        if directory:
            entities["directory"] = directory

        # 4. Extract Web URLs
        url = self._extract_url(text)
        if url:
            entities["url"] = url

        # 5. Extract Search Query
        search_query = self._extract_search_query(text)
        if search_query:
            entities["search_query"] = search_query

        # 6. Extract Project Name
        project_name = self._extract_project_name(text_lower)
        if project_name:
            entities["project_name"] = project_name

        return entities

    def _extract_app_name(self, text_lower: str) -> str | None:
        """Extract canonical app name if mentioned."""
        # Direct lookup for app aliases
        for alias, canonical in _APP_ALIASES.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text_lower):
                return canonical

        # Generic open/launch pattern: "open X", "launch X", "start X"
        match = re.search(r"\b(?:open|launch|start|run|close|focus)\s+([a-z0-9 _-]{2,30})", text_lower)
        if match:
            target = match.group(1).strip()
            # Clean trailing words like "app", "application", "please"
            target = re.sub(r"\b(app|application|please|plz|now)\b", "", target).strip()
            if target in _APP_ALIASES:
                return _APP_ALIASES[target]
            if target and not any(w in target for w in ["file", "folder", "directory", "project", "code", "weather"]):
                return target.title()

        return None

    def _extract_file_path(self, text: str) -> str | None:
        """Extract file path or filename."""
        # Match explicit paths with extensions (.py, .txt, .json, .md, .csv, etc.)
        match = re.search(r"[\w\-/\\.]+\.[a-zA-Z0-9]{1,8}", text)
        if match:
            return match.group(0)

        # Match phrases like "in file X" or "file named X"
        match_named = re.search(r"\bfile\s+(?:named\s+|called\s+)?([a-zA-Z0-9_\-\.]+)", text, re.IGNORECASE)
        if match_named:
            val = match_named.group(1).strip()
            if val.lower() not in ("this", "the", "a", "my", "please", "plz", "now", "today", "here", "there", "it"):
                return val

        return None

    def _extract_directory(self, text_lower: str) -> str | None:
        """Extract directory or folder name."""
        dirs = ["desktop", "documents", "downloads", "pictures", "videos", "music", "project folder", "home"]
        for d in dirs:
            if d in text_lower:
                return d.title() if d != "project folder" else "Project"
        match = re.search(r"\b(?:folder|directory)\s+([a-z0-9_-]{2,30})", text_lower)
        if match:
            return match.group(1).strip().title()
        return None

    def _extract_url(self, text: str) -> str | None:
        """Extract web URL."""
        match = re.search(r"https?://[^\s]+|www\.[^\s]+", text)
        return match.group(0) if match else None

    def _extract_search_query(self, text: str) -> str | None:
        """Extract search or research query."""
        patterns = [
            r"\b(?:search|look up|find|google)\s+(?:for\s+|about\s+)?(.+)",
            r"\b(?:what is|who is|where is|how to|why does)\s+(.+)",
            r"\bweather\s+(?:in|for|today|tomorrow)?\s*(.*)",
        ]
        text_lower = text.lower()
        for p in patterns:
            match = re.search(p, text_lower, re.IGNORECASE)
            if match and match.group(1).strip():
                query = match.group(1).strip().strip("?")
                if query:
                    return query
        return None

    def _extract_project_name(self, text_lower: str) -> str | None:
        """Extract project name if mentioned."""
        match = re.search(r"\bproject\s+([a-z0-9_-]{2,30})", text_lower)
        if match and match.group(1) not in ("folder", "directory", "files", "code"):
            return match.group(1).strip().title()
        return None
