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

    # Throw states (player throwing opponent) - indicates setup for edgeguard
    THROW_F = 0xC7  # 199 - Forward throw
    THROW_B = 0xC8  # 200 - Back throw
    THROW_HI = 0xC9  # 201 - Up throw
    THROW_LW = 0xCA  # 202 - Down throw

    # Recovery move states (opponent recovering) - for clutch detection
    # These are special fall states that indicate recovery move usage
    SPECIAL_FALL = 35  # After up-B or side-B that causes special fall
    # Character-specific up-B action states (approximate ranges)
    SPECIAL_HI = 0x161  # 353 - Generic up-B start


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

# Throw states - player throwing opponent (setup for edgeguard situation)
THROW_STATES = {
    ActionState.THROW_F,
    ActionState.THROW_B,
    ActionState.THROW_HI,
    ActionState.THROW_LW,
}

# States that indicate opponent is actively recovering (used up-B/side-B)
# Special fall means they used their recovery and are now helpless
RECOVERY_STATES = {
    ActionState.FALL_SPECIAL,  # Helpless fall after recovery move
}

# States where opponent CAN grab ledge (airborne and not in recovery/attack lag)
# For ledgehog detection, we require FALL_SPECIAL to ensure they actually used recovery
LEDGE_GRABABLE_STATES = {
    ActionState.FALL_SPECIAL,  # Helpless - most common ledgehog scenario
    ActionState.FALL,          # Regular falling (rare but possible)
}

