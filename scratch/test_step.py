import sys
sys.path.insert(0, r"D:\Sreekanta\VS Code Project\Desktop AI\AuraAI\src")
import integrations.smarthome.tapo_client as tc

color_input = "light blue"
norm = color_input.strip().lower()
norm = norm.replace("worm", "warm").replace("lite", "light").replace("purpule", "purple")
norm = norm.replace("blu", "blue").replace("gren", "green")

print("norm is:", repr(norm))
print("in COLOR_NAME_TO_HSV:", norm in tc.COLOR_NAME_TO_HSV)
if norm in tc.COLOR_NAME_TO_HSV:
    print("MATCHED 1:", tc.COLOR_NAME_TO_HSV[norm])
