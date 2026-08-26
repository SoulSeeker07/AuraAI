from integrations.smarthome.tapo_client import parse_color_to_hsv_or_temp

print("parse_color_to_hsv_or_temp('light blue'):", parse_color_to_hsv_or_temp("light blue"))
print("parse_color_to_hsv_or_temp('warm green'):", parse_color_to_hsv_or_temp("warm green"))
print("parse_color_to_hsv_or_temp('baby pink'):", parse_color_to_hsv_or_temp("baby pink"))
print("parse_color_to_hsv_or_temp('sunset orange'):", parse_color_to_hsv_or_temp("sunset orange"))
print("parse_color_to_hsv_or_temp('warm white'):", parse_color_to_hsv_or_temp("warm white"))
print("parse_color_to_hsv_or_temp('cool white'):", parse_color_to_hsv_or_temp("cool white"))
