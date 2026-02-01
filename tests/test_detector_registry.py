"""Tests for detector registry and integration."""

from pathlib import Path

from src.detectors.base import FrameData
from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment


class MockDetector:
    """A mock detector for testing."""

    def __init__(self, name: str = "mock", moments_to_return: list[TaggedMoment] | None = None) -> None:
        self._name = name
        self._moments = moments_to_return or []
        self.detect_called_with: list[FrameData] | None = None

    @property
    def name(self) -> str:
        return self._name

    def detect(self, frames: list[FrameData], replay_path: Path) -> list[TaggedMoment]:
        self.detect_called_with = frames
        return self._moments


def test_registry_register_detector() -> None:
    """Registry can register detectors."""
    registry = DetectorRegistry()
    detector = MockDetector("test")

    registry.register(detector)

    assert "test" in registry.detector_names


def test_registry_get_detector() -> None:
    """Registry can retrieve registered detector by name."""
    registry = DetectorRegistry()
    detector = MockDetector("test")
    registry.register(detector)

    retrieved = registry.get("test")

    assert retrieved is detector


def test_registry_run_all_detectors() -> None:
    """Registry runs all registered detectors on frames."""
    registry = DetectorRegistry()

    # Create mock detectors that return moments
    moment1 = TaggedMoment(
        replay_path=Path("/test.slp"),
        frame_start=100,
        frame_end=200,
        tags=["detector1:tag"],
        metadata={},
    )
    moment2 = TaggedMoment(
        replay_path=Path("/test.slp"),
        frame_start=300,
        frame_end=400,
        tags=["detector2:tag"],
        metadata={},
    )

    detector1 = MockDetector("detector1", [moment1])
    detector2 = MockDetector("detector2", [moment2])

    registry.register(detector1)
    registry.register(detector2)

    frames = [
        FrameData(
            frame_number=i,
            player_x=0.0,
            player_y=0.0,
            player_action_state=0,
            player_stocks=4,
            opponent_x=0.0,
            opponent_y=0.0,
            opponent_action_state=0,
            opponent_stocks=4,
            stage_id=31,
        )
        for i in range(10)
    ]

    moments = registry.run_all(frames, Path("/test.slp"))

    # Both detectors should have been called
    assert detector1.detect_called_with == frames
    assert detector2.detect_called_with == frames

    # Should return moments from both detectors
    assert len(moments) == 2
    assert moment1 in moments
    assert moment2 in moments


def test_registry_default_detectors() -> None:
    """Default registry includes ledgehog detector."""
    registry = DetectorRegistry.with_default_detectors()

    assert "ledgehog" in registry.detector_names
