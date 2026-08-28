import sqlite3

conn = sqlite3.connect("./aura_memory_db/chroma.sqlite3")
cur = conn.cursor()
tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in chroma.sqlite3:")
for t in tables:
    count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  - {t}: {count} rows")

print("\n--- Collections ---")
for col in cur.execute("SELECT * FROM collections").fetchall():
    print(col)

print("\n--- Embeddings ---")
for emb in cur.execute("SELECT * FROM embeddings").fetchall():
    print(emb[:4])

print("\n--- Embedding Metadata ---")
for meta in cur.execute("SELECT * FROM embedding_metadata").fetchall():
    print(meta)
