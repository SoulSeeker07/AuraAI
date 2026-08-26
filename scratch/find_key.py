from integrations.smarthome.tapo_client import COLOR_TEMP_PRESETS
print("Matching presets for 'light blue':", [k for k in COLOR_TEMP_PRESETS if k in 'light blue'])
for k in COLOR_TEMP_PRESETS:
    if k in 'light blue':
        print(f"Key '{k}' in 'light blue'")
