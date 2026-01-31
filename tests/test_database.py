"""Tests for SQLite database operations."""

import sqlite3
from pathlib import Path

from src.database import MomentDatabase
from src.models import TaggedMoment


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


def test_database_store_moment(tmp_db_path: Path) -> None:
    """Can store a TaggedMoment in the database."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "player:sheik"],
        metadata={"opponent": "fox", "stage": "battlefield"},
    )

    moment_id = db.store_moment(moment, mtime=1234567890.0)
    assert moment_id > 0


def test_database_retrieve_moments_by_tag(tmp_db_path: Path) -> None:
    """Can retrieve moments by tag."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    moment1 = TaggedMoment(
        replay_path=Path("/replays/game1.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic"],
        metadata={},
    )
    moment2 = TaggedMoment(
        replay_path=Path("/replays/game2.slp"),
        frame_start=2000,
        frame_end=2500,
        tags=["ledgehog:strict"],
        metadata={},
    )

    db.store_moment(moment1, mtime=1234567890.0)
    db.store_moment(moment2, mtime=1234567891.0)

    basic_moments = db.find_moments_by_tag("ledgehog:basic")
    assert len(basic_moments) == 1
    assert basic_moments[0].frame_start == 1000

    strict_moments = db.find_moments_by_tag("ledgehog:strict")
    assert len(strict_moments) == 1
    assert strict_moments[0].frame_start == 2000


def test_database_check_replay_needs_scan(tmp_db_path: Path) -> None:
    """Can check if replay needs scanning based on mtime."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    replay_path = Path("/replays/game.slp")

    # Not in database yet - needs scan
    assert db.needs_scan(replay_path, current_mtime=1000.0) is True

    # Store a moment for this replay
    moment = TaggedMoment(
        replay_path=replay_path,
        frame_start=100,
        frame_end=200,
        tags=["test"],
        metadata={},
    )
    db.store_moment(moment, mtime=1000.0)

    # Same mtime - no scan needed
    assert db.needs_scan(replay_path, current_mtime=1000.0) is False

    # Newer mtime - needs scan
    assert db.needs_scan(replay_path, current_mtime=2000.0) is True
