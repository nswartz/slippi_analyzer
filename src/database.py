"""SQLite database for storing detected moments."""

import sqlite3
from pathlib import Path


class MomentDatabase:
    """SQLite database for moments and replay metadata."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS replays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                mtime REAL NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS moments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                replay_id INTEGER NOT NULL,
                frame_start INTEGER NOT NULL,
                frame_end INTEGER NOT NULL,
                metadata TEXT,
                FOREIGN KEY (replay_id) REFERENCES replays(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moment_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (moment_id) REFERENCES moments(id)
            )
        """)

        conn.commit()
        conn.close()
