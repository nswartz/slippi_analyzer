"""Configuration file support for slippi-clip."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

try:
    import tomllib  # pyright: ignore[reportMissingTypeStubs]
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,import-untyped]


@dataclass
class Config:
    """Application configuration."""

    # General
    player_port: int = 0
    player_tags: list[str] = field(default_factory=lambda: [])

    # Database
    db_path: Path = field(
        default_factory=lambda: Path("~/.config/slippi-clip/moments.db").expanduser()
    )

    # Dolphin
    dolphin_executable: Path = field(
        default_factory=lambda: Path("/usr/bin/dolphin-emu")
    )
    dolphin_user_dir: Path | None = field(
        default_factory=lambda: Path.home() / ".dolphin-slippi"
    )
    iso_path: Path | None = None

    # FFmpeg
    ffmpeg_crf: int = 18
    ffmpeg_preset: str = "medium"


def load_config(config_path: Path) -> Config:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config.toml file

    Returns:
        Config object with values from file (or defaults if file missing)
    """
    config = Config()

    if not config_path.exists():
        return config

    with open(config_path, "rb") as f:
        data = cast(dict[str, Any], tomllib.load(f))  # pyright: ignore[reportUnknownMemberType]

    # General section
    general = cast(dict[str, Any], data.get("general", {}))
    if "player_port" in general:
        config.player_port = int(general["player_port"])
    if "player_tags" in general:
        tags = general["player_tags"]
        if isinstance(tags, list):
            config.player_tags = [str(t) for t in cast(list[Any], tags)]

    # Database section
    database = cast(dict[str, Any], data.get("database", {}))
    if "path" in database:
        config.db_path = Path(str(database["path"])).expanduser()

    # Dolphin section
    dolphin = cast(dict[str, Any], data.get("dolphin", {}))
    if "executable" in dolphin:
        config.dolphin_executable = Path(str(dolphin["executable"]))
    if "user_dir" in dolphin:
        config.dolphin_user_dir = Path(str(dolphin["user_dir"]))
    if "iso_path" in dolphin:
        config.iso_path = Path(str(dolphin["iso_path"]))

    # FFmpeg section
    ffmpeg = cast(dict[str, Any], data.get("ffmpeg", {}))
    if "crf" in ffmpeg:
        config.ffmpeg_crf = int(ffmpeg["crf"])
    if "preset" in ffmpeg:
        config.ffmpeg_preset = str(ffmpeg["preset"])

    return config


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    return Path("~/.config/slippi-clip/config.toml").expanduser()
