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
        replay_path=Path("/replays/game.slp"),
        output_dir=Path("/tmp/frames"),
    )

    assert "/usr/bin/dolphin-emu" in cmd[0]
    assert "-u" in cmd  # User directory


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
    assert "dumpframes" in content
