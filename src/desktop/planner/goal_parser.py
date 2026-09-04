"""
Goal Parser
Parses natural language goal strings into structured intent definitions and parameter dictionaries.
"""

import re
from typing import Any

from .desktop_goal import DesktopGoal, GoalPriority


class GoalParser:
    """
    Parses user natural language goal inputs.
    """

    def parse(self, text: str, parameters: dict[str, Any] | None = None) -> DesktopGoal:
        """
        Parse natural language goal text into a DesktopGoal object.

        Args:
            text: Natural language string
            parameters: Optional initial parameters

        Returns:
            Parsed DesktopGoal
        """
        params = (parameters or {}).copy()
        clean_text = text.strip()
        lower_text = clean_text.lower()

        # Extract explicit capability if formatted like capability:arg
        explicit_cap = None
        if ":" in clean_text and not clean_text.startswith("http"):
            parts = clean_text.split(":", 1)
            candidate_cap = parts[0].strip()
            if (
                candidate_cap.replace(".", "_").replace("-", "_").isidentifier()
                and len(parts) > 1
            ):
                explicit_cap = candidate_cap
                params["target"] = parts[1].strip()

        # Simple priority detection
        priority = GoalPriority.NORMAL
        if "urgent" in lower_text or "critical" in lower_text:
            priority = GoalPriority.CRITICAL
        elif "high priority" in lower_text:
            priority = GoalPriority.HIGH

        # ── Parse UIA natural language patterns if not already explicitly set ─
        if not explicit_cap:
            parsed_cap, parsed_params = self._parse_uia_intent(clean_text)
            if parsed_cap:
                explicit_cap = parsed_cap
                for k, v in parsed_params.items():
                    if k not in params or not params[k]:
                        params[k] = v

        return DesktopGoal(
            goal=clean_text,
            priority=priority,
            explicit_capability=explicit_cap,
            parameters=params,
        )

    def _parse_uia_intent(self, text: str) -> tuple[str | None, dict[str, Any]]:
        """
        Extract UIA capability and structured criteria (window_title, name, control_type, text)
        from natural language text.
        """
        lower = text.lower().strip()
        params: dict[str, Any] = {}

        # 1. Extract Window Title: "in <Window>" or "from <Window>" or "of <Window>"
        m_win = re.search(
            r"\b(?:in|into|from|of|on)\s+([A-Z0-9][a-zA-Z0-9_\-\.\s]*?)(?:\s+(?:window|app|application|dialog))?$",
            text,
        )
        if m_win:
            win_candidate = m_win.group(1).strip()
            # Ignore false positives like "into Search", "in Dark Mode", "of Button"
            if win_candidate.lower() not in [
                "search",
                "button",
                "checkbox",
                "textbox",
                "dark mode",
                "light mode",
                "menu",
                "list",
            ]:
                params["window_title"] = win_candidate

        # 2. Inspect Tree: "inspect UI tree in Notepad" / "get UI tree for Notepad"
        if any(
            k in lower
            for k in [
                "inspect tree",
                "inspect ui tree",
                "get tree",
                "get ui tree",
                "dump tree",
                "dump ui",
                "ui tree",
                "element tree",
            ]
        ):
            return ("uia.get_tree", params)

        # 3. Type Text: "type 'hello world' into Search in Notepad" / "type hello in search"
        m_type = re.search(
            r"^(?:please\s+)?(?:type|enter|write|input|fill)\s+(?:text\s+)?(?:['\"](?P<qtext>[^'\"]+)['\"]|(?P<rawtext>\S+))\s+(?:into|in|to)\s+(?P<target>[a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:in|into|on|from)\s+(?P<win>[A-Z0-9][a-zA-Z0-9_\-\.\s]*))?$",
            text,
            re.IGNORECASE,
        )
        if m_type:
            text_val = m_type.group("qtext") or m_type.group("rawtext") or ""
            target_elem = m_type.group("target").strip()
            win_val = m_type.group("win")
            if win_val:
                params["window_title"] = win_val.strip()
            params["text"] = text_val.strip()
            params["name"] = target_elem
            return ("uia.type_text", params)

        # Fallback type check: "type <text> into <element>"
        if any(lower.startswith(v) for v in ["type ", "enter ", "write ", "input ", "fill "]):
            q_match = re.search(r"['\"]([^'\"]+)['\"]", text)
            if q_match:
                params["text"] = q_match.group(1).strip()
            if "into " in lower or "in " in lower:
                return ("uia.type_text", params)

        # 4. Click / Double-Click
        is_keyboard_press = any(
            k in lower for k in ["press enter", "press tab", "press esc", "press escape", "press return", "press space"]
        )
        if not is_keyboard_press:
            is_double = "double click" in lower or "double-click" in lower
            target_cap = "uia.double_click" if is_double else "uia.click"
            m_click = re.search(
                r"^(?:please\s+)?(?:double[\s-]click|click|tap|invoke)\s+(?:on\s+)?(?:the\s+)?(?P<elem>[a-zA-Z0-9_\-\.\s]+?)(?:\s+(?P<ctype>button|link|menuitem|tab|item|icon|folder|drive))?(?:\s+(?:in|into|on|of)\s+(?P<win>[A-Z0-9][a-zA-Z0-9_\-\.\s]*))?$",
                text,
                re.IGNORECASE,
            )
            if m_click:
                elem_name = m_click.group("elem").strip()
                ctype = m_click.group("ctype")
                win_val = m_click.group("win")

                for drop in ["the", "a", "an", "button", "item", "link", "icon"]:
                    elem_name = re.sub(rf"\b{drop}\b", "", elem_name, flags=re.IGNORECASE).strip()

                params["name"] = elem_name
                params["control_type"] = ctype.title() if ctype else "Button"
                if win_val:
                    params["window_title"] = win_val.strip()
                return (target_cap, params)

            if lower.startswith(("click ", "click on ", "double click ", "double-click ", "double click on ")):
                elem_candidate = text
                for pfx in ["double click on the ", "double click the ", "double click on ", "double click ", "double-click on ", "double-click ", "click on the ", "click the ", "click on ", "click "]:
                    if elem_candidate.lower().startswith(pfx):
                        elem_candidate = elem_candidate[len(pfx) :].strip()
                        break
                if " in " in elem_candidate:
                    e_parts = elem_candidate.split(" in ", 1)
                    params["name"] = e_parts[0].replace("button", "").replace("icon", "").strip()
                    params["window_title"] = e_parts[1].strip()
                else:
                    params["name"] = elem_candidate.replace("button", "").replace("icon", "").strip()
                params["control_type"] = "Button"
                return (target_cap, params)

        # 5. Toggle: "toggle dark mode checkbox in Settings" / "toggle dark mode" / "uncheck box"
        is_toggle = lower.startswith("toggle ") or lower.startswith("uncheck ") or (
            lower.startswith("check ") and any(w in lower for w in ["checkbox", "check box", "switch", "box"])
        )
        if is_toggle:
            m_tog = re.search(
                r"^(?:please\s+)?(?:toggle|check|uncheck)\s+(?:the\s+)?(?P<elem>[a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:checkbox|check\s*box|switch))?(?:\s+(?:in|into|on|of)\s+(?P<win>[A-Z0-9][a-zA-Z0-9_\-\.\s]*))?$",
                text,
                re.IGNORECASE,
            )
            if m_tog:
                elem_name = m_tog.group("elem").strip()
                win_val = m_tog.group("win")
                for drop in ["the", "a", "an", "checkbox", "check box", "switch", "box"]:
                    elem_name = re.sub(rf"\b{drop}\b", "", elem_name, flags=re.IGNORECASE).strip()
                params["name"] = elem_name
                params["control_type"] = "CheckBox"
                if win_val:
                    params["window_title"] = win_val.strip()
                return ("uia.toggle", params)

        # 6. Find Element: "find element Save in Notepad" / "locate Save button"
        if any(k in lower for k in ["find element", "locate element", "search element", "find button", "locate button"]):
            m_find = re.search(
                r"^(?:please\s+)?(?:find|locate|search\s+for)\s+(?:the\s+)?(?:element\s+|button\s+)?(?P<elem>[a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:in|into|on|of)\s+(?P<win>[A-Z0-9][a-zA-Z0-9_\-\.\s]*))?$",
                text,
                re.IGNORECASE,
            )
            if m_find:
                elem_name = m_find.group("elem").strip()
                win_val = m_find.group("win")
                params["name"] = elem_name
                if win_val:
                    params["window_title"] = win_val.strip()
                return ("uia.find_element", params)

        # 7. Get Value / Read Text: "get value of Search in Notepad" / "read text from Search"
        if any(k in lower for k in ["get value", "read value", "get text", "read text"]):
            m_val = re.search(
                r"^(?:please\s+)?(?:get|read)\s+(?:the\s+)?(?:value|text)\s+(?:of|from)\s+(?P<elem>[a-zA-Z0-9_\-\.\s]+?)(?:\s+(?:in|into|on)\s+(?P<win>[A-Z0-9][a-zA-Z0-9_\-\.\s]*))?$",
                text,
                re.IGNORECASE,
            )
            if m_val:
                elem_name = m_val.group("elem").strip()
                win_val = m_val.group("win")
                params["name"] = elem_name
                if win_val:
                    params["window_title"] = win_val.strip()
                return ("uia.get_value", params)

        return (None, {})

