"""Capture pipeline for recording moments as video clips."""

import tempfile
from pathlib import Path

from src.capture.dolphin import DolphinConfig, DolphinController
from src.capture.ffmpeg import FFmpegEncoder
from src.models import TaggedMoment, generate_clip_filename
from src.sidecar import write_sidecar_file


class CapturePipeline:
    """Pipeline for capturing moments as video clips."""

    def __init__(
        self,
        output_dir: Path,
        dolphin_config: DolphinConfig | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.dolphin_config = dolphin_config or DolphinConfig()
        self._dolphin = DolphinController(self.dolphin_config)
        self._ffmpeg = FFmpegEncoder()

    def capture_moment(
        self,
        moment: TaggedMoment,
        index: int,
    ) -> Path | None:
        """Capture a single moment as a video clip.

        Args:
            moment: The moment to capture
            index: Index for filename generation

        Returns:
            Path to the generated video clip, or None if capture failed
        """
        # Create temp directory for frames
        with tempfile.TemporaryDirectory() as temp_dir:
            frame_dir = Path(temp_dir) / "frames"
            frame_dir.mkdir()

            # Start Dolphin capture for the specific frame range
            self._dolphin.start_capture(
                replay_path=moment.replay_path,
                output_dir=frame_dir,
                start_frame=moment.frame_start,
                end_frame=moment.frame_end,
            )

            # Wait for capture to complete (monitors frame dump file)
            return_code = self._dolphin.wait_for_completion(frame_dir=frame_dir)
            if return_code != 0:
                return None

            # Find Dolphin's output files
            video_file = frame_dir / "framedump0.avi"
            audio_file = frame_dir / "dspdump.wav"

            # Generate output filename
            filename = generate_clip_filename(moment, index)
            output_path = self.output_dir / filename

            # Encode AVI+WAV to MP4
            self._ffmpeg.encode_avi(
                video_file=video_file,
                output_file=output_path,
                audio_file=audio_file if audio_file.exists() else None,
            )

            # Write sidecar metadata file
            write_sidecar_file(output_path, moment)

            return output_path

    def capture_moments(
        self,
        moments: list[TaggedMoment],
    ) -> list[Path]:
        """Capture multiple moments as video clips.

        Args:
            moments: List of moments to capture

        Returns:
            List of paths to generated video clips
        """
        results: list[Path] = []

        for i, moment in enumerate(moments, start=1):
            result = self.capture_moment(moment, index=i)
            if result is not None:
                results.append(result)

        return results
