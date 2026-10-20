"""SQLite connection helper for the minimal job store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(data_dir: str | Path) -> sqlite3.Connection:
    """Open ``<data_dir>/app.db`` and ensure the minimal schema exists."""

    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(directory / "app.db"))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection
