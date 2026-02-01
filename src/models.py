"""Core data models for slippi-clip."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaggedMoment:
    """A detected moment in a Slippi replay with associated tags."""

    replay_path: Path
    frame_start: int
    frame_end: int
    tags: list[str] = field(default_factory=lambda: [])
    metadata: dict[str, str] = field(default_factory=lambda: {})

    @property
    def frame_count(self) -> int:
        """Number of frames in this moment."""
        return self.frame_end - self.frame_start

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds (assuming 60fps)."""
        return self.frame_count / 60.0


def generate_clip_filename(moment: TaggedMoment, index: int) -> str:
    """Generate a descriptive filename for a clip.

    Format: {index:03d}_{player}_vs-{opponent}_{stage}.mp4

    Tags are stored in sidecar JSON files, not in the filename.
    """
    player = moment.metadata.get("player", "unknown")
    opponent = moment.metadata.get("opponent", "unknown")
    stage = moment.metadata.get("stage", "unknown")

    return f"{index:03d}_{player}_vs-{opponent}_{stage}.mp4"
