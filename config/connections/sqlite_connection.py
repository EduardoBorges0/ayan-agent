import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from load_env import AYAN_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS memory_summary (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class SQLiteConnect:
    @staticmethod
    @contextmanager
    def connect() -> Iterator[sqlite3.Connection]:
        AYAN_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(AYAN_DB_PATH, timeout=5)
        try:
            connection.executescript(_SCHEMA)
            yield connection
            connection.commit()
        finally:
            connection.close()
