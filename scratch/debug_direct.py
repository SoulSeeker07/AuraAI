import sys
import inspect
sys.path.insert(0, r"D:\Sreekanta\VS Code Project\Desktop AI\AuraAI\src")
import integrations.smarthome.tapo_client as tc

print(inspect.getsource(tc.parse_color_to_hsv_or_temp))
