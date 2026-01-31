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
    DAMAGE_FALL = 38  # Tumble
    FALL = 29  # Falling
    FALL_SPECIAL = 35  # Helpless fall


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
    opponent_offstage_frame: int
    initiating_hit_frame: int | None = None


class LedgehogDetector:
    """Detects ledgehog moments in replays."""

    FRAMES_BEFORE = 300  # 5 seconds at 60fps
    FRAMES_AFTER = 120   # 2 seconds at 60fps

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

            # Start tracking when player grabs ledge and opponent is offstage
            if player_on_ledge and opponent_offstage and tracking_event is None:
                tracking_event = LedgehogEvent(
                    ledge_grab_frame=frame.frame_number,
                    opponent_offstage_frame=frame.frame_number,
                )

            # Check for stock loss while tracking
            if tracking_event is not None:
                if frame.opponent_stocks < prev_opponent_stocks:
                    # Ledgehog confirmed!
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
                            tags=["ledgehog:basic"],
                            metadata={},
                        )
                    )
                    tracking_event = None

                # Cancel tracking if player leaves ledge without opponent dying
                elif not player_on_ledge:
                    tracking_event = None

            prev_opponent_stocks = frame.opponent_stocks

        return moments
