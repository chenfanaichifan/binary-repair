"""SQLite connection helper: bootstrap + member-5 migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db.migrate import apply_migrations, connect as _connect


def connect(data_dir: str | Path) -> sqlite3.Connection:
    """Open ``<data_dir>/app.db`` and apply all pending migrations."""

    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    connection = _connect(directory / "app.db")
    apply_migrations(connection)
    return connection
