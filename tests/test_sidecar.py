"""Tests for sidecar metadata files."""

import json
from pathlib import Path

from src.models import TaggedMoment
from src.sidecar import generate_sidecar_metadata, write_sidecar_file


def test_generate_sidecar_metadata() -> None:
    """Generate sidecar metadata from TaggedMoment."""
    moment = TaggedMoment(
        replay_path=Path("/replays/Game_20251114T001152.slp"),
        frame_start=4500,
        frame_end=4800,
        tags=["ledgehog:basic", "ledgehog:strict"],
        metadata={
            "date": "20251114",
            "player": "FOXY",
            "opponent": "fox",
            "stage": "battlefield",
        },
    )

    meta = generate_sidecar_metadata(moment)

    assert meta["replay"] == "Game_20251114T001152.slp"
    assert meta["frame_start"] == 4500
    assert meta["frame_end"] == 4800
    assert meta["tags"] == ["ledgehog:basic", "ledgehog:strict"]
    assert meta["player"] == "FOXY"
    assert meta["opponent"] == "fox"
    assert meta["stage"] == "battlefield"


def test_generate_sidecar_metadata_includes_duration() -> None:
    """Sidecar metadata includes duration in seconds."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=0,
        frame_end=300,  # 5 seconds at 60fps
        tags=["ledgehog:basic"],
        metadata={},
    )

    meta = generate_sidecar_metadata(moment)

    assert meta["duration_seconds"] == 5.0


def test_write_sidecar_file(tmp_path: Path) -> None:
    """Write sidecar JSON file alongside video."""
    video_path = tmp_path / "clip_001.mp4"
    video_path.touch()

    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=100,
        frame_end=200,
        tags=["ledgehog:basic"],
        metadata={"opponent": "marth"},
    )

    sidecar_path = write_sidecar_file(video_path, moment)

    assert sidecar_path == tmp_path / "clip_001.mp4.json"
    assert sidecar_path.exists()

    # Verify content
    content = json.loads(sidecar_path.read_text())
    assert content["replay"] == "game.slp"
    assert content["tags"] == ["ledgehog:basic"]
    assert content["opponent"] == "marth"


def test_sidecar_file_is_valid_json(tmp_path: Path) -> None:
    """Sidecar file is valid, parseable JSON."""
    video_path = tmp_path / "test.mp4"
    video_path.touch()

    moment = TaggedMoment(
        replay_path=Path("/path/to/replay.slp"),
        frame_start=0,
        frame_end=60,
        tags=["tag1", "tag2"],
        metadata={"key": "value"},
    )

    sidecar_path = write_sidecar_file(video_path, moment)

    # Should not raise
    with open(sidecar_path) as f:
        data = json.load(f)

    assert isinstance(data, dict)
    assert "tags" in data
    assert "replay" in data
