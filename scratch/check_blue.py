from integrations.smarthome.tapo_client import COLOR_NAME_TO_HSV
print("'light blue' in COLOR_NAME_TO_HSV:", "light blue" in COLOR_NAME_TO_HSV)
print("Keys with 'blue':", [k for k in COLOR_NAME_TO_HSV if "blue" in k])
