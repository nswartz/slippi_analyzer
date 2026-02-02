"""Ledgehog moment detector."""

from dataclasses import dataclass
from pathlib import Path

from src.detectors.base import FrameData
from src.models import TaggedMoment


class ActionState:
    """Melee action state constants (subset relevant for detection)."""

    WAIT = 14  # Standing
    CLIFF_WAIT = 253  # Holding ledge
    CLIFF_CATCH = 252  # Grabbing ledge
    FALL = 29  # Falling
    FALL_SPECIAL = 35  # Helpless fall (after recovery move or air dodge)
    ESCAPE_AIR = 236  # Air dodge

    # Damage states - opponent was hit
    DAMAGE_HI = 75  # Hit, knocked upward
    DAMAGE_N = 76  # Hit, knocked neutral
    DAMAGE_LW = 77  # Hit, knocked downward
    DAMAGE_FALL = 38  # Tumble falling
    DAMAGE_FLY_HI = 87  # Flying from hit upward
    DAMAGE_FLY_N = 88  # Flying from hit neutral
    DAMAGE_FLY_LW = 89  # Flying from hit downward
    DAMAGE_FLY_TOP = 90  # Flying from hit straight up
    DAMAGE_FLY_ROLL = 91  # Tumbling from hit


# Damage states that indicate opponent was hit (not a clean recovery)
DAMAGE_STATES = {
    ActionState.DAMAGE_HI,
    ActionState.DAMAGE_N,
    ActionState.DAMAGE_LW,
    ActionState.DAMAGE_FALL,
    ActionState.DAMAGE_FLY_HI,
    ActionState.DAMAGE_FLY_N,
    ActionState.DAMAGE_FLY_LW,
    ActionState.DAMAGE_FLY_TOP,
    ActionState.DAMAGE_FLY_ROLL,
}


# Stage edge x-coordinates (absolute value, edges are symmetric)
# These are approximate values for legal stages
STAGE_EDGES: dict[int, float] = {
    2: 63.35,   # Fountain of Dreams
    3: 56.0,    # Pokemon Stadium
    8: 68.4,    # Yoshi's Story
    28: 71.3,   # Dream Land
    31: 68.4,   # Battlefield
    32: 85.6,   # Final Destination
}


@dataclass
class LedgehogEvent:
    """Internal tracking for a potential ledgehog."""

    ledge_grab_frame: int
    player_left_ledge_frame: int | None = None
    opponent_reached_ledge_position: bool = False  # Did opponent get to ledge-grab position?
    opponent_was_hit: bool = False  # Was opponent hit during recovery? (makes it ledgeguard)


class LedgehogDetector:
    """Detects ledgehog moments in replays.

    A ledgehog is detected when:
    1. Player is on the ledge (CLIFF_CATCH or CLIFF_WAIT)
    2. Opponent reaches "ledge-grab position" (close to ledge, at/below ledge height)
    3. Opponent has a CLEAN recovery (not hit by attacks)
    4. Opponent subsequently loses a stock

    If opponent is hit during recovery, it's a ledgeguard, not a ledgehog.

    This captures the essence of a ledgehog - the player taking the ledge
    when the opponent needed it to recover.
    """

    FRAMES_BEFORE = 300  # 5 seconds at 60fps
    FRAMES_AFTER = 120   # 2 seconds at 60fps
    POST_LEDGE_WINDOW = 120  # Continue tracking for 2 seconds after player leaves ledge

    # Ledge-grab position thresholds
    LEDGE_GRAB_DISTANCE = 15.0  # Max horizontal distance from edge to grab ledge
    LEDGE_GRAB_MAX_HEIGHT = -15.0  # Must be at ledge height (below stage level)
    LEDGE_GRAB_MIN_HEIGHT = -45.0  # Not too far below (blast zone)

    @property
    def name(self) -> str:
        return "ledgehog"

    def detect(
        self, frames: list[FrameData], replay_path: Path
    ) -> list[TaggedMoment]:
        """Analyze frames and return detected ledgehog moments."""
        if not frames:
            return []

        moments: list[TaggedMoment] = []
        stage_id = frames[0].stage_id
        edge_x = STAGE_EDGES.get(stage_id, 70.0)  # Default if unknown stage

        # Track state across frames
        tracking_event: LedgehogEvent | None = None
        prev_opponent_stocks = frames[0].opponent_stocks if frames else 4

        for frame in frames:
            player_on_ledge = frame.player_action_state in (
                ActionState.CLIFF_WAIT,
                ActionState.CLIFF_CATCH,
            )
            opponent_offstage = abs(frame.opponent_x) > edge_x
            opponent_on_stage = (
                abs(frame.opponent_x) < edge_x and
                frame.opponent_y > -20  # Roughly above stage level
            )

            # Check if opponent is in "ledge-grab position"
            # This means they're close enough to the ledge to grab it
            # They must be at actual ledge height, not floating above the stage
            opponent_in_ledge_grab_position = (
                abs(frame.opponent_x) >= edge_x - 5 and  # At or past edge
                abs(frame.opponent_x) <= edge_x + self.LEDGE_GRAB_DISTANCE and
                frame.opponent_y <= self.LEDGE_GRAB_MAX_HEIGHT and  # At ledge height
                frame.opponent_y > self.LEDGE_GRAB_MIN_HEIGHT  # Not in blast zone
            )

            # Start tracking when player grabs ledge and opponent is offstage
            if player_on_ledge and opponent_offstage:
                if tracking_event is None:
                    tracking_event = LedgehogEvent(
                        ledge_grab_frame=frame.frame_number,
                        opponent_reached_ledge_position=opponent_in_ledge_grab_position,
                    )

            # Continue tracking
            if tracking_event is not None:
                # Track if opponent ever reaches ledge-grab position while player on ledge
                if player_on_ledge and opponent_in_ledge_grab_position:
                    tracking_event.opponent_reached_ledge_position = True

                # Track if opponent was hit during recovery (makes it a ledgeguard)
                if frame.opponent_action_state in DAMAGE_STATES:
                    tracking_event.opponent_was_hit = True

                # Note when player leaves ledge
                if not player_on_ledge and tracking_event.player_left_ledge_frame is None:
                    tracking_event.player_left_ledge_frame = frame.frame_number

                # Check for stock loss
                if frame.opponent_stocks < prev_opponent_stocks:
                    # Only count as ledgehog if:
                    # - Opponent reached ledge-grab position
                    # - Opponent was NOT hit (otherwise it's a ledgeguard)
                    if (tracking_event.opponent_reached_ledge_position and
                            not tracking_event.opponent_was_hit):
                        frame_start = max(
                            0, tracking_event.ledge_grab_frame - self.FRAMES_BEFORE
                        )
                        frame_end = min(
                            len(frames) - 1,
                            frame.frame_number + self.FRAMES_AFTER,
                        )

                        moments.append(
                            TaggedMoment(
                                replay_path=replay_path,
                                frame_start=frame_start,
                                frame_end=frame_end,
                                tags=["ledgehog"],
                                metadata={},
                            )
                        )
                    tracking_event = None

                # Cancel tracking if:
                # - Opponent lands safely on stage
                # - Too much time passed since player left ledge
                elif opponent_on_stage:
                    tracking_event = None
                elif (tracking_event.player_left_ledge_frame is not None and
                      frame.frame_number - tracking_event.player_left_ledge_frame > self.POST_LEDGE_WINDOW):
                    tracking_event = None

            prev_opponent_stocks = frame.opponent_stocks

        return moments
