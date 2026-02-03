"""Dolphin emulator automation for frame dumping."""

import configparser
import json
import subprocess
import threading
import time
import uuid
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
    mute_music: bool = True  # Mute in-game music (keeps SFX) for video editing


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
    cmd: list[str] = [str(config.executable)]

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
    command_id: str | None = None,
) -> None:
    """Create a Slippi playback configuration file.

    Args:
        replay_path: Path to the .slp replay file
        output_path: Path to write the playback.txt config
        start_frame: Optional start frame for playback
        end_frame: Optional end frame for playback
        command_id: Optional command ID for triggering reload
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
    if command_id is not None:
        config["commandId"] = command_id

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)


class DolphinController:
    """Controller for Dolphin emulator frame dumping."""

    # Melee NTSC 1.02 game ID
    MELEE_GAME_ID = "GALE01"

    def __init__(self, config: DolphinConfig) -> None:
        self.config = config
        self._process: subprocess.Popen[str] | None = None
        self._original_window: str | None = None
        self._minimize_thread: threading.Thread | None = None
        self._stop_minimize_thread = threading.Event()
        self._minimized_windows: set[str] = set()

    def get_active_window(self) -> str | None:
        """Get the currently active window ID using xdotool."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _find_dolphin_windows(self) -> list[str]:
        """Find Dolphin window IDs by searching multiple patterns."""
        window_ids: list[str] = []
        # Try multiple search patterns - AppImage may use different names
        search_patterns = [
            ["xdotool", "search", "--name", "Slippi"],
            ["xdotool", "search", "--name", "Dolphin"],
            ["xdotool", "search", "--class", "dolphin-emu"],
            ["xdotool", "search", "--class", "dolphin"],
        ]
        for pattern in search_patterns:
            try:
                result = subprocess.run(
                    pattern,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0 and result.stdout.strip():
                    for wid in result.stdout.strip().split("\n"):
                        if wid and wid not in window_ids:
                            window_ids.append(wid)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        return window_ids

    def _window_minimizer_loop(self) -> None:
        """Background thread that continuously minimizes Dolphin windows.

        Polls rapidly to catch windows as soon as they appear, minimizing
        them before they can flash on screen or steal focus.
        """
        while not self._stop_minimize_thread.is_set():
            try:
                window_ids = self._find_dolphin_windows()
                for window_id in window_ids:
                    if window_id not in self._minimized_windows:
                        # Minimize this new window immediately
                        subprocess.run(
                            ["xdotool", "windowminimize", window_id],
                            timeout=2,
                            capture_output=True,
                        )
                        self._minimized_windows.add(window_id)
                        # Restore focus to original window
                        if self._original_window:
                            subprocess.run(
                                ["xdotool", "windowactivate", self._original_window],
                                timeout=2,
                                capture_output=True,
                            )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            # Poll every 50ms for fast response
            time.sleep(0.05)

    def _start_window_minimizer(self) -> None:
        """Start the background window minimizer thread."""
        self._stop_minimize_thread.clear()
        self._minimized_windows.clear()
        self._minimize_thread = threading.Thread(
            target=self._window_minimizer_loop,
            daemon=True,
        )
        self._minimize_thread.start()

    def _stop_window_minimizer(self) -> None:
        """Stop the background window minimizer thread."""
        self._stop_minimize_thread.set()
        if self._minimize_thread is not None:
            self._minimize_thread.join(timeout=2)
            self._minimize_thread = None

    def _minimize_dolphin_window(self) -> None:
        """Find and minimize Dolphin window immediately, restore focus.

        Uses xdotool --sync to wait for window to appear rather than fixed sleep,
        which minimizes the window as soon as it's created.
        """
        try:
            # Use --sync to wait for window to appear (up to 10 seconds)
            # This minimizes as soon as the window exists, reducing visibility
            result = subprocess.run(
                ["xdotool", "search", "--sync", "--name", "Slippi"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0 and result.stdout.strip():
                window_ids = result.stdout.strip().split("\n")
                for window_id in window_ids:
                    if window_id:
                        # Minimize immediately
                        subprocess.run(
                            ["xdotool", "windowminimize", "--sync", window_id],
                            timeout=5,
                        )
            else:
                # Fallback: try other patterns
                window_ids = self._find_dolphin_windows()
                for window_id in window_ids:
                    subprocess.run(
                        ["xdotool", "windowminimize", window_id],
                        timeout=5,
                    )

            # Restore focus to original window
            if self._original_window:
                subprocess.run(
                    ["xdotool", "windowactivate", "--sync", self._original_window],
                    timeout=5,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # xdotool not available or timed out, continue without minimizing
            pass

    def _mute_dolphin_audio(self) -> None:
        """Mute Dolphin's audio output via PulseAudio/PipeWire.

        This mutes the application so you don't hear it during capture,
        while still allowing audio to be dumped to file.
        """
        try:
            # Wait for Dolphin to register with PulseAudio
            time.sleep(1.5)

            # Get detailed sink input info and find Dolphin
            result = subprocess.run(
                ["pactl", "list", "sink-inputs"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return

            # Parse sink inputs - each starts with "Sink Input #N"
            current_id: str | None = None
            current_app: str = ""

            for line in result.stdout.split("\n"):
                line_stripped = line.strip()
                if line_stripped.startswith("Sink Input #"):
                    # Save previous if it was Dolphin
                    if current_id and ("dolphin" in current_app or "slippi" in current_app):
                        subprocess.run(
                            ["pactl", "set-sink-input-mute", current_id, "1"],
                            timeout=5,
                        )
                    # Start new sink input
                    current_id = line_stripped.split("#")[1].strip()
                    current_app = ""
                elif "application.name" in line_stripped.lower():
                    current_app = line_stripped.lower()
                elif "application.process.binary" in line_stripped.lower():
                    current_app += " " + line_stripped.lower()

            # Check the last one
            if current_id and ("dolphin" in current_app or "slippi" in current_app):
                subprocess.run(
                    ["pactl", "set-sink-input-mute", current_id, "1"],
                    timeout=5,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # pactl not available, continue without muting
            pass

    def setup_music_mute(self) -> None:
        """Set up Gecko code to mute in-game music (keeps SFX).

        Creates a game-specific settings file with a Gecko code that
        disables music playback in Melee NTSC 1.02.
        """
        if self.config.user_dir is None:
            raise ValueError("user_dir must be set to configure music mute")

        # Create GameSettings directory
        game_settings_dir = self.config.user_dir / "GameSettings"
        game_settings_dir.mkdir(parents=True, exist_ok=True)

        # Write Gecko code to disable music for Melee NTSC 1.02
        # "Netplay Safe Kill Music" by Myougi - works by returning 1 from music check
        # Source: https://www.smashladder.com/blogs/view/270d/2017-03-31/netplay-safe-kill-music-gecko-code-for-fm-4-4
        gecko_ini_path = game_settings_dir / f"{self.MELEE_GAME_ID}.ini"
        gecko_content = """\
[Gecko_Enabled]
$Netplay Safe Kill Music

[Gecko]
$Netplay Safe Kill Music
040249a4 38600001
"""
        with open(gecko_ini_path, "w") as f:
            f.write(gecko_content)

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

        # Enable cheats for Gecko codes (music muting)
        if self.config.mute_music:
            if "Core" not in dolphin_config:
                dolphin_config["Core"] = {}
            dolphin_config["Core"]["EnableCheats"] = "True"
            self.setup_music_mute()

        with open(dolphin_ini_path, "w") as f:
            dolphin_config.write(f)

    def start_capture(
        self,
        replay_path: Path,
        output_dir: Path,
        start_frame: int | None = None,
        end_frame: int | None = None,
        restore_window: str | None = None,
    ) -> None:
        """Start Dolphin for frame capture.

        Args:
            replay_path: Path to replay file
            output_dir: Directory for output frames
            start_frame: Optional start frame for capture
            end_frame: Optional end frame for capture
            restore_window: Window ID to restore focus to after capture
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

        # Use provided window ID or capture current for focus restoration
        self._original_window = restore_window or self.get_active_window()

        # Start background thread to minimize windows as they appear
        self._start_window_minimizer()

        self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

        # IMMEDIATELY minimize first window with --sync (waits for window to exist)
        # This catches the first window before the polling loop can miss it
        self._minimize_dolphin_window()

        # Mute Dolphin audio output (so user doesn't hear it during capture)
        self._mute_dolphin_audio()

    def wait_for_completion(
        self,
        frame_dir: Path | None = None,
        check_interval: float = 1.0,
        stable_threshold: float = 3.0,
        timeout: float | None = None,
    ) -> int:
        """Wait for Dolphin to finish capturing.

        Monitors frame dump file size. When the file stops growing for
        stable_threshold seconds, playback is considered complete.

        Args:
            frame_dir: Directory where frame dump files are written
            check_interval: Seconds between file size checks
            stable_threshold: Seconds file must be stable before terminating
            timeout: Maximum seconds to wait (None = no limit)

        Returns:
            Return code from Dolphin process (0 on success)
        """
        if self._process is None:
            raise RuntimeError("No capture in progress")

        video_file = frame_dir / "framedump0.avi" if frame_dir else None
        last_size = -1
        stable_time = 0.0
        elapsed = 0.0

        while self._process.poll() is None:
            # Check for timeout
            if timeout is not None and elapsed >= timeout:
                break

            # Check file size if we have a frame_dir
            if video_file and video_file.exists():
                current_size = video_file.stat().st_size
                if current_size == last_size:
                    stable_time += check_interval
                    if stable_time >= stable_threshold:
                        # File has stopped growing, playback is complete
                        break
                else:
                    stable_time = 0.0
                    last_size = current_size

            time.sleep(check_interval)
            elapsed += check_interval

        # Give Dolphin time to finish writing files
        time.sleep(2)

        # Stop the window minimizer thread
        self._stop_window_minimizer()

        # Terminate Dolphin
        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()

        return_code = self._process.returncode
        self._process = None
        return return_code if return_code is not None else 0

    def stop(self) -> None:
        """Stop Dolphin capture."""
        self._stop_window_minimizer()
        if self._process is not None:
            self._process.terminate()
            self._process.wait(timeout=10)
            self._process = None

    def reload_replay(
        self,
        replay_path: Path,
        start_frame: int | None = None,
        end_frame: int | None = None,
    ) -> None:
        """Reload a new replay into running Dolphin via commandId.

        Dolphin must already be running (started via start_capture).
        Updates playback.txt with new replay and a fresh commandId,
        which triggers Dolphin to reload without restarting.

        Args:
            replay_path: Path to new replay file
            start_frame: Optional start frame
            end_frame: Optional end frame

        Raises:
            RuntimeError: If Dolphin is not running
            ValueError: If user_dir is not configured
        """
        if self._process is None or self._process.poll() is not None:
            raise RuntimeError("Dolphin is not running. Call start_capture first.")

        if self.config.user_dir is None:
            raise ValueError("user_dir must be set for playback config")

        playback_config_path = self.config.user_dir / "Slippi" / "playback.txt"

        # Generate unique commandId to trigger reload
        command_id = f"cmd-{uuid.uuid4().hex[:8]}"

        create_playback_config(
            replay_path=replay_path,
            output_path=playback_config_path,
            start_frame=start_frame,
            end_frame=end_frame,
            command_id=command_id,
        )
