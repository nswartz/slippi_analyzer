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
