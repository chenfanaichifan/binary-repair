#!/usr/bin/env python3
"""Apply numbered SQL migrations to SQLite, atomically and idempotently.

Rules:
  * files are ``NNN_name.sql`` and are applied in numeric order
  * an applied migration is never edited; changing the schema means a new file
  * each file runs inside one transaction with its schema_migrations row
  * the process is safe to run on every start

Usage:
    python db/migrate.py --db var/app.db
    python db/migrate.py --db var/app.db --dry-run
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

MIGRATION_RE = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")
DEFAULT_DIR = Path(__file__).resolve().parent / "migrations"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with the pragmas this schema relies on."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if str(db_path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def discover(directory: str | Path = DEFAULT_DIR) -> list[tuple[int, str, Path]]:
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"migrations directory not found: {directory}")

    found: list[tuple[int, str, Path]] = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        if not match:
            raise ValueError(f"migration name must be NNN_name.sql: {path.name}")
        found.append((int(match.group(1)), match.group(2), path))

    versions = [v for v, _, _ in found]
    if len(set(versions)) != len(versions):
        raise ValueError("duplicate migration versions")
    return found


def _ensure_registry(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " applied_at TEXT NOT NULL)"
    )
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    _ensure_registry(conn)
    return {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}


def apply_migrations(
    conn: sqlite3.Connection,
    directory: str | Path = DEFAULT_DIR,
    *,
    dry_run: bool = False,
) -> list[int]:
    """Apply pending migrations. Returns the versions applied (or that would be)."""
    applied = applied_versions(conn)
    pending = [(v, name, path) for v, name, path in discover(directory) if v not in applied]
    if dry_run:
        return [v for v, _, _ in pending]

    done: list[int] = []
    for version, name, path in pending:
        sql = path.read_text(encoding="utf-8")
        # executescript commits any pending transaction first, so the BEGIN and
        # the bookkeeping row are part of the script itself.
        script = (
            "BEGIN IMMEDIATE;\n"
            f"{sql}\n"
            "INSERT INTO schema_migrations(version, name, applied_at) VALUES "
            f"({version}, '{name}', '{utc_now()}');\n"
            "COMMIT;\n"
        )
        try:
            conn.executescript(script)
        except sqlite3.Error:
            conn.rollback()
            raise
        done.append(version)
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="var/app.db", help="database path or :memory:")
    ap.add_argument("--migrations", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.db != ":memory:":
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)

    conn = connect(args.db)
    try:
        pending = apply_migrations(conn, args.migrations, dry_run=args.dry_run)
        if args.dry_run:
            print("pending: " + (", ".join(map(str, pending)) or "none"))
        else:
            print("applied: " + (", ".join(map(str, pending)) or "none (already up to date)"))
        print(f"schema version: {max(applied_versions(conn), default=0)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
