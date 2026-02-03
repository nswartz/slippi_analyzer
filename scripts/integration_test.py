#!/usr/bin/env python3
"""Integration test script for the capture pipeline.

Usage:
    .venv/bin/python scripts/integration_test.py [REPLAY_DIR]

This script:
1. Scans a replay directory for ledgehogs
2. Captures the first N detected moments
3. Reports timing and success/failure

Requires: Dolphin configured, ISO available, replay files
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.capture.dolphin import DolphinConfig
from src.capture.pipeline import CapturePipeline
from src.config import get_default_config_path, load_config
from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment
from src.scanner import ReplayScanner


def main() -> None:
    print("=" * 60)
    print("SLIPPI CLIP INTEGRATION TEST")
    print("=" * 60)

    # Load config
    config_path = get_default_config_path()
    config = load_config(config_path)
    print(f"\nConfig: {config_path}")
    print(f"  Dolphin: {config.dolphin_executable}")
    print(f"  ISO: {config.iso_path}")

    # Get replay directory from argument or use default
    if len(sys.argv) > 1:
        replay_dir = Path(sys.argv[1]).expanduser()
    else:
        replay_dir = Path.home() / "Slippi"

    print(f"  Replay dir: {replay_dir}")

    # Verify prerequisites
    if not config.dolphin_executable.exists():
        print(f"\nERROR: Dolphin executable not found: {config.dolphin_executable}")
        sys.exit(1)
    if config.iso_path is None or not config.iso_path.exists():
        print(f"\nERROR: ISO path not found: {config.iso_path}")
        sys.exit(1)
    if not replay_dir.exists():
        print(f"\nERROR: Replay directory not found: {replay_dir}")
        sys.exit(1)

    # Step 1: Scan for moments
    print("\n" + "-" * 60)
    print("STEP 1: Scanning for ledgehog moments...")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        registry = DetectorRegistry.with_default_detectors()
        scanner = ReplayScanner()

        # Find replays
        replays = list(replay_dir.glob("**/*.slp"))[:10]  # Limit to 10
        print(f"Found {len(replays)} replays to scan")

        moments: list[TaggedMoment] = []
        player_port = config.player_port  # Default to 0 if not configured
        for replay in replays:
            try:
                found = scanner.scan_replay(
                    replay_path=replay,
                    player_port=player_port,
                    registry=registry,
                )
                moments.extend(found)
                if found:
                    print(f"  {replay.name}: {len(found)} moments")
            except Exception as e:
                print(f"  {replay.name}: ERROR - {e}")

        print(f"\nTotal moments found: {len(moments)}")

        if not moments:
            print("\nNo moments found. Try scanning more replays or a different directory.")
            sys.exit(0)

        # Step 2: Capture clips
        print("\n" + "-" * 60)
        print("STEP 2: Capturing clips...")
        print("-" * 60)

        output_dir = Path(temp_dir) / "clips"
        output_dir.mkdir()

        dolphin_config = DolphinConfig(
            executable=config.dolphin_executable,
            user_dir=config.dolphin_user_dir,
            iso_path=config.iso_path,
        )

        pipeline = CapturePipeline(
            output_dir=output_dir,
            dolphin_config=dolphin_config,
        )

        # Capture first 2 moments (or all if fewer)
        to_capture = moments[:2]
        print(f"Capturing {len(to_capture)} clips...")

        start_time = time.time()
        results = pipeline.capture_moments(to_capture)
        elapsed = time.time() - start_time

        print(f"\nCapture complete in {elapsed:.1f}s")
        print(f"  Success: {len(results)}/{len(to_capture)}")

        for result in results:
            size_kb = result.stat().st_size / 1024
            print(f"  {result.name}: {size_kb:.0f} KB")

        # Summary
        print("\n" + "=" * 60)
        print("INTEGRATION TEST COMPLETE")
        print("=" * 60)
        if len(results) == len(to_capture):
            print("STATUS: PASS")
        else:
            print("STATUS: PARTIAL (some clips failed)")


if __name__ == "__main__":
    main()
