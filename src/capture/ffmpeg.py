"""FFmpeg wrapper for encoding video clips."""

import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from enum import Enum
from pathlib import Path


class VideoEncoder(Enum):
    """Available video encoders for FFmpeg."""

    SOFTWARE = "software"  # libopenh264 (CPU)
    NVENC = "nvenc"        # NVIDIA GPU encoder
    VAAPI = "vaapi"        # AMD/Intel GPU encoder (Linux)


def build_avi_encode_command(
    video_file: Path,
    audio_file: Path | None,
    output_file: Path,
    encoder: VideoEncoder = VideoEncoder.SOFTWARE,
) -> list[str]:
    """Build ffmpeg command for encoding AVI+WAV to MP4.

    Args:
        video_file: Path to input AVI video file (from Dolphin frame dump)
        audio_file: Optional path to WAV audio file (from Dolphin audio dump)
        output_file: Path for output MP4 video
        encoder: Video encoder to use (SOFTWARE, NVENC, or VAAPI)

    Returns:
        Command as list of strings
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
    ]

    # VAAPI requires hardware device initialization before input
    if encoder == VideoEncoder.VAAPI:
        cmd.extend(["-vaapi_device", "/dev/dri/renderD128"])

    cmd.extend(["-i", str(video_file)])

    if audio_file is not None:
        cmd.extend(["-i", str(audio_file)])

    # Video encoding settings based on encoder type
    if encoder == VideoEncoder.NVENC:
        # NVIDIA GPU encoding with constant quality
        cmd.extend([
            "-c:v", "h264_nvenc",
            "-pix_fmt", "yuv420p",
            "-cq", "23",  # Constant quality (similar to CRF)
            "-preset", "p4",  # Balance of speed and quality
        ])
    elif encoder == VideoEncoder.VAAPI:
        # AMD/Intel GPU encoding via VAAPI
        cmd.extend([
            "-vf", "format=nv12,hwupload",
            "-c:v", "h264_vaapi",
            "-qp", "23",  # Quality parameter
        ])
    else:
        # Software encoding (default)
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

    def __init__(
        self,
        max_workers: int = 2,
        encoder: VideoEncoder = VideoEncoder.SOFTWARE,
    ) -> None:
        """Initialize the encoder.

        Args:
            max_workers: Maximum number of concurrent encoding threads.
                         Defaults to 2.
            encoder: Video encoder to use (SOFTWARE, NVENC, or VAAPI).
                     Defaults to SOFTWARE.
        """
        self._max_workers = max_workers
        self._encoder = encoder

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
            encoder=self._encoder,
        )

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    _executor: ThreadPoolExecutor | None = None

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor for async encoding."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
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
