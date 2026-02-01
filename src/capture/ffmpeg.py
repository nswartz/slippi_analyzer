"""FFmpeg wrapper for encoding video clips."""

import subprocess
from pathlib import Path


def build_encode_command(
    frame_pattern: Path,
    audio_file: Path | None,
    output_file: Path,
    fps: int = 60,
) -> list[str]:
    """Build ffmpeg command for encoding frames to video.

    Args:
        frame_pattern: Path pattern for input frames (e.g., /tmp/frame_%05d.png)
        audio_file: Optional path to audio file
        output_file: Path for output video
        fps: Frames per second

    Returns:
        Command as list of strings
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-framerate", str(fps),
        "-i", str(frame_pattern),
    ]

    if audio_file is not None:
        cmd.extend(["-i", str(audio_file)])
        cmd.extend(["-c:a", "aac"])

    cmd.extend([
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        str(output_file),
    ])

    return cmd


class FFmpegEncoder:
    """Encodes frame sequences to video files."""

    def encode(
        self,
        frame_dir: Path,
        output_file: Path,
        fps: int = 60,
        audio_file: Path | None = None,
    ) -> None:
        """Encode frames in directory to video file.

        Args:
            frame_dir: Directory containing numbered frame images
            output_file: Output video path
            fps: Frames per second
            audio_file: Optional audio file to mux
        """
        # Find frame pattern
        frames = sorted(frame_dir.glob("frame_*.png"))
        if not frames:
            raise ValueError(f"No frames found in {frame_dir}")

        # Determine pattern (assumes frame_00000.png format)
        frame_pattern = frame_dir / "frame_%05d.png"

        cmd = build_encode_command(
            frame_pattern=frame_pattern,
            audio_file=audio_file,
            output_file=output_file,
            fps=fps,
        )

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
