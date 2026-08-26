from integrations.smarthome.tapo_client import parse_color_to_hsv_or_temp, COLOR_TEMP_PRESETS
import re

print("Parsing 'light blue':", parse_color_to_hsv_or_temp("light blue"))

for name in sorted(COLOR_TEMP_PRESETS.keys(), key=len, reverse=True):
    if re.search(r"\b" + re.escape(name) + r"\b", "light blue"):
        print("COLOR_TEMP_PRESETS matched:", name)
