"""Tests for capture pipeline."""

from concurrent.futures import Future
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

        # Verify FFmpeg was called to encode AVI to MP4
        mock_ffmpeg_instance.encode_avi.assert_called_once()

        # Should return output path
        assert result is not None
        assert result.suffix == ".mp4"


def test_pipeline_captures_multiple_moments(tmp_path: Path) -> None:
    """Pipeline captures multiple moments with fresh Dolphin per clip (batch mode)."""
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
        # Should launch fresh Dolphin for each clip (batch mode required for frame dumping)
        assert mock_dolphin_instance.start_capture.call_count == 3
        # No reload - persistent mode doesn't dump frames
        assert mock_dolphin_instance.reload_replay.call_count == 0


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
        mock_ffmpeg_instance.encode_avi.assert_not_called()


def test_capture_moment_gets_active_window_before_start_capture(tmp_path: Path) -> None:
    """Active window should be captured right before Dolphin starts.

    This ensures focus restoration works correctly for batch captures:
    we capture the active window immediately before each capture starts,
    not when DolphinController is first created.
    """
    from src.capture.dolphin import DolphinController, DolphinConfig
    from src.capture.ffmpeg import FFmpegEncoder

    call_order: list[str] = []
    captured_restore_window: list[str | None] = []

    def mock_get_active_window(self: DolphinController) -> str:
        call_order.append("get_active_window")
        return "12345"

    def mock_start_capture(
        self: DolphinController,
        replay_path: Path,
        output_dir: Path,
        start_frame: int | None = None,
        end_frame: int | None = None,
        restore_window: str | None = None,
    ) -> None:
        call_order.append("start_capture")
        captured_restore_window.append(restore_window)

    with patch.object(DolphinController, "get_active_window", mock_get_active_window):
        with patch.object(DolphinController, "start_capture", mock_start_capture):
            with patch.object(DolphinController, "wait_for_completion", return_value=0):
                with patch.object(FFmpegEncoder, "encode_avi"):
                    with patch("src.capture.pipeline.write_sidecar_file"):
                        output_dir = tmp_path / "clips"
                        pipeline = CapturePipeline(
                            output_dir=output_dir,
                            dolphin_config=DolphinConfig(),
                        )

                        moment = TaggedMoment(
                            replay_path=Path("/tmp/test.slp"),
                            frame_start=100,
                            frame_end=200,
                            tags=["test"],
                            metadata={"date": "2025-01-01", "stage": "battlefield", "player": "sheik"},
                        )

                        pipeline.capture_moment(moment, index=1)

    # Verify get_active_window was called before start_capture
    assert "get_active_window" in call_order, "get_active_window must be called"
    assert "start_capture" in call_order, "start_capture must be called"
    gaw_idx = call_order.index("get_active_window")
    sc_idx = call_order.index("start_capture")
    assert gaw_idx < sc_idx, "get_active_window must be called before start_capture"

    # Verify the captured window ID was passed to start_capture
    assert len(captured_restore_window) == 1
    assert captured_restore_window[0] == "12345", "Active window ID must be passed to start_capture"


def test_capture_moments_launches_fresh_dolphin_per_clip(tmp_path: Path) -> None:
    """Batch capture launches fresh Dolphin per clip (batch mode required for frame dump)."""
    from src.capture.dolphin import DolphinController, DolphinConfig
    from src.capture.ffmpeg import FFmpegEncoder

    start_capture_calls = 0

    def mock_start_capture(self: DolphinController, **kwargs: object) -> None:
        nonlocal start_capture_calls
        start_capture_calls += 1
        # Set _output_dir like the real method does
        output_dir = kwargs.get("output_dir")
        if output_dir is not None:
            self._output_dir = output_dir if isinstance(output_dir, Path) else Path(str(output_dir))
            # Create dummy output files like Dolphin would (in subdirectories)
            frames_dir = self._output_dir / "Frames"
            audio_dir = self._output_dir / "Audio"
            frames_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)
            (frames_dir / "framedump0.avi").touch()
            (audio_dir / "dspdump.wav").touch()

    with patch.object(DolphinController, "start_capture", mock_start_capture):
        with patch.object(DolphinController, "wait_for_completion", return_value=0):
            with patch.object(DolphinController, "get_active_window", return_value="12345"):
                with patch.object(FFmpegEncoder, "encode_avi"):
                    with patch("src.capture.pipeline.write_sidecar_file"):
                        pipeline = CapturePipeline(
                            output_dir=tmp_path / "clips",
                            dolphin_config=DolphinConfig(),
                        )

                        moments = [
                            TaggedMoment(
                                replay_path=Path(f"/tmp/test{i}.slp"),
                                frame_start=i * 100,
                                frame_end=i * 100 + 50,
                                tags=["test"],
                                metadata={"date": "2025-01-01", "stage": "bf", "player": "fox"},
                            )
                            for i in range(3)
                        ]

                        pipeline.capture_moments(moments)

    # Should launch fresh Dolphin for each clip (batch mode required for frame dumping)
    assert start_capture_calls == 3, f"Expected 3 start_capture calls, got {start_capture_calls}"


def test_capture_moments_uses_async_encoding(tmp_path: Path) -> None:
    """capture_moments uses encode_avi_async for background encoding."""
    from src.capture.dolphin import DolphinController, DolphinConfig
    from src.capture.ffmpeg import FFmpegEncoder

    encode_async_calls = 0
    encode_sync_calls = 0

    def mock_start_capture(self: DolphinController, **kwargs: object) -> None:
        output_dir = kwargs.get("output_dir")
        if output_dir is not None:
            self._output_dir = output_dir if isinstance(output_dir, Path) else Path(str(output_dir))
            frames_dir = self._output_dir / "Frames"
            audio_dir = self._output_dir / "Audio"
            frames_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)
            (frames_dir / "framedump0.avi").touch()
            (audio_dir / "dspdump.wav").touch()

    def mock_encode_avi_async(self: FFmpegEncoder, **kwargs: object) -> "Future[None]":
        nonlocal encode_async_calls
        encode_async_calls += 1
        future: Future[None] = Future()
        future.set_result(None)
        return future

    def mock_encode_avi(self: FFmpegEncoder, **kwargs: object) -> None:
        nonlocal encode_sync_calls
        encode_sync_calls += 1

    with patch.object(DolphinController, "start_capture", mock_start_capture):
        with patch.object(DolphinController, "wait_for_completion", return_value=0):
            with patch.object(DolphinController, "get_active_window", return_value="12345"):
                with patch.object(FFmpegEncoder, "encode_avi_async", mock_encode_avi_async):
                    with patch.object(FFmpegEncoder, "encode_avi", mock_encode_avi):
                        with patch("src.capture.pipeline.write_sidecar_file"):
                            pipeline = CapturePipeline(
                                output_dir=tmp_path / "clips",
                                dolphin_config=DolphinConfig(),
                            )

                            moments = [
                                TaggedMoment(
                                    replay_path=Path(f"/tmp/test{i}.slp"),
                                    frame_start=i * 100,
                                    frame_end=i * 100 + 50,
                                    tags=["test"],
                                    metadata={"date": "2025-01-01", "stage": "bf", "player": "fox"},
                                )
                                for i in range(3)
                            ]

                            results = pipeline.capture_moments(moments)

    # Should use async encoding for all 3 clips
    assert encode_async_calls == 3, f"Expected 3 encode_avi_async calls, got {encode_async_calls}"
    # Should NOT use sync encoding
    assert encode_sync_calls == 0, f"Expected 0 encode_avi calls, got {encode_sync_calls}"
    # Should return 3 results
    assert len(results) == 3
