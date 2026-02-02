"""Tests for configuration file support."""

from pathlib import Path

from src.config import Config, get_xdg_data_home, load_config


def test_config_defaults() -> None:
    """Config has sensible defaults when no file exists."""
    config = Config()

    # Uses XDG_DATA_HOME for database
    expected_db = get_xdg_data_home() / "slippi-clip" / "moments.db"
    assert config.db_path == expected_db
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

    # Should return default config with XDG paths
    expected_db = get_xdg_data_home() / "slippi-clip" / "moments.db"
    assert config.player_port == 0
    assert config.db_path == expected_db


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
    # Default values (XDG paths)
    expected_db = get_xdg_data_home() / "slippi-clip" / "moments.db"
    assert config.db_path == expected_db


def test_config_player_tags_default() -> None:
    """Config has empty player_tags by default."""
    config = Config()

    assert config.player_tags == []


def test_load_config_player_tags(tmp_path: Path) -> None:
    """Load player_tags from config file."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[general]
player_tags = ["PDL-637", "PIE-381"]
""")

    config = load_config(config_path)

    assert config.player_tags == ["PDL-637", "PIE-381"]


def test_config_player_tags_with_port_fallback(tmp_path: Path) -> None:
    """When player_tags is set, player_port can still be used as fallback."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[general]
player_port = 1
player_tags = ["PDL-637"]
""")

    config = load_config(config_path)

    # Both are set - tags take precedence in scanning logic
    assert config.player_tags == ["PDL-637"]
    assert config.player_port == 1


def test_load_config_expands_tilde_in_paths(tmp_path: Path) -> None:
    """Database path with ~ should be expanded to user home."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[database]
path = "~/.slippi-clip/moments.db"
""")

    config = load_config(config_path)

    # Tilde should be expanded
    assert "~" not in str(config.db_path)
    assert str(config.db_path).startswith(str(Path.home()))
