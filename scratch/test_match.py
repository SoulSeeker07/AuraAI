triggers = ("weather widget", "weather hud", "weather overlay",
            "system monitor", "system hud", "system overlay", "resource monitor", "hardware monitor",
            "tasks widget", "tasks overlay", "agent tasks",
            "personal os widget", "personal os overlay", "personal os dashboard", "personal os",
            "system status widget", "system status overlay", "chat hud", "chat overlay",
            "jarvis rings", "jarvis widget", "rings hud", "jarvis hud", "rings overlay", "voice rings", "jarvis")
actions = ("open", "show", "toggle", "launch", "display", "hide", "close", "bring up")

normalized = "show weather hud"
print("trigger matches:", [t for t in triggers if t in normalized])
print("action matches:", [a for a in actions if a in normalized])
