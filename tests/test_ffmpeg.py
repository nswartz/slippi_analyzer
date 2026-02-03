"""Tests for ffmpeg wrapper."""

from concurrent.futures import Future
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.capture.ffmpeg import FFmpegEncoder, build_avi_encode_command


def test_build_avi_encode_command() -> None:
    """Build ffmpeg command for encoding AVI+WAV to MP4."""
    cmd = build_avi_encode_command(
        video_file=Path("/tmp/framedump0.avi"),
        audio_file=Path("/tmp/dspdump.wav"),
        output_file=Path("/output/clip.mp4"),
    )

    assert "ffmpeg" in cmd[0]
    assert "-i" in cmd
    assert str(Path("/tmp/framedump0.avi")) in cmd
    assert str(Path("/tmp/dspdump.wav")) in cmd
    assert "-c:v" in cmd
    assert "libopenh264" in cmd
    assert "-c:a" in cmd
    assert "aac" in cmd
    assert str(Path("/output/clip.mp4")) in cmd


def test_build_avi_encode_command_no_audio() -> None:
    """Build ffmpeg command for encoding AVI to MP4 without audio."""
    cmd = build_avi_encode_command(
        video_file=Path("/tmp/framedump0.avi"),
        audio_file=None,
        output_file=Path("/output/clip.mp4"),
    )

    # Should only have one -i (for video)
    assert cmd.count("-i") == 1
    assert "-c:a" not in cmd


def test_ffmpeg_encoder_encode_avi(tmp_path: Path) -> None:
    """FFmpegEncoder.encode_avi calls subprocess with correct command."""
    encoder = FFmpegEncoder()

    video_file = tmp_path / "framedump0.avi"
    audio_file = tmp_path / "dspdump.wav"
    video_file.touch()
    audio_file.touch()

    output_file = tmp_path / "output.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        encoder.encode_avi(
            video_file=video_file,
            audio_file=audio_file,
            output_file=output_file,
        )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args[0]
        assert str(video_file) in call_args
        assert str(audio_file) in call_args


def test_encode_avi_async_returns_future(tmp_path: Path) -> None:
    """encode_avi_async returns a Future that completes when encoding finishes."""
    encoder = FFmpegEncoder()

    video_file = tmp_path / "framedump0.avi"
    audio_file = tmp_path / "dspdump.wav"
    output_file = tmp_path / "output.mp4"
    video_file.write_bytes(b"dummy video")
    audio_file.write_bytes(b"dummy audio")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        future = encoder.encode_avi_async(
            video_file=video_file,
            output_file=output_file,
            audio_file=audio_file,
        )

        assert isinstance(future, Future)
        future.result(timeout=5)
        mock_run.assert_called_once()


def test_encode_avi_async_raises_on_failure(tmp_path: Path) -> None:
    """encode_avi_async Future raises RuntimeError if ffmpeg fails."""
    encoder = FFmpegEncoder()

    video_file = tmp_path / "framedump0.avi"
    output_file = tmp_path / "output.mp4"
    video_file.write_bytes(b"dummy video")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="encode error")

        future = encoder.encode_avi_async(
            video_file=video_file,
            output_file=output_file,
        )

        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            future.result(timeout=5)
