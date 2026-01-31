"""Tests for SQLite database operations."""

import sqlite3
from pathlib import Path

from src.database import MomentDatabase


def test_database_creates_tables(tmp_db_path: Path) -> None:
    """Database initializes with required tables."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    # Verify tables exist
    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "moments" in tables
    assert "tags" in tables
    assert "replays" in tables


def test_database_replays_table_schema(tmp_db_path: Path) -> None:
    """Replays table stores path and mtime for incremental scanning."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute("PRAGMA table_info(replays)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert "id" in columns
    assert "path" in columns
    assert "mtime" in columns
