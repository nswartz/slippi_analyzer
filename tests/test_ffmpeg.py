"""Tests for ffmpeg wrapper."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.capture.ffmpeg import FFmpegEncoder, build_encode_command


def test_build_encode_command() -> None:
    """Build correct ffmpeg command for encoding frames to video."""
    cmd = build_encode_command(
        frame_pattern=Path("/tmp/frames/frame_%05d.png"),
        audio_file=Path("/tmp/audio.wav"),
        output_file=Path("/output/clip.mp4"),
        fps=60,
    )

    assert "ffmpeg" in cmd[0]
    assert "-framerate" in cmd
    assert "60" in cmd
    assert "-i" in cmd
    assert str(Path("/tmp/frames/frame_%05d.png")) in cmd
    assert str(Path("/output/clip.mp4")) in cmd


def test_build_encode_command_no_audio() -> None:
    """Build ffmpeg command without audio."""
    cmd = build_encode_command(
        frame_pattern=Path("/tmp/frames/frame_%05d.png"),
        audio_file=None,
        output_file=Path("/output/clip.mp4"),
        fps=60,
    )

    assert "-i" in cmd
    # Should only have one -i (for video), not two
    assert cmd.count("-i") == 1


def test_ffmpeg_encoder_encode(tmp_path: Path) -> None:
    """FFmpegEncoder calls subprocess with correct command."""
    encoder = FFmpegEncoder()

    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()

    # Create dummy frame files
    for i in range(10):
        (frame_dir / f"frame_{i:05d}.png").touch()

    output_file = tmp_path / "output.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        encoder.encode(
            frame_dir=frame_dir,
            output_file=output_file,
            fps=60,
        )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args[0]
