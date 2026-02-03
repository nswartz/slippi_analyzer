"""Sidecar metadata files for video clips."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models import TaggedMoment


def generate_sidecar_metadata(moment: TaggedMoment) -> dict[str, Any]:
    """Generate metadata dictionary for a clip sidecar file.

    Args:
        moment: The TaggedMoment to generate metadata for

    Returns:
        Dictionary with clip metadata
    """
    return {
        "replay": moment.replay_path.name,
        "replay_path": str(moment.replay_path),
        "frame_start": moment.frame_start,
        "frame_end": moment.frame_end,
        "duration_seconds": moment.duration_seconds,
        "tags": moment.tags,
        "player": moment.metadata.get("player", ""),
        "opponent": moment.metadata.get("opponent", ""),
        "stage": moment.metadata.get("stage", ""),
        "date": moment.metadata.get("date", ""),
        "created": datetime.now(timezone.utc).isoformat(),
    }


def write_sidecar_file(video_path: Path, moment: TaggedMoment) -> Path:
    """Write a sidecar JSON file alongside a video clip.

    Args:
        video_path: Path to the video file
        moment: The TaggedMoment with metadata

    Returns:
        Path to the created sidecar file
    """
    sidecar_path = video_path.with_suffix(video_path.suffix + ".json")
    metadata = generate_sidecar_metadata(moment)

    with open(sidecar_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return sidecar_path
