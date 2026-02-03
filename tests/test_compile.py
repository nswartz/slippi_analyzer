"""Tests for clip compilation."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.capture.compile import build_concat_command, compile_clips


def test_build_concat_command() -> None:
    """Build correct ffmpeg concat command."""
    clips = [
        Path("/clips/clip1.mp4"),
        Path("/clips/clip2.mp4"),
        Path("/clips/clip3.mp4"),
    ]
    output = Path("/output/final.mp4")

    cmd = build_concat_command(clips, output)

    assert "ffmpeg" in cmd[0]
    assert "-f" in cmd
    assert "concat" in cmd
    # Output file should be in command
    assert str(output) in cmd


def test_build_concat_command_creates_list_file(tmp_path: Path) -> None:
    """Concat command creates a list file for ffmpeg."""
    clips = [
        tmp_path / "clip1.mp4",
        tmp_path / "clip2.mp4",
    ]
    # Create dummy files
    for clip in clips:
        clip.touch()

    output = tmp_path / "final.mp4"

    cmd = build_concat_command(clips, output, list_file=tmp_path / "list.txt")

    list_file = tmp_path / "list.txt"
    assert list_file.exists()

    content = list_file.read_text()
    assert "clip1.mp4" in content
    assert "clip2.mp4" in content


def test_compile_clips_calls_ffmpeg(tmp_path: Path) -> None:
    """compile_clips calls ffmpeg with concat command."""
    clips = [
        tmp_path / "clip1.mp4",
        tmp_path / "clip2.mp4",
    ]
    for clip in clips:
        clip.touch()

    output = tmp_path / "final.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        compile_clips(clips, output)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args[0]
