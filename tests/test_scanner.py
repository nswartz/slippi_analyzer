"""Tests for replay scanner."""

from pathlib import Path

import pytest

from src.detectors.base import FrameData
from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment
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
    for _, frames in result.items():
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
    metadata = scanner.get_metadata(replay_path, player_port=0)

    assert "date" in metadata
    assert "stage" in metadata
    assert "player" in metadata  # Character name
    assert metadata["player"] == "sheik"  # Port 0 is Sheik in fixture


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


def test_replay_scanner_scan_replay_runs_detectors(tmp_path: Path) -> None:
    """ReplayScanner.scan_replay runs detectors and returns moments."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    scanner = ReplayScanner()
    registry = DetectorRegistry.with_default_detectors()

    # Scan the replay
    moments = scanner.scan_replay(
        replay_path=replay_path,
        player_port=0,
        registry=registry,
    )

    # Should return a list of moments (may be empty if no ledgehogs in this replay)
    assert isinstance(moments, list)
    for moment in moments:
        assert isinstance(moment, TaggedMoment)


def test_replay_scanner_scan_replay_adds_metadata(tmp_path: Path) -> None:
    """ReplayScanner.scan_replay adds replay metadata to moments."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    # Create a mock detector that always returns a moment
    class AlwaysDetectMock:
        @property
        def name(self) -> str:
            return "always"

        def detect(
            self, frames: list[FrameData], replay_path: Path
        ) -> list[TaggedMoment]:
            if frames:
                return [
                    TaggedMoment(
                        replay_path=replay_path,
                        frame_start=0,
                        frame_end=100,
                        tags=["test:always"],
                        metadata={},
                    )
                ]
            return []

    scanner = ReplayScanner()
    registry = DetectorRegistry()
    registry.register(AlwaysDetectMock())

    moments = scanner.scan_replay(
        replay_path=replay_path,
        player_port=0,
        registry=registry,
    )

    # Should have moments with metadata filled in
    assert len(moments) >= 1
    moment = moments[0]
    assert "date" in moment.metadata
    assert "stage" in moment.metadata
    assert "player" in moment.metadata
    assert "opponent" in moment.metadata


def test_normalize_connect_code_handles_dash() -> None:
    """normalize_connect_code converts dash format to hash format."""
    from src.scanner import normalize_connect_code

    assert normalize_connect_code("PDL-637") == "PDL#637"
    assert normalize_connect_code("PIE-381") == "PIE#381"


def test_normalize_connect_code_handles_hash() -> None:
    """normalize_connect_code leaves hash format unchanged."""
    from src.scanner import normalize_connect_code

    assert normalize_connect_code("PDL#637") == "PDL#637"
    assert normalize_connect_code("PIE#381") == "PIE#381"


def test_normalize_connect_code_case_insensitive() -> None:
    """normalize_connect_code normalizes to uppercase."""
    from src.scanner import normalize_connect_code

    assert normalize_connect_code("pdl-637") == "PDL#637"
    assert normalize_connect_code("PDL-637") == "PDL#637"


def test_find_player_port_by_code() -> None:
    """find_player_port_by_code finds correct port for connect code."""
    from src.scanner import find_player_port_by_code

    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    # Port 0 = PDL#637 (PhoenixDarkLord)
    assert find_player_port_by_code(replay_path, "PDL#637") == 0
    assert find_player_port_by_code(replay_path, "PDL-637") == 0  # Dash format
    assert find_player_port_by_code(replay_path, "pdl-637") == 0  # Case insensitive

    # Port 1 = ADMI#105
    assert find_player_port_by_code(replay_path, "ADMI#105") == 1

    # Port 2 = JEEF#676
    assert find_player_port_by_code(replay_path, "JEEF#676") == 2

    # Port 3 = HAMM#587
    assert find_player_port_by_code(replay_path, "HAMM#587") == 3


def test_find_player_port_by_code_returns_none_for_unknown() -> None:
    """find_player_port_by_code returns None for unknown code."""
    from src.scanner import find_player_port_by_code

    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    assert find_player_port_by_code(replay_path, "UNKNOWN#999") is None


def test_find_player_port_by_codes_list() -> None:
    """find_player_port_by_codes finds first matching code from list."""
    from src.scanner import find_player_port_by_codes

    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    # User has PDL-637 and PIE-381, but only PDL-637 is in this replay
    assert find_player_port_by_codes(replay_path, ["PDL-637", "PIE-381"]) == 0

    # Test with codes in opposite order
    assert find_player_port_by_codes(replay_path, ["PIE-381", "PDL-637"]) == 0

    # Test when no codes match
    assert find_player_port_by_codes(replay_path, ["UNKNOWN#999"]) is None


def test_scan_replays_parallel_faster_than_sequential() -> None:
    """Parallel scanning should be faster for multiple replays."""
    import time
    from unittest.mock import patch

    scanner = ReplayScanner()

    # Mock slow replay scanning (100ms each)
    def slow_scan(
        path: Path, player_port: int, registry: DetectorRegistry
    ) -> list[TaggedMoment]:
        time.sleep(0.1)
        return []

    with patch.object(scanner, "scan_replay", side_effect=slow_scan):
        paths = [Path(f"/fake/replay_{i}.slp") for i in range(10)]
        registry = DetectorRegistry()

        # Sequential would take 10 * 0.1 = 1 second
        # Parallel with 4 workers should take ~0.3 seconds
        start = time.time()
        results = scanner.scan_replays_parallel(
            paths, player_port=0, registry=registry, max_workers=4
        )
        elapsed = time.time() - start

        assert elapsed < 0.5  # Should be much faster than 1 second
        assert len(results) == 10  # Should have 10 result lists (one per replay)
