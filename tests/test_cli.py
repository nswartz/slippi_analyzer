"""Tests for CLI interface."""

from pathlib import Path

from click.testing import CliRunner

from src.cli import main
from src.database import MomentDatabase
from src.models import TaggedMoment


def test_cli_help() -> None:
    """CLI shows help message."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "slippi-clip" in result.output.lower() or "usage" in result.output.lower()


def test_cli_scan_command_exists() -> None:
    """CLI has scan command."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])

    assert result.exit_code == 0
    assert "scan" in result.output.lower()


def test_cli_find_command_exists() -> None:
    """CLI has find command."""
    runner = CliRunner()
    result = runner.invoke(main, ["find", "--help"])

    assert result.exit_code == 0
    assert "find" in result.output.lower()


def test_scan_initializes_database(tmp_path: Path) -> None:
    """Scan command initializes database."""
    runner = CliRunner()

    replay_dir = tmp_path / "replays"
    replay_dir.mkdir()

    db_path = tmp_path / "test.db"

    result = runner.invoke(main, [
        "scan",
        str(replay_dir),
        "--db", str(db_path),
    ])

    assert result.exit_code == 0
    assert db_path.exists()


def test_find_queries_database_by_tag(tmp_path: Path) -> None:
    """Find command queries database and displays results."""
    db_path = tmp_path / "test.db"

    # Set up database with test moments
    db = MomentDatabase(db_path)
    db.initialize()

    moment1 = TaggedMoment(
        replay_path=Path("/replays/game1.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic"],
        metadata={"opponent": "fox", "stage": "battlefield"},
    )
    moment2 = TaggedMoment(
        replay_path=Path("/replays/game2.slp"),
        frame_start=2000,
        frame_end=2500,
        tags=["ledgehog:strict"],
        metadata={"opponent": "marth", "stage": "fd"},
    )

    db.store_moment(moment1, mtime=1000.0)
    db.store_moment(moment2, mtime=1000.0)

    runner = CliRunner()
    result = runner.invoke(main, [
        "find",
        "--tag", "ledgehog:basic",
        "--db", str(db_path),
    ])

    assert result.exit_code == 0
    # Should show the found moment info
    assert "game1.slp" in result.output
    assert "fox" in result.output or "1000" in result.output


def test_find_displays_count(tmp_path: Path) -> None:
    """Find command shows count of matching moments."""
    db_path = tmp_path / "test.db"

    db = MomentDatabase(db_path)
    db.initialize()

    # Store 3 moments with same tag
    for i in range(3):
        moment = TaggedMoment(
            replay_path=Path(f"/replays/game{i}.slp"),
            frame_start=1000 + i * 100,
            frame_end=1500 + i * 100,
            tags=["ledgehog:basic"],
            metadata={},
        )
        db.store_moment(moment, mtime=1000.0)

    runner = CliRunner()
    result = runner.invoke(main, [
        "find",
        "--tag", "ledgehog:basic",
        "--db", str(db_path),
    ])

    assert result.exit_code == 0
    # Should indicate 3 moments found
    assert "3" in result.output
