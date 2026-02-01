"""Tests for configuration file support."""

from pathlib import Path

from src.config import Config, load_config


def test_config_defaults() -> None:
    """Config has sensible defaults when no file exists."""
    config = Config()

    assert config.db_path == Path("~/.config/slippi-clip/moments.db").expanduser()
    assert config.player_port == 0


def test_load_config_from_file(tmp_path: Path) -> None:
    """Load configuration from TOML file."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[general]
player_port = 2

[database]
path = "/custom/path/moments.db"

[dolphin]
executable = "/opt/dolphin/dolphin-emu"
iso_path = "/games/melee.iso"
""")

    config = load_config(config_path)

    assert config.player_port == 2
    assert config.db_path == Path("/custom/path/moments.db")
    assert config.dolphin_executable == Path("/opt/dolphin/dolphin-emu")
    assert config.iso_path == Path("/games/melee.iso")


def test_load_config_missing_file() -> None:
    """load_config returns defaults when file doesn't exist."""
    config = load_config(Path("/nonexistent/config.toml"))

    # Should return default config
    assert config.player_port == 0
    assert config.db_path == Path("~/.config/slippi-clip/moments.db").expanduser()


def test_config_partial_override(tmp_path: Path) -> None:
    """Config file can override only some values."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[general]
player_port = 3
""")

    config = load_config(config_path)

    # Overridden value
    assert config.player_port == 3
    # Default values
    assert config.db_path == Path("~/.config/slippi-clip/moments.db").expanduser()
