"""Tests for filename generation."""

from pathlib import Path

from src.models import TaggedMoment, generate_clip_filename


def test_generate_clip_filename_basic() -> None:
    """Generate descriptive filename from moment metadata (no tags in filename)."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:strict"],
        metadata={
            "date": "2025-01-15",
            "player": "sheik",
            "opponent": "fox",
            "stage": "battlefield",
        },
    )

    filename = generate_clip_filename(moment, index=1)
    # Tags are stored in sidecar JSON, not filename
    assert filename == "001_sheik_vs-fox_battlefield.mp4"


def test_generate_clip_filename_preserves_index() -> None:
    """Index is zero-padded in filename."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "ledgehog:strict"],
        metadata={
            "player": "sheik",
            "opponent": "marth",
            "stage": "yoshis",
        },
    )

    filename = generate_clip_filename(moment, index=42)
    assert filename == "042_sheik_vs-marth_yoshis.mp4"


def test_generate_clip_filename_missing_metadata() -> None:
    """Handle missing metadata gracefully."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic"],
        metadata={},
    )

    filename = generate_clip_filename(moment, index=1)
    assert filename == "001_unknown_vs-unknown_unknown.mp4"
