"""Tests for ledgehog detector."""

from pathlib import Path

from src.detectors.base import FrameData
from src.detectors.ledgehog import LedgehogDetector, ActionState, STAGE_EDGES


def make_frame(
    frame_number: int,
    player_x: float = 0.0,
    player_y: float = 0.0,
    player_action: int = 0,
    player_stocks: int = 4,
    opponent_x: float = 0.0,
    opponent_y: float = 0.0,
    opponent_action: int = 0,
    opponent_stocks: int = 4,
    stage_id: int = 2,  # Fountain of Dreams
) -> FrameData:
    """Helper to create FrameData for tests."""
    return FrameData(
        frame_number=frame_number,
        player_x=player_x,
        player_y=player_y,
        player_action_state=player_action,
        player_stocks=player_stocks,
        opponent_x=opponent_x,
        opponent_y=opponent_y,
        opponent_action_state=opponent_action,
        opponent_stocks=opponent_stocks,
        stage_id=stage_id,
    )


def test_ledgehog_detector_name() -> None:
    """Detector has correct name."""
    detector = LedgehogDetector()
    assert detector.name == "ledgehog"


def test_no_detection_when_not_on_ledge() -> None:
    """No ledgehog detected when player is not on ledge."""
    detector = LedgehogDetector()
    frames = [
        make_frame(i, player_action=ActionState.WAIT)
        for i in range(100)
    ]

    moments = detector.detect(frames, Path("/test.slp"))
    assert len(moments) == 0


def test_basic_ledgehog_detection() -> None:
    """Detect basic ledgehog: player on ledge, opponent offstage, opponent dies."""
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames (frames 0-99), opponent has 4 stocks
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge, opponent is offstage with 4 stocks (frames 100-149)
    for i in range(100, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,  # Past the edge
                opponent_y=-50.0,
                opponent_stocks=4,  # Still has 4 stocks while offstage
                stage_id=stage_id,
            )
        )

    # Opponent loses stock at frame 150 (goes to 3 stocks)
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                player_x=0.0,
                player_action=ActionState.WAIT,
                opponent_stocks=3,  # Lost a stock
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:basic" in moments[0].tags
    # Moment should start 5 seconds (300 frames) before the ledgehog,
    # but clamped to frame 0 since the ledgehog is at frame 100
    assert moments[0].frame_start >= 0
    # Moment should end after the stock loss
    assert moments[0].frame_end >= 150
