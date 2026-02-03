"""Dolphin emulator automation for frame dumping."""

import json
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.capture.monitors import get_least_active_monitor, get_monitors


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
    batch_mode: bool = False,
) -> list[str]:
    """Build command to launch Slippi Playback for frame dumping.

    Args:
        config: Dolphin configuration
        playback_config_path: Path to playback.txt config file
        batch_mode: If True, Dolphin exits after replay ends. WARNING: batch
            mode (-b flag) DISABLES frame dumping in Slippi Playback! Leave
            False (default) for frame capture - Dolphin will be terminated
            by wait_for_completion() after the dump file stabilizes.

    Returns:
        Command as list of strings
    """
    cmd: list[str] = [str(config.executable)]

    if config.user_dir:
        cmd.extend(["-u", str(config.user_dir)])

    if config.iso_path:
        cmd.extend(["-e", str(config.iso_path)])

    # Slippi Playback specific arguments
    # NOTE: Don't use --output-directory - it may conflict with frame dumping.
    # Dumps go to user_dir/Dump/ instead.
    cmd.extend([
        "-i", str(playback_config_path),  # Playback config file
        "--hide-seekbar",  # Hide seekbar during playback
        "--cout",  # Enable console output for frame tracking
    ])

    # Batch mode causes Dolphin to exit after replay ends
    # WARNING: -b flag DISABLES frame dumping! Only use for non-capture scenarios.
    if batch_mode:
        cmd.append("-b")

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
        self._process: subprocess.Popen[bytes] | None = None
        self._original_window: str | None = None
        self._minimize_thread: threading.Thread | None = None
        self._stop_minimize_thread = threading.Event()
        self._minimized_windows: set[str] = set()
        self._output_dir: Path | None = None  # Set by start_capture for persistent sessions

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

    def _kill_existing_dolphin(self) -> None:
        """Kill any existing Slippi Dolphin emulator processes before starting a new capture.

        This prevents issues where a lingering Dolphin window from a previous
        run interferes with launching a new instance.

        IMPORTANT: Only targets Slippi emulator, NOT the KDE Dolphin file manager.
        The KDE file manager is /usr/bin/dolphin, while Slippi runs from AppImage.
        """
        try:
            # Only kill Slippi emulator processes, NOT the KDE Dolphin file manager
            # Slippi runs from AppImage with "Slippi" in the path or as mounted AppImage
            # The KDE file manager is /usr/bin/dolphin and should NOT be killed
            slippi_patterns = [
                "Slippi_Playback",  # AppImage name
                "Slippi.*AppImage",  # AppImage with Slippi
                r"\.mount_Slippi",  # Mounted AppImage temp directory
            ]
            for pattern in slippi_patterns:
                subprocess.run(
                    ["pkill", "-f", pattern],
                    capture_output=True,
                    timeout=5,
                )
            # Give processes time to terminate
            time.sleep(0.5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

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
        """Find and minimize Dolphin window on least-active monitor.

        Uses xdotool --sync to wait for window to appear rather than fixed sleep,
        which minimizes the window as soon as it's created. On multi-monitor
        setups, moves the window to the least-active monitor first.
        """
        try:
            # Get monitors and find least active
            monitors = get_monitors()
            target_monitor = get_least_active_monitor(monitors) if monitors else None

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
                        # Move to least-active monitor if we have multi-monitor
                        if target_monitor and len(monitors) > 1:
                            subprocess.run(
                                [
                                    "xdotool",
                                    "windowmove",
                                    window_id,
                                    str(target_monitor.x),
                                    str(target_monitor.y),
                                ],
                                timeout=5,
                            )

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
        """Prepare directories for frame dumping.

        NOTE: This method intentionally does NOT modify Dolphin.ini or GFX.ini.
        The user_dir should be pre-configured with correct settings (copy from
        Slippi Launcher config). Using configparser to rewrite INI files corrupts
        them in ways that break Dolphin's frame dumping.

        Only sets up:
        - Dump directories (Frames/ and Audio/)
        - Gecko codes for music muting (if enabled)
        """
        if self.config.user_dir is None:
            raise ValueError("user_dir must be set to configure frame dump")

        # Ensure Dump directories exist
        dump_dir = self.config.user_dir / "Dump"
        (dump_dir / "Frames").mkdir(parents=True, exist_ok=True)
        (dump_dir / "Audio").mkdir(parents=True, exist_ok=True)

        # Set up Gecko code for music muting (this writes to GameSettings/, not Config/)
        if self.config.mute_music:
            self.setup_music_mute()

    def start_capture(
        self,
        replay_path: Path,
        output_dir: Path,
        start_frame: int | None = None,
        end_frame: int | None = None,
        restore_window: str | None = None,
        persistent: bool = False,
    ) -> None:
        """Start Dolphin for frame capture.

        Args:
            replay_path: Path to replay file
            output_dir: Directory for output frames
            start_frame: Optional start frame for capture
            end_frame: Optional end frame for capture
            restore_window: Window ID to restore focus to after capture
            persistent: If True, Dolphin stays running after replay ends for
                reload_replay() calls. Set False (default) for single captures.
        """
        # Kill any lingering Dolphin processes before starting
        self._kill_existing_dolphin()

        self.setup_frame_dump(output_dir)

        # Store output directory for persistent sessions
        self._output_dir = output_dir

        # Create playback config file
        if self.config.user_dir is None:
            raise ValueError("user_dir must be set for playback config")

        playback_config_path = self.config.user_dir / "Slippi" / "playback.txt"
        playback_config_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate commandId for persistent sessions (needed for reload)
        command_id = f"cmd-{uuid.uuid4().hex[:8]}" if persistent else None

        create_playback_config(
            replay_path=replay_path,
            output_path=playback_config_path,
            start_frame=start_frame,
            end_frame=end_frame,
            command_id=command_id,
        )

        cmd = build_dolphin_command(
            config=self.config,
            playback_config_path=playback_config_path,
            batch_mode=False,  # NEVER use batch mode - it disables frame dumping!
        )

        # Use provided window ID or capture current for focus restoration
        self._original_window = restore_window or self.get_active_window()

        # Start background thread to minimize windows as they appear
        self._start_window_minimizer()

        # Don't capture stdout - it can fill the pipe buffer and block Dolphin
        # The --cout output goes to stderr anyway
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

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
        timeout: float = 120.0,
        terminate: bool = True,
    ) -> int:
        """Wait for Dolphin to finish capturing.

        Monitors frame dump file size. When the file stops growing for
        stable_threshold seconds, playback is considered complete.

        Args:
            frame_dir: Directory where frame dump files are written
            check_interval: Seconds between file size checks
            stable_threshold: Seconds file must be stable before terminating
            timeout: Maximum seconds to wait (default 120s). Without batch mode,
                Dolphin doesn't exit automatically, so this timeout prevents hangs.
            terminate: If True (default), terminate Dolphin after capture.
                Set False for persistent sessions where you'll call reload_replay().

        Returns:
            Return code from Dolphin process (0 on success, always 0 if not terminating)
        """
        if self._process is None:
            raise RuntimeError("No capture in progress")

        # Dolphin creates subdirectories under DumpPath: Frames/ for video, Audio/ for audio
        video_file = frame_dir / "Frames" / "framedump0.avi" if frame_dir else None
        last_size = -1
        stable_time = 0.0
        elapsed = 0.0

        while self._process.poll() is None:
            # Check for timeout
            if elapsed >= timeout:
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

        if terminate:
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

        # Not terminating - return success
        return 0

    def stop(self) -> None:
        """Stop Dolphin capture."""
        self._stop_window_minimizer()
        if self._process is not None:
            self._process.terminate()
            self._process.wait(timeout=10)
            self._process = None

    def copy_output_files(self, dest_dir: Path) -> None:
        """Copy output files from shared directory to destination.

        Used in persistent sessions to collect each clip's output files
        after capture completes, before reloading the next replay.

        Args:
            dest_dir: Destination directory for the output files

        Raises:
            RuntimeError: If no output directory has been set (start_capture not called)
        """
        if self._output_dir is None:
            raise RuntimeError("No output directory set. Call start_capture first.")

        # Dolphin creates subdirectories: Frames/ for video, Audio/ for audio
        video_file = self._output_dir / "Frames" / "framedump0.avi"
        audio_file = self._output_dir / "Audio" / "dspdump.wav"
        dest_dir.mkdir(parents=True, exist_ok=True)

        if video_file.exists():
            shutil.copy2(video_file, dest_dir / "framedump0.avi")
            video_file.unlink()  # Clear for next clip
        if audio_file.exists():
            shutil.copy2(audio_file, dest_dir / "dspdump.wav")
            audio_file.unlink()  # Clear for next clip

    def reload_replay(
        self,
        replay_path: Path,
        start_frame: int | None = None,
        end_frame: int | None = None,
    ) -> None:
        """Reload a new replay into running Dolphin via commandId.

        Dolphin must already be running (started via start_capture with persistent=True).
        Updates playback.txt with new replay and a fresh commandId,
        which triggers Dolphin to reload without restarting.

        Note: Call copy_output_files() before this method to save the previous
        clip's output files before they get overwritten.

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
