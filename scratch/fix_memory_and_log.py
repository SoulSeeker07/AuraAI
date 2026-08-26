import sqlite3
import json
from pathlib import Path

# 1. Update Memory.db
conn = sqlite3.connect("Memory.db")
c = conn.cursor()
c.execute("DELETE FROM topics WHERE summary LIKE '%John%'")
c.execute("DELETE FROM facts WHERE value LIKE '%John%'")
c.execute("INSERT OR REPLACE INTO facts (id, category, key, value, created_at, updated_at) VALUES (1, 'person', 'name', 'Sreekanta', '2026-08-04T18:39:08', '2026-08-24T18:20:00')")
c.execute("INSERT OR REPLACE INTO facts (category, key, value, created_at, updated_at) VALUES ('profile', 'name', 'Sreekanta', '2026-08-24T18:20:00', '2026-08-24T18:20:00')")
conn.commit()
conn.close()

# 2. Clean ChatLog.json
chat_path = Path("Data/ChatLog.json")
if chat_path.exists():
    with open(chat_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cleaned = [d for d in data if "John" not in d.get("content", "")]
    with open(chat_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)

print("Memory.db and ChatLog.json cleaned successfully.")
