"""Tests for replay scanner."""

from pathlib import Path

import pytest

from src.detectors.base import FrameData
from src.scanner import ReplayScanner, parse_replay_to_frames


def test_parse_replay_returns_frame_data_list() -> None:
    """parse_replay_to_frames returns list of FrameData for each opponent."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    # This is a doubles match (4 players), so we get frames for each opponent
    # When player_port=0 (Sheik), opponents are ports 2 and 3 (Fox and Peach)
    result = parse_replay_to_frames(replay_path, player_port=0)

    # Should return a dict mapping opponent port to frame list
    assert isinstance(result, dict)
    # In doubles, Sheik (port 0) has 2 opponents (ports 2, 3)
    assert len(result) >= 1  # At least one opponent

    # Each opponent's frames should be a list of FrameData
    for opponent_port, frames in result.items():
        assert isinstance(frames, list)
        assert len(frames) > 0
        assert isinstance(frames[0], FrameData)


def test_frame_data_has_correct_stage_id() -> None:
    """FrameData should have correct stage ID from replay."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    result = parse_replay_to_frames(replay_path, player_port=0)
    # Get frames for any opponent
    frames = next(iter(result.values()))

    # Stage 31 = Battlefield
    assert frames[0].stage_id == 31


def test_frame_data_tracks_positions() -> None:
    """FrameData should track player and opponent positions."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    result = parse_replay_to_frames(replay_path, player_port=0)
    frames = next(iter(result.values()))

    # Positions should be floats
    assert isinstance(frames[0].player_x, float)
    assert isinstance(frames[0].player_y, float)
    assert isinstance(frames[0].opponent_x, float)
    assert isinstance(frames[0].opponent_y, float)


def test_frame_data_tracks_stocks() -> None:
    """FrameData should track player and opponent stocks."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    result = parse_replay_to_frames(replay_path, player_port=0)
    frames = next(iter(result.values()))

    # Game starts with 4 stocks each
    assert frames[0].player_stocks == 4
    assert frames[0].opponent_stocks == 4


def test_replay_scanner_extracts_metadata() -> None:
    """ReplayScanner extracts metadata from replay."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    scanner = ReplayScanner()
    metadata = scanner.get_metadata(replay_path)

    assert "date" in metadata
    assert "stage" in metadata
    assert "player" in metadata  # Character name


def test_replay_scanner_identifies_teammates_vs_opponents() -> None:
    """ReplayScanner correctly identifies teammates vs opponents in doubles."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    scanner = ReplayScanner()
    # Port 0 = Sheik, Port 1 = Marth (teammate), Ports 2,3 = opponents (Fox, Peach)
    opponents = scanner.get_opponent_ports(replay_path, player_port=0)

    # In doubles, should identify port 2 and 3 as opponents
    # Port 0 and 1 are on the same team
    assert 0 not in opponents  # Self is not an opponent
    assert 1 not in opponents  # Teammate is not an opponent
    assert 2 in opponents or 3 in opponents  # At least one opponent identified
