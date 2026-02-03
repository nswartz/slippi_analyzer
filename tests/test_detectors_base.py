"""Tests for detector base protocol."""

from pathlib import Path

from src.detectors.base import FrameData
from src.models import TaggedMoment


def test_frame_data_structure() -> None:
    """FrameData contains player positions and states."""
    frame = FrameData(
        frame_number=100,
        player_x=0.0,
        player_y=0.0,
        player_action_state=0,
        player_stocks=4,
        player_facing=1,
        opponent_x=-50.0,
        opponent_y=-100.0,
        opponent_action_state=185,  # Example: Fall
        opponent_stocks=3,
        opponent_facing=-1,
        stage_id=2,  # Fountain of Dreams
    )

    assert frame.frame_number == 100
    assert frame.opponent_stocks == 3
    assert frame.player_facing == 1
    assert frame.opponent_facing == -1


def test_detector_protocol_compliance() -> None:
    """Detector protocol requires name and detect methods."""

    class MockDetector:
        @property
        def name(self) -> str:
            return "mock"

        def detect(
            self, frames: list[FrameData], replay_path: Path
        ) -> list[TaggedMoment]:
            return []

    detector = MockDetector()
    # This should pass type checking - protocol compliance
    assert detector.name == "mock"
    assert detector.detect([], Path("/test.slp")) == []
