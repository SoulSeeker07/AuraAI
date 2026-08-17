"""
Goal Classifier
Categorizes user desktop goals into functional domains (workspace, system_control, diagnostics, media).
"""


class GoalClassifier:
    """
    Classifies natural language goals into functional desktop categories.
    """

    CATEGORY_KEYWORDS = {
        "uia": [
            "click button",
            "press button",
            "tap button",
            "invoke button",
            "click on",
            "click the",
            "click",
            "type into",
            "write into",
            "type text",
            "enter text",
            "input text",
            "fill text",
            "toggle checkbox",
            "toggle switch",
            "check box",
            "uncheck",
            "inspect tree",
            "ui tree",
            "element tree",
            "find element",
            "locate element",
            "search element",
            "get value of",
            "read value",
            "read text from",
            "get field",
            "select option",
            "select item",
            "choose option",
            "choose item",
            "button",
            "checkbox",
            "textbox",
            "input field",
        ],
        "window": [
            "window",
            "focus",
            "bring up",
            "minimize",
            "maximize",
            "switch to",
            "restore",
            "close",
        ],
        "clipboard": ["clipboard", "copy", "paste", "copied", "clear clipboard"],
        "display": ["display", "screen", "resolution", "brightness", "monitor"],
        "audio": [
            "volume",
            "sound",
            "mute",
            "unmute",
            "audio",
            "speaker",
            "speakers",
            "microphone",
            "microphones",
            "mic",
        ],
        "power": [
            "battery",
            "power",
            "shutdown",
            "restart",
            "sleep",
            "hibernate",
            "lock",
        ],
        "network": [
            "wifi",
            "internet",
            "ping",
            "ip address",
            "dns",
            "network",
            "latency",
            "connect",
        ],
    }

    def classify(self, text: str) -> str:
        """
        Classify text into a desktop category.

        Args:
            text: Goal text

        Returns:
            Category name string (defaults to 'general')
        """
        lower_text = text.lower()
        best_category = "general"
        best_len = 0

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in lower_text:
                    if len(kw) > best_len:
                        best_len = len(kw)
                        best_category = category
        return best_category

