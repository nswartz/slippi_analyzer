"""Tests for capture pipeline."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.capture.pipeline import CapturePipeline
from src.models import TaggedMoment


def test_pipeline_captures_single_moment(tmp_path: Path) -> None:
    """Pipeline captures a single moment through Dolphin and FFmpeg."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=2000,
        tags=["ledgehog:basic"],
        metadata={"date": "2025-01-15", "player": "sheik", "opponent": "fox", "stage": "battlefield"},
    )

    output_dir = tmp_path / "clips"

    with patch("src.capture.pipeline.DolphinController") as mock_dolphin, \
         patch("src.capture.pipeline.FFmpegEncoder") as mock_ffmpeg:

        # Setup mocks
        mock_dolphin_instance = MagicMock()
        mock_dolphin.return_value = mock_dolphin_instance
        mock_dolphin_instance.wait_for_completion.return_value = 0

        mock_ffmpeg_instance = MagicMock()
        mock_ffmpeg.return_value = mock_ffmpeg_instance

        pipeline = CapturePipeline(output_dir=output_dir)
        result = pipeline.capture_moment(moment, index=1)

        # Verify Dolphin was called
        mock_dolphin_instance.start_capture.assert_called_once()

        # Verify FFmpeg was called
        mock_ffmpeg_instance.encode.assert_called_once()

        # Should return output path
        assert result is not None
        assert result.suffix == ".mp4"


def test_pipeline_captures_multiple_moments(tmp_path: Path) -> None:
    """Pipeline captures multiple moments in sequence."""
    moments = [
        TaggedMoment(
            replay_path=Path(f"/replays/game{i}.slp"),
            frame_start=1000 + i * 1000,
            frame_end=2000 + i * 1000,
            tags=["ledgehog:basic"],
            metadata={"date": "2025-01-15", "player": "sheik", "opponent": "fox", "stage": "bf"},
        )
        for i in range(3)
    ]

    output_dir = tmp_path / "clips"

    with patch("src.capture.pipeline.DolphinController") as mock_dolphin, \
         patch("src.capture.pipeline.FFmpegEncoder") as mock_ffmpeg:

        mock_dolphin_instance = MagicMock()
        mock_dolphin.return_value = mock_dolphin_instance
        mock_dolphin_instance.wait_for_completion.return_value = 0

        mock_ffmpeg_instance = MagicMock()
        mock_ffmpeg.return_value = mock_ffmpeg_instance

        pipeline = CapturePipeline(output_dir=output_dir)
        results = pipeline.capture_moments(moments)

        # All 3 should be captured
        assert len(results) == 3
        assert mock_dolphin_instance.start_capture.call_count == 3


def test_pipeline_handles_dolphin_failure(tmp_path: Path) -> None:
    """Pipeline handles Dolphin failure gracefully."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=2000,
        tags=["ledgehog:basic"],
        metadata={},
    )

    output_dir = tmp_path / "clips"

    with patch("src.capture.pipeline.DolphinController") as mock_dolphin, \
         patch("src.capture.pipeline.FFmpegEncoder") as mock_ffmpeg:

        mock_dolphin_instance = MagicMock()
        mock_dolphin.return_value = mock_dolphin_instance
        # Simulate failure
        mock_dolphin_instance.wait_for_completion.return_value = 1

        mock_ffmpeg_instance = MagicMock()
        mock_ffmpeg.return_value = mock_ffmpeg_instance

        pipeline = CapturePipeline(output_dir=output_dir)
        result = pipeline.capture_moment(moment, index=1)

        # Should return None on failure
        assert result is None
        # FFmpeg should not be called if Dolphin fails
        mock_ffmpeg_instance.encode.assert_not_called()