# States that indicate player was hit (not intentional ledge grab)
PLAYER_HIT_STATES = {
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
    ledge_grab_frame_idx: int  # Index in frames list for technique classification
    player_left_ledge_frame: int | None = None
    opponent_reached_ledge_position: bool = False  # Did opponent get to ledge-grab position?
    opponent_reached_ledge_frame: int | None = None  # When did they reach it?
    opponent_was_hit: bool = False  # Was opponent hit during recovery? (makes it ledgeguard)
    opponent_in_recovery_state: bool = False  # Was opponent in special fall (used recovery)?
    throw_setup_frame: int | None = None  # Frame of throw that set up this edgeguard situation
    player_was_hit_into_ledge: bool = False  # Player got hit into grabbing ledge (lucky, not intentional)


class LedgehogDetector:
    """Detects ledgehog moments in replays.

    A ledgehog is detected when:
    1. Player is on the ledge (CLIFF_CATCH or CLIFF_WAIT)
    2. Opponent reaches "ledge-grab position" (close to ledge, at/below ledge height)
    3. Opponent has a CLEAN recovery (not hit by attacks)
    4. Opponent subsequently loses a stock
    5. The ledge grab timing was reactive (opponent reached ledge within 2 seconds)

    If opponent is hit during recovery, it's a ledgeguard, not a ledgehog.
    If opponent took too long to reach ledge after grab, it was preemptive (filtered out).

    Tags:
    - "ledgehog" - Standard ledgehog (opponent reached ledge within 2 sec)
    - "ledgehog:clutch" - Tight timing (within 1 second / 60 frames)
    - "ledgehog:clutch:30" - Within i-frame window (30 frames / 0.5 sec)
    - "ledgehog:clutch:15" - Super clutch (15 frames / 0.25 sec)
    - "ledgehog:clutch:10" - Insane timing (10 frames)
    - "ledgehog:clutch:5" - Frame-tight (5 frames)
    - "ledgehog:clutch:1" - Frame-perfect (1 frame or simultaneous)
    """

    FRAMES_BEFORE = 300  # 5 seconds at 60fps (default)
    FRAMES_BEFORE_WITH_SETUP = 480  # 8 seconds if there was a throw setup
    FRAMES_AFTER = 120   # 2 seconds at 60fps
    POST_LEDGE_WINDOW = 120  # Continue tracking for 2 seconds after player leaves ledge

    # Ledge-grab position thresholds
    # Tightened to only count when opponent is RIGHT at ledge-grab height
    # Sweetspotting characters (Fox, Falco, etc.) grab ledge around Y = -5 to -15
    # If they're lower, they're still in recovery animation and not actually "at" ledge
    LEDGE_GRAB_DISTANCE = 12.0  # Max horizontal distance from edge to grab ledge
    LEDGE_GRAB_MAX_HEIGHT = -5.0  # Upper bound - must be below stage level
    LEDGE_GRAB_MIN_HEIGHT = -20.0  # Lower bound - if lower, they're still recovering

    # Timing-based reaction quality thresholds (frames)
    # Max frames between ledge grab and opponent reaching ledge position
    MAX_REACTION_FRAMES = 120  # 2 seconds - beyond this, grab was too preemptive

    # Clutch timing tiers (frames) - each tier adds its tag
    CLUTCH_TIERS = [
        (60, "ledgehog:clutch"),      # 1 second - tight timing
        (30, "ledgehog:clutch:30"),   # 0.5 sec - within i-frame window
        (15, "ledgehog:clutch:15"),   # 0.25 sec - super clutch
        (10, "ledgehog:clutch:10"),   # insane timing
        (5, "ledgehog:clutch:5"),     # frame-tight
        (1, "ledgehog:clutch:1"),     # frame-perfect
    ]

    # How far back to look for a throw that set up the edgeguard
    THROW_LOOKBACK_FRAMES = 300  # 5 seconds

    @property
    def name(self) -> str:
        return "ledgehog"

    def _classify_ledge_technique(
        self,
        frames: list[FrameData],
        grab_frame_idx: int,
    ) -> str:
        """Classify the technique used to grab the ledge.

        Looks at player state before the grab to determine technique.

        Args:
            frames: List of all frame data
            grab_frame_idx: Index of the frame where ledge was grabbed

        Returns:
            Tag suffix: "recovery", "wavedash", "ramen", "jump", or "hit"
        """
        if grab_frame_idx < 5:
            return "jump"  # Not enough history, assume jump

        # Look at the 30 frames before grab
        lookback = min(30, grab_frame_idx)
        pre_grab_frames = frames[grab_frame_idx - lookback:grab_frame_idx]

        grab_frame = frames[grab_frame_idx]
        edge_x = STAGE_EDGES.get(grab_frame.stage_id, 68.4)
        player_side = 1 if grab_frame.player_x > 0 else -1  # 1=right edge, -1=left edge

        # Check if player was in FALL_SPECIAL before grab (recovery)
        was_in_fall_special = any(
            f.player_action_state == ActionState.FALL_SPECIAL for f in pre_grab_frames[-15:]
        )

        # Check if player was hit recently (damage states)
        was_hit = any(
            f.player_action_state in DAMAGE_STATES for f in pre_grab_frames[-30:]
        )

        # Check for airdodge (wavedash/ramen)
        had_airdodge = any(
            f.player_action_state == ActionState.ESCAPE_AIR for f in pre_grab_frames[-10:]
        )

        # Check player position history - were they on stage before?
        # Stage level is approximately y=0, so check y >= -5 (allows for slight variations)
        was_on_stage = any(
            abs(f.player_x) < edge_x - 10 and f.player_y >= -5
            for f in pre_grab_frames[-30:]
        )

        if was_hit:
            return "hit"
        elif was_in_fall_special and not was_on_stage:
            return "recovery"
        elif had_airdodge and was_on_stage:
            # Wavedash vs ramen: check facing relative to stage
            # Wavedash = facing toward the edge (away from center)
            # Ramen = facing toward center (requires turnaround)
            # player_side is 1 for right edge, -1 for left edge
            # player_facing is 1 for facing right, -1 for facing left
            # Facing edge means player_facing matches player_side
            facing_edge = (player_side * grab_frame.player_facing) > 0
            return "wavedash" if facing_edge else "ramen"
        else:
            return "jump"

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
        recent_throw_frame: int | None = None  # Track recent throws for clip extension
        player_hit_frame: int | None = None  # Track when player was last hit

        # How recently player must have been hit to count as "hit into ledge"
        HIT_INTO_LEDGE_WINDOW = 30  # 0.5 seconds

        for frame_idx, frame in enumerate(frames):
            player_on_ledge = frame.player_action_state in (
                ActionState.CLIFF_WAIT,
                ActionState.CLIFF_CATCH,
            )
            opponent_offstage = abs(frame.opponent_x) > edge_x
            opponent_on_stage = (
                abs(frame.opponent_x) < edge_x and
                frame.opponent_y > -20  # Roughly above stage level
            )

            # Track if player threw opponent (for "interesting neutral" detection)
            if frame.player_action_state in THROW_STATES:
                recent_throw_frame = frame.frame_number

            # Track if player was hit (for "hit into ledge" detection)
            if frame.player_action_state in PLAYER_HIT_STATES:
                player_hit_frame = frame.frame_number

            # Check if opponent is in "ledge-grab position"
            # This means they're close enough to the ledge to grab it AND
            # they're in a state where they could actually grab (not air-dodge, etc.)
            opponent_position_valid = (
                abs(frame.opponent_x) >= edge_x - 5 and  # At or past edge
                abs(frame.opponent_x) <= edge_x + self.LEDGE_GRAB_DISTANCE and
                frame.opponent_y <= self.LEDGE_GRAB_MAX_HEIGHT and  # At ledge height
                frame.opponent_y > self.LEDGE_GRAB_MIN_HEIGHT  # Not in blast zone
            )
            # Must also be in a state that can grab ledge (not air-dodge, attack, etc.)
            opponent_can_grab = frame.opponent_action_state in LEDGE_GRABABLE_STATES
            opponent_in_ledge_grab_position = opponent_position_valid and opponent_can_grab

            # Check if opponent is in recovery state (used their up-B/side-B)
            opponent_recovering = frame.opponent_action_state in RECOVERY_STATES

            # Start tracking when player grabs ledge and opponent is offstage
            if player_on_ledge and opponent_offstage:
                if tracking_event is None:
                    # Check if there was a recent throw that set this up
                    throw_setup = None
                    if (recent_throw_frame is not None and
                            frame.frame_number - recent_throw_frame <= self.THROW_LOOKBACK_FRAMES):
                        throw_setup = recent_throw_frame

                    # Check if player was hit into grabbing ledge (lucky, not intentional)
                    hit_into_ledge = (
                        player_hit_frame is not None and
                        frame.frame_number - player_hit_frame <= HIT_INTO_LEDGE_WINDOW
                    )

                    tracking_event = LedgehogEvent(
                        ledge_grab_frame=frame.frame_number,
                        ledge_grab_frame_idx=frame_idx,
                        opponent_reached_ledge_position=opponent_in_ledge_grab_position,
                        opponent_reached_ledge_frame=(
                            frame.frame_number if opponent_in_ledge_grab_position else None
                        ),
                        opponent_in_recovery_state=opponent_recovering,
                        throw_setup_frame=throw_setup,
                        player_was_hit_into_ledge=hit_into_ledge,
                    )

            # Continue tracking
            if tracking_event is not None:
                # Track if/when opponent reaches ledge-grab position while player on ledge
                if player_on_ledge and opponent_in_ledge_grab_position:
                    if not tracking_event.opponent_reached_ledge_position:
                        tracking_event.opponent_reached_ledge_position = True
                        tracking_event.opponent_reached_ledge_frame = frame.frame_number

                # Track if opponent is in recovery state
                if opponent_recovering:
                    tracking_event.opponent_in_recovery_state = True

                # Track if opponent was hit during recovery (makes it a ledgeguard)
                if frame.opponent_action_state in DAMAGE_STATES:
                    tracking_event.opponent_was_hit = True

                # Note when player leaves ledge
                if not player_on_ledge and tracking_event.player_left_ledge_frame is None:
                    tracking_event.player_left_ledge_frame = frame.frame_number

                # Check for stock loss
                if frame.opponent_stocks < prev_opponent_stocks:
                    # Only count as ledgehog if:
                    # - Opponent reached ledge-grab position (and was in grabable state)
                    # - Opponent was NOT hit (otherwise it's a ledgeguard)
                    # - Player was NOT hit into grabbing ledge (intentional, not lucky)
                    # - Timing was reactive (opponent reached ledge within MAX_REACTION_FRAMES)
                    is_valid_ledgehog = (
                        tracking_event.opponent_reached_ledge_position and
                        not tracking_event.opponent_was_hit and
                        not tracking_event.player_was_hit_into_ledge
                    )

                    # Timing check: opponent must reach ledge within reaction window
                    reaction_frames = 0
                    if is_valid_ledgehog and tracking_event.opponent_reached_ledge_frame is not None:
                        reaction_frames = (
                            tracking_event.opponent_reached_ledge_frame -
                            tracking_event.ledge_grab_frame
                        )
                        if reaction_frames > self.MAX_REACTION_FRAMES:
                            is_valid_ledgehog = False

                    if is_valid_ledgehog:
                        # Extend clip if there was a throw setup (interesting neutral)
                        frames_before = self.FRAMES_BEFORE
                        if tracking_event.throw_setup_frame is not None:
                            # Extend to include the throw
                            frames_before = max(
                                self.FRAMES_BEFORE_WITH_SETUP,
                                tracking_event.ledge_grab_frame - tracking_event.throw_setup_frame + 120
                            )

                        frame_start = max(0, tracking_event.ledge_grab_frame - frames_before)
                        frame_end = min(
                            len(frames) - 1,
                            frame.frame_number + self.FRAMES_AFTER,
                        )

                        # Determine tags based on timing quality
                        tags = ["ledgehog"]

                        # Add all applicable clutch tier tags
                        for threshold, tag in self.CLUTCH_TIERS:
                            if reaction_frames <= threshold:
                                tags.append(tag)

                        # Classify the technique used to grab ledge
                        technique = self._classify_ledge_technique(
                            frames, tracking_event.ledge_grab_frame_idx
                        )
                        tags.append(f"ledgehog:{technique}")

                        moments.append(
                            TaggedMoment(
                                replay_path=replay_path,
                                frame_start=frame_start,
                                frame_end=frame_end,
                                tags=tags,
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
