"""Tests for filename generation."""

from pathlib import Path

from src.models import TaggedMoment, generate_clip_filename


def test_generate_clip_filename_basic() -> None:
    """Generate descriptive filename from moment metadata."""
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
    assert filename == "2025-01-15_sheik_vs-fox_battlefield_ledgehog-strict_001.mp4"


def test_generate_clip_filename_multiple_tags() -> None:
    """Use most specific ledgehog tag in filename."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "ledgehog:strict", "ledgehog:intentional"],
        metadata={
            "date": "2025-01-15",
            "player": "sheik",
            "opponent": "marth",
            "stage": "yoshis",
        },
    )

    filename = generate_clip_filename(moment, index=5)
    # Should use intentional (most specific)
    assert filename == "2025-01-15_sheik_vs-marth_yoshis_ledgehog-intentional_005.mp4"


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
    assert filename == "unknown_unknown_vs-unknown_unknown_ledgehog-basic_001.mp4"
