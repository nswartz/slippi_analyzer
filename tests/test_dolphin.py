"""Tests for Dolphin automation."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.capture.dolphin import (
    DolphinConfig,
    DolphinController,
    build_dolphin_command,
)


def test_dolphin_config_defaults() -> None:
    """DolphinConfig has sensible defaults."""
    config = DolphinConfig()

    assert config.executable == Path("/usr/bin/dolphin-emu")
    assert config.user_dir is not None


def test_dolphin_config_custom_paths() -> None:
    """DolphinConfig accepts custom paths."""
    config = DolphinConfig(
        executable=Path("/custom/dolphin"),
        user_dir=Path("/custom/user"),
        iso_path=Path("/path/to/melee.iso"),
    )

    assert config.executable == Path("/custom/dolphin")
    assert config.iso_path == Path("/path/to/melee.iso")


def test_build_dolphin_command() -> None:
    """Build correct Dolphin launch command."""
    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=Path("/home/user/.dolphin-slippi"),
        iso_path=Path("/games/melee.iso"),
    )

    cmd = build_dolphin_command(
        config=config,
        playback_config_path=Path("/home/user/.dolphin-slippi/Slippi/playback.txt"),
        output_dir=Path("/tmp/frames"),
    )

    assert "/usr/bin/dolphin-emu" in cmd[0]
    assert "-u" in cmd  # User directory
    assert "-i" in cmd  # Playback config flag
    assert "-b" in cmd  # Batch mode flag
    assert "--cout" in cmd  # Console output for frame tracking


def test_dolphin_controller_setup_dump_config(tmp_path: Path) -> None:
    """DolphinController sets up frame dump configuration."""
    user_dir = tmp_path / "dolphin"
    user_dir.mkdir()

    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=user_dir,
    )

    controller = DolphinController(config)
    controller.setup_frame_dump(output_dir=tmp_path / "frames")

    # Check that config file was created/modified
    gfx_ini = user_dir / "Config" / "GFX.ini"
    assert gfx_ini.exists()

    content = gfx_ini.read_text().lower()
    assert "internalresolutionframedumps" in content


def test_setup_frame_dump_preserves_case(tmp_path: Path) -> None:
    """GFX.ini option names must preserve CamelCase for Dolphin compatibility."""
    user_dir = tmp_path / "dolphin"
    user_dir.mkdir()

    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=user_dir,
    )

    controller = DolphinController(config)
    output_dir = tmp_path / "frames"
    controller.setup_frame_dump(output_dir=output_dir)

    gfx_ini = user_dir / "Config" / "GFX.ini"
    content = gfx_ini.read_text()

    # Dolphin requires CamelCase keys - lowercase won't work
    assert "InternalResolutionFrameDumps" in content, f"Expected InternalResolutionFrameDumps in: {content}"


def test_setup_frame_dump_configures_dolphin_ini(tmp_path: Path) -> None:
    """setup_frame_dump enables DumpFramesSilent in Dolphin.ini for batch mode."""
    user_dir = tmp_path / "dolphin"
    user_dir.mkdir()

    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=user_dir,
    )

    controller = DolphinController(config)
    output_dir = tmp_path / "frames"
    controller.setup_frame_dump(output_dir=output_dir)

    dolphin_ini = user_dir / "Config" / "Dolphin.ini"
    assert dolphin_ini.exists(), "Dolphin.ini should be created"

    content = dolphin_ini.read_text()

    # Must enable silent dump for batch mode
    assert "DumpFrames = True" in content, f"Expected DumpFrames in: {content}"
    assert "DumpFramesSilent = True" in content, f"Expected DumpFramesSilent in: {content}"

    # DSP section must enable audio dump
    assert "[DSP]" in content, f"Expected DSP section in: {content}"
    assert "DumpAudio = True" in content, f"Expected DumpAudio in: {content}"
    assert "DumpAudioSilent = True" in content, f"Expected DumpAudioSilent in: {content}"


def test_wait_for_completion_monitors_file_size(tmp_path: Path) -> None:
    """wait_for_completion terminates Dolphin when frame dump file stops growing."""
    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=tmp_path,
    )
    controller = DolphinController(config)

    # Create frame dump file that simulates a completed dump
    # Dolphin creates Frames/ subdirectory under the dump path
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    frames_subdir = frame_dir / "Frames"
    frames_subdir.mkdir()
    video_file = frames_subdir / "framedump0.avi"
    video_file.write_bytes(b"x" * 1000)

    # Mock the process
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Process still running
    mock_process.returncode = 0
    # Accessing protected member is acceptable in tests for mocking
    controller._process = mock_process  # pyright: ignore[reportPrivateUsage]

    # Track terminate calls
    terminate_called = False
    def mock_terminate():
        nonlocal terminate_called
        terminate_called = True
        mock_process.poll.return_value = 0

    mock_process.terminate.side_effect = mock_terminate
    mock_process.wait.return_value = 0

    # Run wait_for_completion - should detect file is stable and terminate
    result = controller.wait_for_completion(
        frame_dir=frame_dir,
        check_interval=0.05,
        stable_threshold=0.1,
        timeout=5.0,
    )

    # Should have terminated the process
    assert terminate_called, "Process should be terminated when file stops growing"
    assert result == 0


def test_reload_replay_updates_playback_config_with_command_id(tmp_path: Path) -> None:
    """reload_replay should update playback.txt with new commandId."""
    import json

    user_dir = tmp_path / "dolphin"
    slippi_dir = user_dir / "Slippi"
    slippi_dir.mkdir(parents=True)

    config = DolphinConfig(
        executable=Path("/usr/bin/echo"),
        user_dir=user_dir,
        iso_path=Path("/tmp/test.iso"),
    )
    controller = DolphinController(config)

    # Mock that Dolphin is running
    controller._process = MagicMock()  # pyright: ignore[reportPrivateUsage]
    controller._process.poll.return_value = None  # Still running

    # Reload with new replay
    controller.reload_replay(
        replay_path=Path("/tmp/new_replay.slp"),
        start_frame=100,
        end_frame=200,
    )

    # Verify playback.txt was updated
    playback_config = slippi_dir / "playback.txt"
    assert playback_config.exists()

    with open(playback_config) as f:
        config_data = json.load(f)

    assert config_data["replay"] == str(Path("/tmp/new_replay.slp").absolute())
    assert config_data["startFrame"] == 100
    assert config_data["endFrame"] == 200
    assert "commandId" in config_data
    assert config_data["commandId"]  # Should not be empty


def test_start_capture_calls_minimize_with_sync_after_launch() -> None:
    """First Dolphin window should be minimized with --sync after Popen."""
    config = DolphinConfig(
        executable=Path("/usr/bin/echo"),
        user_dir=Path("/tmp/test-dolphin"),
        iso_path=Path("/tmp/test.iso"),
    )
    controller = DolphinController(config)

    # Track call ordering: list of ("popen", cmd) or ("run", cmd) tuples
    call_order: list[tuple[str, list[str]]] = []

    def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
        call_order.append(("run", list(cmd)))
        result = MagicMock()
        result.returncode = 0
        result.stdout = "12345"
        return result

    def mock_popen_init(cmd: list[str], **kwargs: object) -> MagicMock:
        call_order.append(("popen", list(cmd)))
        return MagicMock()

    with patch("subprocess.run", side_effect=mock_run):
        with patch("subprocess.Popen", side_effect=mock_popen_init):
            Path("/tmp/test-dolphin/Slippi").mkdir(parents=True, exist_ok=True)
            Path("/tmp/test-dolphin/Config").mkdir(parents=True, exist_ok=True)

            controller.start_capture(
                replay_path=Path("/tmp/test.slp"),
                output_dir=Path("/tmp/output"),
            )

            # Accessing protected method is acceptable in tests for cleanup
            controller._stop_window_minimizer()  # pyright: ignore[reportPrivateUsage]

    # Find the index of Popen call
    popen_indices = [i for i, (call_type, _) in enumerate(call_order) if call_type == "popen"]
    assert len(popen_indices) >= 1, f"Popen should be called. Calls: {call_order}"
    popen_index = popen_indices[0]

    # Find the index of xdotool search --sync call
    sync_search_indices = [
        i for i, (call_type, cmd) in enumerate(call_order)
        if call_type == "run" and "xdotool" in cmd and "--sync" in cmd and "search" in cmd
    ]
    assert len(sync_search_indices) >= 1, f"Should have --sync search call. Calls: {call_order}"
    sync_search_index = sync_search_indices[0]

    # Critical: verify xdotool search --sync is called AFTER Popen
    assert sync_search_index > popen_index, (
        f"xdotool search --sync (index {sync_search_index}) must be called after "
        f"Popen (index {popen_index}). Call order: {call_order}"
    )


def test_minimize_dolphin_window_moves_to_least_active_monitor(tmp_path: Path) -> None:
    """Dolphin window is moved to least-active monitor before minimizing."""
    from src.capture.monitors import Monitor

    config = DolphinConfig(executable=Path("/usr/bin/dolphin-emu"), user_dir=tmp_path)
    controller = DolphinController(config)

    monitors = [
        Monitor("DP-1", 0, 0, 1920, 1080, True),
        Monitor("HDMI-1", 1920, 0, 1920, 1080, False),
    ]

    run_calls: list[list[str]] = []

    def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
        run_calls.append(cmd)
        result = MagicMock()
        result.returncode = 0
        # Return window ID for xdotool search
        if "search" in cmd:
            result.stdout = "12345\n"
        return result

    with patch("src.capture.dolphin.get_monitors", return_value=monitors):
        with patch("src.capture.dolphin.get_least_active_monitor") as mock_least:
            mock_least.return_value = monitors[1]  # HDMI-1
            with patch("subprocess.run", side_effect=mock_run):
                # pyright: ignore[reportPrivateUsage]
                controller._minimize_dolphin_window()

    # Verify windowmove was called with HDMI-1 coordinates (x=1920)
    move_calls = [c for c in run_calls if "windowmove" in c]
    assert len(move_calls) > 0, f"Should have windowmove call. Calls: {run_calls}"
    # Should move to x=1920 (HDMI-1's x position)
    move_call = move_calls[0]
    assert "1920" in move_call, f"Should move to x=1920. Call: {move_call}"
