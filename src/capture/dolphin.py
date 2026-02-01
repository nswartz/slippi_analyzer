"""Dolphin emulator automation for frame dumping."""

import configparser
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DolphinConfig:
    """Configuration for Dolphin emulator."""

    executable: Path = field(default_factory=lambda: Path("/usr/bin/dolphin-emu"))
    user_dir: Path | None = field(
        default_factory=lambda: Path.home() / ".dolphin-slippi"
    )
    iso_path: Path | None = None


def build_dolphin_command(
    config: DolphinConfig,
    playback_config_path: Path,
    output_dir: Path,
) -> list[str]:
    """Build command to launch Slippi Playback for frame dumping.

    Args:
        config: Dolphin configuration
        playback_config_path: Path to playback.txt config file
        output_dir: Directory for frame dump output

    Returns:
        Command as list of strings
    """
    cmd = [str(config.executable)]

    if config.user_dir:
        cmd.extend(["-u", str(config.user_dir)])

    if config.iso_path:
        cmd.extend(["-e", str(config.iso_path)])

    # Slippi Playback specific arguments
    cmd.extend([
        "-i", str(playback_config_path),  # Playback config file
        "-b",  # Batch mode - exit when done
        "--output-directory", str(output_dir),
        "--hide-seekbar",  # Hide seekbar during playback
        "--cout",  # Enable console output for frame tracking
    ])

    return cmd


def create_playback_config(
    replay_path: Path,
    output_path: Path,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> None:
    """Create a Slippi playback configuration file.

    Args:
        replay_path: Path to the .slp replay file
        output_path: Path to write the playback.txt config
        start_frame: Optional start frame for playback
        end_frame: Optional end frame for playback
    """
    config: dict[str, Any] = {
        "mode": "normal",
        "replay": str(replay_path.absolute()),
        "isRealTimeMode": False,
        "outputOverlayFiles": False,
    }

    if start_frame is not None:
        config["startFrame"] = start_frame
    if end_frame is not None:
        config["endFrame"] = end_frame

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)


class DolphinController:
    """Controller for Dolphin emulator frame dumping."""

    def __init__(self, config: DolphinConfig) -> None:
        self.config = config
        self._process: subprocess.Popen[bytes] | None = None

    def setup_frame_dump(self, output_dir: Path) -> None:
        """Configure Dolphin for frame dumping.

        Modifies GFX.ini to enable frame dumping.
        """
        if self.config.user_dir is None:
            raise ValueError("user_dir must be set to configure frame dump")

        config_dir = self.config.user_dir / "Config"
        config_dir.mkdir(parents=True, exist_ok=True)

        gfx_ini_path = config_dir / "GFX.ini"

        # Parse existing config or create new
        # Preserve case for option names - Dolphin requires CamelCase
        gfx_config = configparser.ConfigParser()
        gfx_config.optionxform = str  # type: ignore[assignment]
        if gfx_ini_path.exists():
            gfx_config.read(gfx_ini_path)

        # Ensure Settings section exists
        if "Settings" not in gfx_config:
            gfx_config["Settings"] = {}

        # Enable video frame dumping at internal resolution (for quality)
        gfx_config["Settings"]["InternalResolutionFrameDumps"] = "True"

        # Write config
        with open(gfx_ini_path, "w") as f:
            gfx_config.write(f)

        # Also configure Dolphin.ini for silent batch mode dumping
        dolphin_ini_path = config_dir / "Dolphin.ini"
        dolphin_config = configparser.ConfigParser()
        dolphin_config.optionxform = str  # type: ignore[assignment]
        if dolphin_ini_path.exists():
            dolphin_config.read(dolphin_ini_path)

        if "Movie" not in dolphin_config:
            dolphin_config["Movie"] = {}

        # Enable silent dump for batch mode (no GUI prompts)
        dolphin_config["Movie"]["DumpFrames"] = "True"
        dolphin_config["Movie"]["DumpFramesSilent"] = "True"

        # Configure DSP for audio dumping
        if "DSP" not in dolphin_config:
            dolphin_config["DSP"] = {}
        dolphin_config["DSP"]["DumpAudio"] = "True"
        dolphin_config["DSP"]["DumpAudioSilent"] = "True"

        with open(dolphin_ini_path, "w") as f:
            dolphin_config.write(f)

    def start_capture(
        self,
        replay_path: Path,
        output_dir: Path,
        start_frame: int | None = None,
        end_frame: int | None = None,
    ) -> None:
        """Start Dolphin for frame capture.

        Args:
            replay_path: Path to replay file
            output_dir: Directory for output frames
            start_frame: Optional start frame for capture
            end_frame: Optional end frame for capture
        """
        self.setup_frame_dump(output_dir)

        # Create playback config file
        if self.config.user_dir is None:
            raise ValueError("user_dir must be set for playback config")

        playback_config_path = self.config.user_dir / "Slippi" / "playback.txt"
        playback_config_path.parent.mkdir(parents=True, exist_ok=True)

        create_playback_config(
            replay_path=replay_path,
            output_path=playback_config_path,
            start_frame=start_frame,
            end_frame=end_frame,
        )

        cmd = build_dolphin_command(
            config=self.config,
            playback_config_path=playback_config_path,
            output_dir=output_dir,
        )

        self._process = subprocess.Popen(cmd)

    def wait_for_completion(self, timeout: float | None = None) -> int:
        """Wait for Dolphin to finish capturing.

        Returns:
            Return code from Dolphin process
        """
        if self._process is None:
            raise RuntimeError("No capture in progress")

        return self._process.wait(timeout=timeout)

    def stop(self) -> None:
        """Stop Dolphin capture."""
        if self._process is not None:
            self._process.terminate()
            self._process.wait(timeout=10)
            self._process = None
