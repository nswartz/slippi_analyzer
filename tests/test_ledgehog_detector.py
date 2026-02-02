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


def test_ledgehog_detected_when_opponent_near_at_grab() -> None:
    """Ledgehog detected: player grabs ledge while opponent is near ledge-grab position.

    This is the "clutch" timing - grabbing the ledge right as the opponent
    is about to grab it themselves.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames (frames 0-99)
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge (CLIFF_CATCH) while opponent is CLOSE to ledge
    # This is the critical moment - opponent is in position to grab ledge
    frames.append(
        make_frame(
            100,
            player_x=edge_x,
            player_y=-10.0,
            player_action=ActionState.CLIFF_CATCH,  # Moment of grabbing
            opponent_x=edge_x + 10.0,  # Close to ledge (within grab range)
            opponent_y=-15.0,  # At ledge height
            opponent_action=ActionState.FALL_SPECIAL,
            opponent_stocks=4,
            stage_id=stage_id,
        )
    )

    # Player holds ledge (CLIFF_WAIT), opponent falls away
    for i in range(101, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,
                opponent_y=-50.0 - (i - 100),  # Falling
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
    assert "ledgehog" in moments[0].tags
    assert moments[0].frame_start >= 0
    assert moments[0].frame_end >= 150


def test_no_ledgehog_when_opponent_never_reaches_ledge_grab_position() -> None:
    """No ledgehog if opponent never reaches ledge-grab position.

    Opponent gets somewhat close but never actually reaches a position
    where they could grab the ledge (too far horizontally or wrong height).
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge
    frames.append(
        make_frame(
            100,
            player_x=edge_x,
            player_y=-10.0,
            player_action=ActionState.CLIFF_CATCH,
            opponent_x=edge_x + 50.0,  # Far from ledge
            opponent_y=-80.0,
            opponent_stocks=4,
            stage_id=stage_id,
        )
    )

    # Player holds ledge, opponent approaches but stays too far/high
    # They're "close-ish" but never in actual ledge-grab position
    for i in range(101, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 25.0,  # Close but not in grab range (>15)
                opponent_y=10.0,  # Above stage level (not at ledge height)
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock (fell past the ledge without reaching grab position)
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_x=edge_x + 100.0,
                opponent_y=-200.0,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    # Should NOT detect - opponent never reached ledge-grab position
    assert len(moments) == 0


def test_no_ledgehog_when_opponent_survives() -> None:
    """No ledgehog if opponent successfully recovers.

    Even with clutch timing, if the opponent doesn't die, it's not a ledgehog.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge while opponent is close
    frames.append(
        make_frame(
            100,
            player_x=edge_x,
            player_y=-10.0,
            player_action=ActionState.CLIFF_CATCH,
            opponent_x=edge_x + 10.0,
            opponent_y=-15.0,
            opponent_action=ActionState.FALL_SPECIAL,
            opponent_stocks=4,
            stage_id=stage_id,
        )
    )

    # Player leaves ledge, opponent lands safely on stage
    for i in range(101, 200):
        frames.append(
            make_frame(
                i,
                player_x=0.0,
                player_action=ActionState.WAIT,
                opponent_x=20.0,  # Back on stage
                opponent_y=0.0,
                opponent_action=ActionState.WAIT,
                opponent_stocks=4,  # Still has all stocks
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    # Should NOT detect - opponent recovered
    assert len(moments) == 0


def test_no_ledgehog_when_opponent_never_approaches() -> None:
    """No ledgehog if opponent never gets close to the ledge at all.

    Just dying offstage while player is on ledge isn't a ledgehog.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge, opponent is FAR offstage
    for i in range(100, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 80.0,  # Very far
                opponent_y=-100.0,
                opponent_action=ActionState.FALL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent dies far from ledge
    frames.append(
        make_frame(
            150,
            opponent_x=edge_x + 100.0,
            opponent_y=-200.0,
            opponent_stocks=3,
            stage_id=stage_id,
        )
    )

    for i in range(151, 200):
        frames.append(make_frame(i, opponent_stocks=3, stage_id=stage_id))

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 0


def test_ledgehog_with_cliff_wait_start() -> None:
    """Ledgehog detected when player already on ledge and opponent approaches.

    Sometimes the player is already holding the ledge (CLIFF_WAIT) when
    the opponent gets close. This should still count if the opponent
    reaches ledge-grab position and then dies.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Player already on ledge, opponent approaching from far
    for i in range(100):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 50.0 - (i * 0.4),  # Approaching
                opponent_y=-30.0,
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent reaches ledge-grab position while player on ledge
    for i in range(100, 130):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 10.0,  # Now close to ledge
                opponent_y=-15.0,  # At ledge height
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent falls and dies
    for i in range(130, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 30.0,
                opponent_y=-100.0 - (i - 130) * 5,
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
    assert "ledgehog" in moments[0].tags


def test_ledgehog_opponent_below_ledge() -> None:
    """Ledgehog detected when opponent is below ledge level.

    The opponent doesn't have to be exactly at ledge height - being
    below it (recovering upward) should also count.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge, opponent is below but close horizontally
    frames.append(
        make_frame(
            100,
            player_x=edge_x,
            player_y=-10.0,
            player_action=ActionState.CLIFF_CATCH,
            opponent_x=edge_x + 8.0,  # Close horizontally
            opponent_y=-40.0,  # Below ledge, recovering upward
            opponent_action=ActionState.FALL_SPECIAL,
            opponent_stocks=4,
            stage_id=stage_id,
        )
    )

    for i in range(101, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,
                opponent_y=-80.0 - (i - 100),
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent dies
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
    assert "ledgehog" in moments[0].tags


def test_ledgehog_when_opponent_reaches_position_later() -> None:
    """Ledgehog detected even if opponent reaches ledge-grab position after grab.

    If the player is already on the ledge and the opponent later reaches
    ledge-grab position (trying to grab but can't), that's still a ledgehog.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge, opponent is still far
    frames.append(
        make_frame(
            100,
            player_x=edge_x,
            player_y=-10.0,
            player_action=ActionState.CLIFF_CATCH,
            opponent_x=edge_x + 50.0,  # Far when player grabs
            opponent_y=-80.0,
            opponent_stocks=4,
            stage_id=stage_id,
        )
    )

    # Opponent approaches and reaches ledge-grab position
    for i in range(101, 130):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 10.0,  # Now in grab range
                opponent_y=-15.0,  # At ledge height
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent falls and dies
    for i in range(130, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 30.0,
                opponent_y=-100.0 - (i - 130) * 5,
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

    # IS a ledgehog - opponent reached grab position while player on ledge
    assert len(moments) == 1
    assert "ledgehog" in moments[0].tags


def test_no_ledgehog_when_opponent_too_high() -> None:
    """No ledgehog if opponent is close horizontally but too high.

    This tests the Falco case: opponent is near the edge horizontally,
    but they're above the ledge and wouldn't have grabbed it anyway.
    They need to be at actual ledge height (below stage level) to count.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge
    frames.append(
        make_frame(
            100,
            player_x=edge_x,
            player_y=-10.0,
            player_action=ActionState.CLIFF_CATCH,
            opponent_x=edge_x + 10.0,  # Close horizontally
            opponent_y=-5.0,  # But too HIGH - above ledge grab range
            opponent_action=ActionState.FALL_SPECIAL,
            opponent_stocks=4,
            stage_id=stage_id,
        )
    )

    # Opponent stays too high and falls past
    for i in range(101, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 15.0,
                opponent_y=-8.0,  # Still too high
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent dies
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    # Should NOT detect - opponent was too high to grab ledge
    assert len(moments) == 0


def test_no_ledgehog_when_opponent_was_hit() -> None:
    """No ledgehog if opponent was hit during recovery (ledgeguard, not ledgehog).

    This tests the case where opponent gets hit by a projectile (needle)
    or attack while recovering. That's an edgeguard/ledgeguard, not a
    ledgehog. A true ledgehog requires a CLEAN recovery attempt denied
    by the player holding the ledge.
    """
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id, opponent_stocks=4))

    # Player grabs ledge
    frames.append(
        make_frame(
            100,
            player_x=edge_x,
            player_y=-10.0,
            player_action=ActionState.CLIFF_CATCH,
            opponent_x=edge_x + 20.0,
            opponent_y=-20.0,
            opponent_action=ActionState.FALL_SPECIAL,  # Recovering
            opponent_stocks=4,
            stage_id=stage_id,
        )
    )

    # Opponent reaches ledge position but gets HIT (e.g., by needle)
    for i in range(101, 110):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 10.0,  # Close to ledge
                opponent_y=-20.0,  # At ledge height
                opponent_action=ActionState.DAMAGE_FLY_HI,  # GOT HIT!
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent tumbles and dies
    for i in range(110, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 30.0,
                opponent_y=-100.0 - (i - 110) * 3,
                opponent_action=ActionState.DAMAGE_FALL,  # Tumbling
                opponent_stocks=4,
                stage_id=stage_id,
            )
        )

    # Opponent dies
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    # Should NOT detect - opponent was hit, this is a ledgeguard
    assert len(moments) == 0
