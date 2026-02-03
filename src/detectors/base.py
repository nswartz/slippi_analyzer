"""Base protocol for moment detectors."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.models import TaggedMoment


@dataclass
class FrameData:
    """Game state for a single frame."""

    frame_number: int

    # Player (user) state
    player_x: float
    player_y: float
    player_action_state: int
    player_stocks: int
    player_facing: int  # 1 = right, -1 = left

    # Opponent state
    opponent_x: float
    opponent_y: float
    opponent_action_state: int
    opponent_stocks: int
    opponent_facing: int  # 1 = right, -1 = left

    # Stage
    stage_id: int


class Detector(Protocol):
    """Protocol for moment detectors."""

    @property
    def name(self) -> str:
        """Unique identifier for this detector."""
        ...

    def detect(
        self, frames: list[FrameData], replay_path: Path
    ) -> list[TaggedMoment]:
        """Analyze frames and return detected moments."""
        ...
