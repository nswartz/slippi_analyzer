"""FFmpeg wrapper for encoding video clips."""

import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path


def build_avi_encode_command(
    video_file: Path,
    audio_file: Path | None,
    output_file: Path,
) -> list[str]:
    """Build ffmpeg command for encoding AVI+WAV to MP4.

    Args:
        video_file: Path to input AVI video file (from Dolphin frame dump)
        audio_file: Optional path to WAV audio file (from Dolphin audio dump)
        output_file: Path for output MP4 video

    Returns:
        Command as list of strings
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i", str(video_file),
    ]

    if audio_file is not None:
        cmd.extend(["-i", str(audio_file)])

    # Video encoding settings
    # Use libopenh264 (available on Fedora) instead of libx264
    # libopenh264 doesn't support CRF, so use bitrate instead
    # 8 Mbps is good for 1080p 60fps game footage
    cmd.extend([
        "-c:v", "libopenh264",
        "-pix_fmt", "yuv420p",
        "-b:v", "8M",
    ])

    # Audio encoding settings (if audio provided)
    if audio_file is not None:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.append(str(output_file))

    return cmd


class FFmpegEncoder:
    """Encodes AVI video files to MP4."""

    def encode_avi(
        self,
        video_file: Path,
        output_file: Path,
        audio_file: Path | None = None,
    ) -> None:
        """Encode AVI video (with optional WAV audio) to MP4.

        Args:
            video_file: Path to AVI video file from Dolphin frame dump
            output_file: Output MP4 path
            audio_file: Optional WAV audio file from Dolphin audio dump
        """
        cmd = build_avi_encode_command(
            video_file=video_file,
            audio_file=audio_file,
            output_file=output_file,
        )

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    _executor: ThreadPoolExecutor | None = None

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor for async encoding."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=2)
        return self._executor

    def encode_avi_async(
        self,
        video_file: Path,
        output_file: Path,
        audio_file: Path | None = None,
    ) -> "Future[None]":
        """Encode AVI video to MP4 asynchronously.

        Returns immediately with a Future that completes when encoding finishes.

        Args:
            video_file: Path to AVI video file from Dolphin frame dump
            output_file: Output MP4 path
            audio_file: Optional WAV audio file from Dolphin audio dump

        Returns:
            Future that completes when encoding finishes
        """
        def _encode() -> None:
            self.encode_avi(
                video_file=video_file,
                output_file=output_file,
                audio_file=audio_file,
            )

        return self._get_executor().submit(_encode)
