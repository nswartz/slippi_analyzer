#!/usr/bin/env python3
"""Test if updating commandId reloads replay without restarting Dolphin.

Usage:
    .venv/bin/python scripts/test_command_id_reload.py REPLAY1.slp REPLAY2.slp

This script:
1. Launches Dolphin with REPLAY1 (frames 0-300)
2. Waits 10 seconds for playback
3. Updates playback.txt with REPLAY2 and new commandId
4. Waits another 10 seconds

Watch the Dolphin window - if it switches to REPLAY2 without restarting,
commandId reload works and we can implement persistent sessions.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

# Add src to path for config loading
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_default_config_path, load_config


def write_playback_config(
    output_path: Path,
    replay_path: Path,
    command_id: str,
    start_frame: int = 0,
    end_frame: int = 300,
) -> None:
    """Write Slippi playback configuration file with commandId."""
    config = {
        "mode": "normal",
        "replay": str(replay_path.absolute()),
        "startFrame": start_frame,
        "endFrame": end_frame,
        "commandId": command_id,
        "isRealTimeMode": False,
        "outputOverlayFiles": False,
    }
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Wrote playback config: {output_path}")
    print(f"  replay: {replay_path}")
    print(f"  commandId: {command_id}")
    print(f"  frames: {start_frame}-{end_frame}")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    replay1 = Path(sys.argv[1]).expanduser().absolute()
    replay2 = Path(sys.argv[2]).expanduser().absolute()

    if not replay1.exists():
        print(f"Error: Replay 1 not found: {replay1}")
        sys.exit(1)
    if not replay2.exists():
        print(f"Error: Replay 2 not found: {replay2}")
        sys.exit(1)

    # Load config
    config_path = get_default_config_path()
    config = load_config(config_path)

    print(f"Using config from: {config_path}")
    print(f"Dolphin executable: {config.dolphin_executable}")
    print(f"Dolphin user dir: {config.dolphin_user_dir}")
    print(f"ISO path: {config.iso_path}")
    print()

    if config.dolphin_user_dir is None:
        print("Error: dolphin_user_dir not configured")
        sys.exit(1)

    # Ensure Slippi directory exists
    slippi_dir = config.dolphin_user_dir / "Slippi"
    slippi_dir.mkdir(parents=True, exist_ok=True)
    playback_config_path = slippi_dir / "playback.txt"

    # Step 1: Write config for first replay
    print("=" * 60)
    print("STEP 1: Launching Dolphin with REPLAY1")
    print("=" * 60)
    write_playback_config(
        output_path=playback_config_path,
        replay_path=replay1,
        command_id="test-cmd-001",
        start_frame=0,
        end_frame=600,  # ~10 seconds
    )

    # Build Dolphin command
    cmd = [str(config.dolphin_executable)]
    if config.dolphin_user_dir:
        cmd.extend(["-u", str(config.dolphin_user_dir)])
    if config.iso_path:
        cmd.extend(["-e", str(config.iso_path)])
    cmd.extend([
        "-i", str(playback_config_path),
        # Note: NOT using -b (batch mode) so we can observe
        "--hide-seekbar",
    ])

    print(f"\nLaunching: {' '.join(cmd)}")
    print("\n>>> WATCH THE DOLPHIN WINDOW <<<")
    print()

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print("Waiting 8 seconds for Replay 1 to play...")
    time.sleep(8)

    # Step 2: Update config with new commandId
    print()
    print("=" * 60)
    print("STEP 2: Updating playback.txt with REPLAY2 and new commandId")
    print("=" * 60)
    write_playback_config(
        output_path=playback_config_path,
        replay_path=replay2,
        command_id="test-cmd-002",  # NEW commandId should trigger reload
        start_frame=0,
        end_frame=600,
    )

    print()
    print(">>> DID THE REPLAY SWITCH? <<<")
    print("  - If YES: commandId reload works! We can implement persistent sessions.")
    print("  - If NO: commandId doesn't trigger reload. Need to restart Dolphin per clip.")
    print()

    print("Waiting 10 more seconds to observe...")
    time.sleep(10)

    # Cleanup
    print("\nTerminating Dolphin...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    print("Done.")
    print()
    print("=" * 60)
    print("RESULT: Did the replay switch when commandId changed?")
    print("  YES -> We can implement persistent Dolphin sessions (Task 4 & 5)")
    print("  NO  -> Skip to finishing; restart-per-clip is required")
    print("=" * 60)


if __name__ == "__main__":
    main()
