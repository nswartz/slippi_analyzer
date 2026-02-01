"""Dolphin emulator automation for frame dumping."""

import configparser
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


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
    replay_path: Path,
    output_dir: Path,
) -> list[str]:
    """Build command to launch Dolphin for frame dumping.

    Args:
        config: Dolphin configuration
        replay_path: Path to .slp replay file
        output_dir: Directory for frame dump output

    Returns:
        Command as list of strings
    """
    cmd = [str(config.executable)]

    if config.user_dir:
        cmd.extend(["-u", str(config.user_dir)])

    if config.iso_path:
        cmd.extend(["-e", str(config.iso_path)])

    # Slippi-specific replay playback arguments
    cmd.extend([
        "-i", str(replay_path),  # Input replay
        "--output-directory", str(output_dir),
    ])

    return cmd


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
        gfx_config = configparser.ConfigParser()
        if gfx_ini_path.exists():
            gfx_config.read(gfx_ini_path)

        # Ensure Settings section exists
        if "Settings" not in gfx_config:
            gfx_config["Settings"] = {}

        # Enable frame dumping
        gfx_config["Settings"]["DumpFrames"] = "True"
        gfx_config["Settings"]["DumpFramesAsImages"] = "True"
        gfx_config["Settings"]["DumpPath"] = str(output_dir)

        # Write config
        with open(gfx_ini_path, "w") as f:
            gfx_config.write(f)

    def start_capture(
        self,
        replay_path: Path,
        output_dir: Path,
    ) -> None:
        """Start Dolphin for frame capture.

        Args:
            replay_path: Path to replay file
            output_dir: Directory for output frames
        """
        self.setup_frame_dump(output_dir)

        cmd = build_dolphin_command(
            config=self.config,
            replay_path=replay_path,
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
