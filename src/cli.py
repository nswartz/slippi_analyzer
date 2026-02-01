"""CLI interface for slippi-clip."""

from pathlib import Path

import click

from src.capture.compile import compile_clips as compile_clips_fn
from src.capture.dolphin import DolphinConfig
from src.capture.pipeline import CapturePipeline
from src.config import Config, get_default_config_path, load_config
from src.database import MomentDatabase
from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment
from src.scanner import ReplayScanner


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
@click.pass_context
def main(ctx: click.Context, config: Path | None) -> None:
    """Slippi-clip: Scan replays for moments and capture video clips."""
    ctx.ensure_object(dict)

    config_path = config or get_default_config_path()
    ctx.obj["config"] = load_config(config_path)


@main.command()
@click.argument("replay_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--full-rescan", is_flag=True, help="Re-scan all files, ignoring cache")
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=None,
    help="Database path",
)
@click.option(
    "--player-port",
    type=int,
    default=None,
    help="Player port index (0-3)",
)
@click.pass_context
def scan(
    ctx: click.Context,
    replay_dir: Path,
    full_rescan: bool,
    db: Path | None,
    player_port: int | None,
) -> None:
    """Scan replay directory for moments."""
    cfg: Config = ctx.obj["config"]

    # Use CLI args or fall back to config
    db_path = db or cfg.db_path
    port = player_port if player_port is not None else cfg.player_port

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Scanning {replay_dir}...")
    click.echo(f"Database: {db_path}")

    # Initialize database
    database = MomentDatabase(db_path)
    database.initialize()

    if full_rescan:
        click.echo("Full rescan enabled")

    # Find all .slp files
    replay_files = list(replay_dir.glob("**/*.slp"))
    click.echo(f"Found {len(replay_files)} replay files")

    # Set up scanner and detectors
    scanner = ReplayScanner()
    registry = DetectorRegistry.with_default_detectors()

    # Scan each replay
    scanned_count = 0
    total_moments = 0

    for replay_path in replay_files:
        mtime = replay_path.stat().st_mtime

        # Skip if already scanned (unless full rescan)
        if not full_rescan and not database.needs_scan(replay_path, mtime):
            continue

        try:
            moments = scanner.scan_replay(
                replay_path=replay_path,
                player_port=port,
                registry=registry,
            )

            # Store each moment in database
            for moment in moments:
                database.store_moment(moment, mtime=mtime)

            scanned_count += 1
            total_moments += len(moments)
        except Exception as e:
            click.echo(f"  Error scanning {replay_path.name}: {e}", err=True)

    click.echo(f"Scanned {scanned_count} replays, found {total_moments} moments")


@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("--opponent", help="Filter by opponent character")
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Database path",
)
@click.pass_context
def find(ctx: click.Context, tag: tuple[str, ...], opponent: str | None, db: Path | None) -> None:
    """Find moments matching criteria."""
    cfg: Config = ctx.obj["config"]
    db_path = db or cfg.db_path
    database = MomentDatabase(db_path)

    # Find moments by tag
    all_moments: list[TaggedMoment] = []
    if tag:
        for t in tag:
            moments = database.find_moments_by_tag(t)
            all_moments.extend(moments)
    else:
        click.echo("No tag specified. Use --tag to filter moments.")
        return

    # Filter by opponent if specified
    if opponent:
        all_moments = [
            m for m in all_moments
            if m.metadata.get("opponent", "").lower() == opponent.lower()
        ]

    click.echo(f"Found {len(all_moments)} moments")

    # Display results
    for moment in all_moments:
        replay_name = moment.replay_path.name
        opp = moment.metadata.get("opponent", "unknown")
        stage = moment.metadata.get("stage", "unknown")
        tags_str = ", ".join(moment.tags)
        click.echo(
            f"  {replay_name}: frames {moment.frame_start}-{moment.frame_end} "
            f"vs {opp} on {stage} [{tags_str}]"
        )


@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Database path",
)
@click.pass_context
def capture(ctx: click.Context, tag: tuple[str, ...], output: Path, db: Path | None) -> None:
    """Capture video clips for matching moments."""
    cfg: Config = ctx.obj["config"]
    db_path = db or cfg.db_path
    database = MomentDatabase(db_path)

    # Find moments by tag
    all_moments: list[TaggedMoment] = []
    for t in tag:
        moments = database.find_moments_by_tag(t)
        all_moments.extend(moments)

    if not all_moments:
        click.echo("No moments found matching the specified tags.")
        return

    # Create subdirectory named after the searched tags
    tag_dirname = "_".join(t.replace(":", "-") for t in tag)
    output_dir = output / tag_dirname

    click.echo(f"Capturing {len(all_moments)} clips to {output_dir}")

    # Create DolphinConfig from loaded config
    dolphin_config = DolphinConfig(
        executable=cfg.dolphin_executable,
        user_dir=cfg.dolphin_user_dir,
        iso_path=cfg.iso_path,
    )

    pipeline = CapturePipeline(output_dir=output_dir, dolphin_config=dolphin_config)
    results = pipeline.capture_moments(all_moments)

    click.echo(f"Captured {len(results)} clips")
    for path in results:
        click.echo(f"  {path}")


@main.command("compile")
@click.argument("clips_dir", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
def compile_clips(clips_dir: Path, output: Path) -> None:
    """Compile clips into a single video."""
    # Find all mp4 files in directory
    clips = sorted(clips_dir.glob("*.mp4"))

    if not clips:
        click.echo(f"No .mp4 files found in {clips_dir}")
        return

    click.echo(f"Compiling {len(clips)} clips to {output}")

    compile_clips_fn(clips, output)

    click.echo(f"Compilation complete: {output}")


if __name__ == "__main__":
    main()
