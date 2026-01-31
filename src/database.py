"""SQLite database for storing detected moments."""

import json
import sqlite3
from pathlib import Path

from src.models import TaggedMoment


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

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def store_moment(self, moment: TaggedMoment, mtime: float) -> int:
        """Store a moment in the database. Returns the moment ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Insert or update replay record
        cursor.execute(
            "INSERT OR REPLACE INTO replays (path, mtime) VALUES (?, ?)",
            (str(moment.replay_path), mtime),
        )
        replay_id = cursor.execute(
            "SELECT id FROM replays WHERE path = ?",
            (str(moment.replay_path),),
        ).fetchone()[0]

        # Insert moment
        cursor.execute(
            """INSERT INTO moments (replay_id, frame_start, frame_end, metadata)
               VALUES (?, ?, ?, ?)""",
            (replay_id, moment.frame_start, moment.frame_end, json.dumps(moment.metadata)),
        )
        moment_id: int = cursor.lastrowid  # type: ignore[assignment]

        # Insert tags
        for tag in moment.tags:
            cursor.execute(
                "INSERT INTO tags (moment_id, tag) VALUES (?, ?)",
                (moment_id, tag),
            )

        conn.commit()
        return moment_id

    def find_moments_by_tag(self, tag: str) -> list[TaggedMoment]:
        """Find all moments with a specific tag."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT r.path, m.frame_start, m.frame_end, m.metadata, m.id
            FROM moments m
            JOIN replays r ON m.replay_id = r.id
            JOIN tags t ON t.moment_id = m.id
            WHERE t.tag = ?
            """,
            (tag,),
        )

        moments: list[TaggedMoment] = []
        for row in cursor.fetchall():
            path, frame_start, frame_end, metadata_json, moment_id = row

            # Get all tags for this moment
            tag_cursor = conn.execute(
                "SELECT tag FROM tags WHERE moment_id = ?",
                (moment_id,),
            )
            tags = [r[0] for r in tag_cursor.fetchall()]

            moments.append(
                TaggedMoment(
                    replay_path=Path(path),
                    frame_start=frame_start,
                    frame_end=frame_end,
                    tags=tags,
                    metadata=json.loads(metadata_json) if metadata_json else {},
                )
            )

        return moments

    def needs_scan(self, replay_path: Path, current_mtime: float) -> bool:
        """Check if a replay needs to be scanned."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT mtime FROM replays WHERE path = ?",
            (str(replay_path),),
        )
        row = cursor.fetchone()

        if row is None:
            return True  # Not in database

        stored_mtime: float = row[0]
        return current_mtime > stored_mtime
