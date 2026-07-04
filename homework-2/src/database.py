import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "tickets.db"

DDL = """
CREATE TABLE IF NOT EXISTS tickets (
    id           TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_name  TEXT NOT NULL,
    subject      TEXT NOT NULL,
    description  TEXT NOT NULL,
    category     TEXT,
    priority     TEXT NOT NULL DEFAULT 'medium',
    status       TEXT NOT NULL DEFAULT 'new',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    resolved_at  TEXT,
    assigned_to  TEXT,
    tags         TEXT NOT NULL DEFAULT '[]',
    metadata     TEXT,
    classification_confidence REAL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(DDL)
        # Migrate existing DBs that predate the classification_confidence column
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()}
        if "classification_confidence" not in columns:
            conn.execute("ALTER TABLE tickets ADD COLUMN classification_confidence REAL")


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else None
    return d
