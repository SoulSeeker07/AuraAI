from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "database" / "app.db"
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    return DB_PATH
