"""
Goal Classifier
Categorizes user desktop goals into functional domains (workspace, system_control, diagnostics, media).
"""


class GoalClassifier:
    """
    Classifies natural language goals into functional desktop categories.
    """

    CATEGORY_KEYWORDS = {
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
        "audio": ["volume", "sound", "mute", "unmute", "audio", "speaker", "mic"],
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
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in lower_text:
                    return category
        return "general"
