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


def test_strict_ledgehog_requires_fall_special() -> None:
    """Strict ledgehog requires opponent to enter FALL_SPECIAL (helpless) state."""
    detector = LedgehogDetector()
    stage_id = 2
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id))

    # Player on ledge, opponent offstage in FALL_SPECIAL (helpless from recovery)
    for i in range(100, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,
                opponent_y=-50.0,
                opponent_action=ActionState.FALL_SPECIAL,  # Helpless state
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:basic" in moments[0].tags
    assert "ledgehog:strict" in moments[0].tags


def test_no_strict_tag_without_fall_special() -> None:
    """No strict tag if opponent was never in FALL_SPECIAL (like Peach f-smash case)."""
    detector = LedgehogDetector()
    stage_id = 2
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id))

    # Player on ledge, opponent offstage but in DAMAGE_FLY (being launched, not recovering)
    for i in range(100, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,
                opponent_y=-50.0,
                opponent_action=ActionState.DAMAGE_FLY_HI,  # Being launched, not helpless
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:basic" in moments[0].tags
    assert "ledgehog:strict" not in moments[0].tags  # No strict - wasn't in helpless


def test_strict_ledgehog_on_stage_up_b() -> None:
    """Strict ledgehog when opponent uses Up-B on stage toward ledge."""
    detector = LedgehogDetector()
    stage_id = 2
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id))

    # Opponent on stage near edge, enters FALL_SPECIAL (from Up-B)
    # Player grabs ledge
    for i in range(100, 130):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x - 10.0,  # On stage, near edge
                opponent_y=20.0,
                opponent_action=ActionState.FALL_SPECIAL,  # Helpless from Up-B
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent falls offstage and dies
    for i in range(130, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,  # Now offstage
                opponent_y=-80.0,
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:strict" in moments[0].tags


def test_strict_ledgehog_from_air_dodge() -> None:
    """Strict ledgehog when opponent air dodges toward ledge."""
    detector = LedgehogDetector()
    stage_id = 2
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id))

    # Opponent offstage, air dodges (ESCAPE_AIR), then enters FALL_SPECIAL
    for i in range(100, 110):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 15.0,
                opponent_y=-30.0,
                opponent_action=ActionState.ESCAPE_AIR,  # Air dodge
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Air dodge ends, now in FALL_SPECIAL
    for i in range(110, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,
                opponent_y=-60.0,
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:strict" in moments[0].tags


def test_no_ledgehog_when_opponent_far_from_ledge() -> None:
    """No ledgehog if opponent never gets close to the ledge.

    Just dying offstage while player is on ledge isn't a ledgehog.
    The opponent must actually approach the ledge to be "hogged".
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge, opponent is FAR offstage (never approaches)
    # This simulates clip 5: "falco doesn't even come close to the ledge"
    for i in range(100, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 80.0,  # Very far from ledge
                opponent_y=-100.0,  # Deep offstage
                opponent_action=ActionState.FALL,  # Just falling, not recovering
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock at frame 150 (respawns at center stage)
    # Note: stock loss frame still has opponent far away (blast zone position)
    frames.append(
        make_frame(
            150,
            opponent_x=edge_x + 100.0,  # In blast zone when stock loss registered
            opponent_y=-200.0,
            opponent_stocks=3,  # Lost a stock
            stage_id=stage_id,
        )
    )

    # After stock loss, opponent respawns (neutral frames)
    for i in range(151, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    # Should NOT detect a ledgehog - opponent never approached
    assert len(moments) == 0


def test_no_ledgehog_when_opponent_survives() -> None:
    """No ledgehog if opponent successfully recovers.

    This tests the case from user feedback where "falco survives".
    Even if player was on ledge, if opponent lands back on stage,
    it's not a ledgehog.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge, opponent is offstage and approaching
    for i in range(100, 130):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,  # Close enough to be "approaching"
                opponent_y=-30.0,
                opponent_action=ActionState.FALL_SPECIAL,  # Recovering
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Player leaves ledge, opponent lands safely on stage
    for i in range(130, 200):
        frames.append(
            make_frame(
                i,
                player_x=0.0,
                player_action=ActionState.WAIT,  # Player no longer on ledge
                opponent_x=20.0,  # Back on stage
                opponent_y=0.0,
                opponent_action=ActionState.WAIT,  # Standing safely
                opponent_stocks=4,  # Still has all stocks
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    # Should NOT detect a ledgehog - opponent recovered
    assert len(moments) == 0
