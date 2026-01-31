"""Core data models for slippi-clip."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaggedMoment:
    """A detected moment in a Slippi replay with associated tags."""

    replay_path: Path
    frame_start: int
    frame_end: int
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

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

    Format: {date}_vs-{opponent}_{stage}_{primary_tag}_{index:03d}.mp4
    """
    # Get metadata with defaults
    date_str = moment.metadata.get("date", "unknown")
    opponent = moment.metadata.get("opponent", "unknown")
    stage = moment.metadata.get("stage", "unknown")

    # Find the most specific ledgehog tag
    tag_priority = ["ledgehog:intentional", "ledgehog:strict", "ledgehog:basic"]
    primary_tag = "unknown"
    for tag in tag_priority:
        if tag in moment.tags:
            primary_tag = tag.replace(":", "-")
            break

    return f"{date_str}_vs-{opponent}_{stage}_{primary_tag}_{index:03d}.mp4"
