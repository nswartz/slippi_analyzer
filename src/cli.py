"""CLI interface for slippi-clip."""

from pathlib import Path

import click

from src.database import MomentDatabase


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Slippi-clip: Scan replays for moments and capture video clips."""
    pass


@main.command()
@click.argument("replay_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--full-rescan", is_flag=True, help="Re-scan all files, ignoring cache")
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def scan(replay_dir: Path, full_rescan: bool, db: Path) -> None:
    """Scan replay directory for moments."""
    # Ensure parent directory exists
    db.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Scanning {replay_dir}...")
    click.echo(f"Database: {db}")

    # Initialize database
    database = MomentDatabase(db)
    database.initialize()

    if full_rescan:
        click.echo("Full rescan enabled")

    # Find all .slp files
    replay_files = list(replay_dir.glob("**/*.slp"))
    click.echo(f"Found {len(replay_files)} replay files")

    # TODO: Parse replays and run detectors
    click.echo("Scan complete")


@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("--opponent", help="Filter by opponent character")
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def find(tag: tuple[str, ...], opponent: str | None, db: Path) -> None:
    """Find moments matching criteria."""
    click.echo(f"Finding moments in {db}")
    if tag:
        click.echo(f"Tags: {', '.join(tag)}")
    if opponent:
        click.echo(f"Opponent: {opponent}")
    # TODO: Implement query logic
    click.echo("Find complete (not implemented yet)")


@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def capture(tag: tuple[str, ...], output: Path, db: Path) -> None:
    """Capture video clips for matching moments."""
    click.echo(f"Capturing clips to {output}")
    # TODO: Implement capture logic
    click.echo("Capture complete (not implemented yet)")


@main.command("compile")
@click.argument("clips_dir", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
def compile_clips(clips_dir: Path, output: Path) -> None:
    """Compile clips into a single video."""
    click.echo(f"Compiling {clips_dir} to {output}")
    # TODO: Implement compile logic
    click.echo("Compile complete (not implemented yet)")


if __name__ == "__main__":
    main()
