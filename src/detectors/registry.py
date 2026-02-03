"""Detector registry for managing and running moment detectors."""

from pathlib import Path

from src.detectors.base import Detector, FrameData
from src.models import TaggedMoment


class DetectorRegistry:
    """Registry for managing moment detectors."""

    def __init__(self) -> None:
        self._detectors: dict[str, Detector] = {}

    def register(self, detector: Detector) -> None:
        """Register a detector."""
        self._detectors[detector.name] = detector

    def get(self, name: str) -> Detector | None:
        """Get a detector by name."""
        return self._detectors.get(name)

    @property
    def detector_names(self) -> list[str]:
        """Get list of registered detector names."""
        return list(self._detectors.keys())

    def run_all(
        self, frames: list[FrameData], replay_path: Path
    ) -> list[TaggedMoment]:
        """Run all registered detectors on frames.

        Returns combined list of moments from all detectors.
        """
        all_moments: list[TaggedMoment] = []

        for detector in self._detectors.values():
            moments = detector.detect(frames, replay_path)
            all_moments.extend(moments)

        return all_moments

    @classmethod
    def with_default_detectors(cls) -> "DetectorRegistry":
        """Create registry with default detectors."""
        from src.detectors.ledgehog import LedgehogDetector

        registry = cls()
        registry.register(LedgehogDetector())
        return registry
