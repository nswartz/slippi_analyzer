"""Clip compilation using FFmpeg."""

import os
import subprocess
import tempfile
from pathlib import Path


def build_concat_command(
    clips: list[Path],
    output: Path,
    list_file: Path | None = None,
) -> list[str]:
    """Build ffmpeg command to concatenate clips.

    Args:
        clips: List of clip paths to concatenate
        output: Output file path
        list_file: Optional path for the concat list file

    Returns:
        Command as list of strings
    """
    # Create list file for ffmpeg concat
    if list_file is None:
        fd, tmp_name = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        list_file = Path(tmp_name)

    with open(list_file, "w") as f:
        for clip in clips:
            # FFmpeg concat format requires 'file' prefix
            f.write(f"file '{clip.absolute()}'\n")

    return [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output),
    ]


def compile_clips(
    clips: list[Path],
    output: Path,
) -> None:
    """Compile multiple clips into a single video.

    Args:
        clips: List of clip paths to concatenate
        output: Output file path

    Raises:
        RuntimeError: If ffmpeg fails
    """
    if not clips:
        raise ValueError("No clips to compile")

    # Create temp list file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for clip in clips:
            f.write(f"file '{clip.absolute()}'\n")
        list_file = Path(f.name)

    try:
        cmd = build_concat_command(clips, output, list_file=list_file)
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    finally:
        list_file.unlink(missing_ok=True)
