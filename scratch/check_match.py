import re
from integrations.smarthome.tapo_client import COLOR_NAME_TO_HSV, COLOR_TEMP_PRESETS

clean_query = "set light color to light blue"
for temp_name in sorted(COLOR_TEMP_PRESETS.keys(), key=len, reverse=True):
    if re.search(r"\b" + re.escape(temp_name) + r"\b", clean_query):
        print("Matched temp_name:", temp_name)
        break

for color_name in sorted(COLOR_NAME_TO_HSV.keys(), key=len, reverse=True):
    if re.search(r"\b" + re.escape(color_name) + r"\b", clean_query):
        print("Matched color_name:", color_name)
        break
