import re

text = "Current task: fixing bug"
words = text.split()
topic = " ".join(words[:3])
print(f"Topic: {topic}")

# Normalize key
key = topic.lower()
key = re.sub(r"[^\w\s-]", "", key)
key = re.sub(r"\s+", "_", key)
key = key.strip("_")[:50]
print(f"Normalized key: {key}")
