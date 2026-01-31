"""Tests for core data models."""

from pathlib import Path
from src.models import TaggedMoment


def test_tagged_moment_creation() -> None:
    """TaggedMoment stores replay path, frame range, tags, and metadata."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "player:sheik"],
        metadata={"opponent": "fox", "stage": "battlefield"},
    )

    assert moment.replay_path == Path("/replays/game.slp")
    assert moment.frame_start == 1000
    assert moment.frame_end == 1500
    assert "ledgehog:basic" in moment.tags
    assert moment.metadata["opponent"] == "fox"


def test_tagged_moment_frame_count() -> None:
    """TaggedMoment can calculate frame count."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=[],
        metadata={},
    )

    assert moment.frame_count == 500


def test_tagged_moment_duration_seconds() -> None:
    """TaggedMoment can calculate duration in seconds (60fps)."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=0,
        frame_end=600,  # 10 seconds at 60fps
        tags=[],
        metadata={},
    )

    assert moment.duration_seconds == 10.0
