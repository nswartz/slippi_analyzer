"""Tests for CLI interface."""

from pathlib import Path

from click.testing import CliRunner

from src.cli import main


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
