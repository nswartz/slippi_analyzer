"""Capture pipeline for recording moments as video clips."""

import shutil
import tempfile
from concurrent.futures import Future
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

        This method launches a fresh Dolphin instance for each capture.
        For batch captures, use capture_moments() which reuses a single
        Dolphin instance via reload_replay().

        Args:
            moment: The moment to capture
            index: Index for filename generation

        Returns:
            Path to the generated video clip, or None if capture failed
        """
        # Capture active window RIGHT BEFORE starting Dolphin
        # This ensures we return focus to whatever user was working in,
        # even during batch captures where multiple moments are processed
        active_window = self._dolphin.get_active_window()

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
                restore_window=active_window,
            )

            # Wait for capture to complete (monitors frame dump file)
            return_code = self._dolphin.wait_for_completion(frame_dir=frame_dir)
            if return_code != 0:
                return None

            # Find Dolphin's output files (in subdirectories created by Dolphin)
            video_file = frame_dir / "Frames" / "framedump0.avi"
            audio_file = frame_dir / "Audio" / "dspdump.wav"

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

        Launches a fresh Dolphin instance per clip. Encodes in background while
        next clip captures, reducing total batch time.

        Args:
            moments: List of moments to capture

        Returns:
            List of paths to generated video clips
        """
        if not moments:
            return []

        results: list[Path] = []
        pending_encodes: list[tuple[Future[None], Path, TaggedMoment, str]] = []

        for i, moment in enumerate(moments, start=1):
            # Capture active window RIGHT BEFORE each Dolphin launch
            active_window = self._dolphin.get_active_window()

            # Create temp directory for frames (manual cleanup after async encode)
            temp_dir = tempfile.mkdtemp()
            frame_dir = Path(temp_dir) / "frames"
            frame_dir.mkdir()

            # Start Dolphin capture (batch mode - exits after replay)
            self._dolphin.start_capture(
                replay_path=moment.replay_path,
                output_dir=frame_dir,
                start_frame=moment.frame_start,
                end_frame=moment.frame_end,
                restore_window=active_window,
            )

            # Wait for capture to complete
            return_code = self._dolphin.wait_for_completion(frame_dir=frame_dir)
            if return_code != 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                continue

            # Find Dolphin's output files
            video_file = frame_dir / "Frames" / "framedump0.avi"
            audio_file = frame_dir / "Audio" / "dspdump.wav"

            # Generate output filename
            filename = generate_clip_filename(moment, i)
            output_path = self.output_dir / filename

            # Start encoding in background (runs while next clip captures)
            future = self._ffmpeg.encode_avi_async(
                video_file=video_file,
                output_file=output_path,
                audio_file=audio_file if audio_file.exists() else None,
            )
            pending_encodes.append((future, output_path, moment, temp_dir))

        # Wait for all encodes to complete
        for future, output_path, moment, temp_dir in pending_encodes:
            try:
                future.result(timeout=300)
                write_sidecar_file(output_path, moment)
                results.append(output_path)
            except Exception as e:
                print(f"Encoding failed for {output_path}: {e}")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        return results
