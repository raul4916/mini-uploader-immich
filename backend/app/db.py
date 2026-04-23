import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import settings


def init_db() -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS config ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get(key: str) -> str | None:
    with _conn() as c:
        row = c.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_(key: str, value: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO config(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def delete(key: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM config WHERE key = ?", (key,))
