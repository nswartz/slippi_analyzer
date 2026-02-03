# Integration Test Coverage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close test coverage gaps that allowed `-b` flag, `--output-directory` flag, and `configparser` INI corruption bugs to slip through.

**Architecture:** Fix existing unit tests to match updated code behavior (no `-b`, no `--output-directory`, no INI modifications). Add integration test that verifies actual frame dump creation with real Dolphin.

**Tech Stack:** pytest, subprocess, pathlib

---

## Background: What Went Wrong

Three bugs shipped because unit tests only verified code structure, not actual Dolphin behavior:

| Bug | Unit Test Said | Reality |
|-----|----------------|---------|
| `-b` flag | "Flag is in command ✓" | `-b` disables frame dumping |
| `--output-directory` | "Flag is in command ✓" | Conflicts with frame dumping |
| `configparser` INI | "DumpFrames = True in file ✓" | Dolphin can't read rewritten file |

---

### Task 1: Fix test_build_dolphin_command to match new behavior

**Files:**
- Modify: `tests/test_dolphin.py:33-51`

**Step 1: Update the test to expect NO `-b` flag by default**

The function signature changed from `batch_mode: bool = True` to `batch_mode: bool = False`, and we removed `output_dir` parameter.

```python
def test_build_dolphin_command() -> None:
    """Build correct Dolphin launch command.

    NOTE: Command must NOT include -b flag or --output-directory by default.
    These flags disable frame dumping in Slippi Playback.
    """
    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=Path("/home/user/.dolphin-slippi"),
        iso_path=Path("/games/melee.iso"),
    )

    cmd = build_dolphin_command(
        config=config,
        playback_config_path=Path("/home/user/.dolphin-slippi/Slippi/playback.txt"),
    )

    assert "/usr/bin/dolphin-emu" in cmd[0]
    assert "-u" in cmd  # User directory
    assert "-i" in cmd  # Playback config flag
    assert "--cout" in cmd  # Console output for frame tracking
    assert "--hide-seekbar" in cmd  # Hide seekbar during playback

    # CRITICAL: These flags break frame dumping and must NOT be present
    assert "-b" not in cmd, "-b batch mode flag disables frame dumping!"
    assert "--output-directory" not in cmd, "--output-directory flag conflicts with frame dumping!"
```

**Step 2: Run test to verify it fails (current code should pass)**

Run: `.venv/bin/pytest tests/test_dolphin.py::test_build_dolphin_command -v`
Expected: PASS (we already fixed the code)

**Step 3: Commit**

```bash
git add tests/test_dolphin.py
git commit -m "test(dolphin): fix command test to reject -b and --output-directory flags

These flags were silently breaking frame dumping. Tests now explicitly
verify they are NOT present in the default command.

Built with Claude Code"
```

---

### Task 2: Add test for explicit batch_mode=True behavior

**Files:**
- Modify: `tests/test_dolphin.py` (add after test_build_dolphin_command)

**Step 1: Write test documenting that batch_mode=True adds -b flag**

```python
def test_build_dolphin_command_batch_mode_adds_b_flag() -> None:
    """batch_mode=True adds -b flag (but disables frame dumping!).

    WARNING: Only use batch_mode=True for non-capture scenarios.
    The -b flag causes Dolphin to exit after replay but DISABLES frame dumping.
    """
    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=Path("/home/user/.dolphin-slippi"),
        iso_path=Path("/games/melee.iso"),
    )

    cmd = build_dolphin_command(
        config=config,
        playback_config_path=Path("/home/user/.dolphin-slippi/Slippi/playback.txt"),
        batch_mode=True,  # Explicitly enable batch mode
    )

    assert "-b" in cmd, "batch_mode=True should add -b flag"
```

**Step 2: Run test**

Run: `.venv/bin/pytest tests/test_dolphin.py::test_build_dolphin_command_batch_mode_adds_b_flag -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_dolphin.py
git commit -m "test(dolphin): document batch_mode=True adds -b flag with warning

Built with Claude Code"
```

---

### Task 3: Fix setup_frame_dump tests to match new behavior

**Files:**
- Modify: `tests/test_dolphin.py:54-147`

**Step 1: Rewrite setup_frame_dump tests**

The function no longer modifies INI files - it only creates directories and sets up Gecko codes. Update all tests to reflect this.

```python
def test_dolphin_controller_setup_frame_dump_creates_directories(tmp_path: Path) -> None:
    """setup_frame_dump creates Dump/Frames and Dump/Audio directories."""
    user_dir = tmp_path / "dolphin"
    user_dir.mkdir()

    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=user_dir,
    )

    controller = DolphinController(config)
    controller.setup_frame_dump(output_dir=tmp_path / "frames")

    # Should create Dump directories
    assert (user_dir / "Dump" / "Frames").exists()
    assert (user_dir / "Dump" / "Audio").exists()


def test_setup_frame_dump_does_not_modify_ini_files(tmp_path: Path) -> None:
    """setup_frame_dump must NOT modify GFX.ini or Dolphin.ini.

    Reason: configparser corrupts INI files in ways that break Dolphin's
    frame dumping. The user_dir should be pre-configured by copying from
    Slippi Launcher config.
    """
    user_dir = tmp_path / "dolphin"
    config_dir = user_dir / "Config"
    config_dir.mkdir(parents=True)

    # Create pre-existing INI files with known content
    gfx_ini = config_dir / "GFX.ini"
    dolphin_ini = config_dir / "Dolphin.ini"
    gfx_ini.write_text("[Settings]\nDumpFrames = True\n")
    dolphin_ini.write_text("[Movie]\nDumpFrames = True\n")

    original_gfx = gfx_ini.read_text()
    original_dolphin = dolphin_ini.read_text()

    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=user_dir,
    )

    controller = DolphinController(config)
    controller.setup_frame_dump(output_dir=tmp_path / "frames")

    # INI files must NOT be modified
    assert gfx_ini.read_text() == original_gfx, "GFX.ini was modified!"
    assert dolphin_ini.read_text() == original_dolphin, "Dolphin.ini was modified!"


def test_setup_frame_dump_creates_gecko_code_for_music_muting(tmp_path: Path) -> None:
    """setup_frame_dump creates Gecko code file when mute_music=True."""
    user_dir = tmp_path / "dolphin"
    user_dir.mkdir()

    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=user_dir,
        mute_music=True,
    )

    controller = DolphinController(config)
    controller.setup_frame_dump(output_dir=tmp_path / "frames")

    # Should create GameSettings/GALE01.ini with Gecko code
    gecko_ini = user_dir / "GameSettings" / "GALE01.ini"
    assert gecko_ini.exists(), "Gecko code file should be created"

    content = gecko_ini.read_text()
    assert "Netplay Safe Kill Music" in content
    assert "[Gecko]" in content
```

**Step 2: Run updated tests**

Run: `.venv/bin/pytest tests/test_dolphin.py -v -k "setup_frame_dump"`
Expected: Some may fail initially if tests exist with old expectations

**Step 3: Delete obsolete tests**

Remove these tests that expect INI modification:
- `test_setup_frame_dump_preserves_case`
- `test_setup_frame_dump_configures_dolphin_ini`
- `test_setup_frame_dump_disables_image_dump`

**Step 4: Run all dolphin tests**

Run: `.venv/bin/pytest tests/test_dolphin.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_dolphin.py
git commit -m "test(dolphin): update setup_frame_dump tests to match new behavior

setup_frame_dump no longer modifies INI files (configparser corrupts them).
It only creates directories and Gecko codes. Tests now verify:
- Dump directories are created
- INI files are NOT modified
- Gecko code is created for music muting

Built with Claude Code"
```

---

### Task 4: Create integration test for actual frame dump verification

**Files:**
- Create: `scripts/test_frame_dump.py`

**Step 1: Write the integration test script**

```python
#!/usr/bin/env python3
"""Integration test: verify Dolphin actually creates frame dump files.

Usage:
    .venv/bin/python scripts/test_frame_dump.py

This test:
1. Copies Slippi Launcher config to isolated directory
2. Runs Dolphin on a short replay segment (without -b flag)
3. Verifies framedump0.avi was created
4. Reports PASS/FAIL

Prerequisites:
- Slippi Launcher installed with playback configured
- At least one .slp replay file exists
- Melee ISO configured in ~/.config/slippi-clip/config.toml
"""

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_default_config_path, load_config


def find_shortest_replay(replay_dir: Path, limit: int = 10) -> Path | None:
    """Find a short replay for quick testing."""
    replays = list(replay_dir.glob("**/*.slp"))[:limit]
    if not replays:
        return None
    # Just return first one - actual duration check would require parsing
    return replays[0]


def main() -> int:
    print("=" * 60)
    print("FRAME DUMP INTEGRATION TEST")
    print("=" * 60)

    # Load config
    config_path = get_default_config_path()
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}")
        print("Run: slippi-clip setup")
        return 1

    config = load_config(config_path)
    print(f"\nConfig: {config_path}")
    print(f"  Dolphin: {config.dolphin_executable}")
    print(f"  ISO: {config.iso_path}")

    # Verify prerequisites
    if not config.dolphin_executable.exists():
        print(f"\nERROR: Dolphin not found: {config.dolphin_executable}")
        return 1

    if config.iso_path is None or not config.iso_path.exists():
        print(f"\nERROR: ISO not found: {config.iso_path}")
        return 1

    slippi_launcher_config = Path.home() / ".config" / "Slippi Launcher" / "playback" / "Config"
    if not slippi_launcher_config.exists():
        print(f"\nERROR: Slippi Launcher config not found: {slippi_launcher_config}")
        print("Install and configure Slippi Launcher first")
        return 1

    # Find a replay
    replay_dir = Path.home() / "Slippi"
    replay = find_shortest_replay(replay_dir)
    if replay is None:
        print(f"\nERROR: No replays found in {replay_dir}")
        return 1

    print(f"  Test replay: {replay}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        user_dir = temp_path / "dolphin"
        user_dir.mkdir()

        # Copy Slippi Launcher config (critical: don't modify with configparser!)
        config_dest = user_dir / "Config"
        shutil.copytree(slippi_launcher_config, config_dest)
        print(f"\nCopied config to: {user_dir}")

        # Create Dump directories
        (user_dir / "Dump" / "Frames").mkdir(parents=True)
        (user_dir / "Dump" / "Audio").mkdir(parents=True)

        # Create playback config for short segment (3 seconds = 180 frames)
        import json
        playback_config = user_dir / "Slippi" / "playback.txt"
        playback_config.parent.mkdir(parents=True, exist_ok=True)
        playback_config.write_text(json.dumps({
            "mode": "normal",
            "replay": str(replay.absolute()),
            "isRealTimeMode": False,
            "outputOverlayFiles": False,
            "startFrame": 0,
            "endFrame": 180,  # 3 seconds at 60fps
        }, indent=2))

        # Build command WITHOUT -b flag and WITHOUT --output-directory
        cmd = [
            str(config.dolphin_executable),
            "-u", str(user_dir),
            "-e", str(config.iso_path),
            "-i", str(playback_config),
            "--hide-seekbar",
            "--cout",
        ]

        print(f"\n{'=' * 60}")
        print("Running Dolphin (10 second timeout)...")
        print("=" * 60)
        print(f"Command: {' '.join(cmd[:6])}...")

        # Run Dolphin
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for frame dump or timeout
        video_file = user_dir / "Dump" / "Frames" / "framedump0.avi"
        start_time = time.time()
        timeout = 30  # 30 seconds max

        last_size = -1
        stable_count = 0

        while time.time() - start_time < timeout:
            if video_file.exists():
                current_size = video_file.stat().st_size
                if current_size > 0:
                    if current_size == last_size:
                        stable_count += 1
                        if stable_count >= 3:  # Stable for 3 checks
                            break
                    else:
                        stable_count = 0
                    last_size = current_size
            time.sleep(1)

        # Terminate Dolphin
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

        # Check results
        print(f"\n{'=' * 60}")
        print("RESULTS")
        print("=" * 60)

        if video_file.exists():
            size_kb = video_file.stat().st_size / 1024
            print(f"Frame dump created: {video_file}")
            print(f"  Size: {size_kb:.1f} KB")

            if size_kb > 100:  # Should be at least 100KB for 3 seconds
                print("\n*** TEST PASSED ***")
                print("Frame dumping works correctly without -b flag")
                return 0
            else:
                print(f"\nWARNING: File seems too small ({size_kb:.1f} KB)")
                print("May indicate partial dump")
                return 1
        else:
            print("ERROR: Frame dump NOT created!")
            print(f"  Expected: {video_file}")
            print("\nPossible causes:")
            print("  1. -b flag was included (disables frame dumping)")
            print("  2. --output-directory was included (conflicts with dumping)")
            print("  3. Dolphin.ini missing DumpFrames = True")
            print("  4. GFX.ini missing correct settings")
            print("\n*** TEST FAILED ***")
            return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Run the integration test**

Run: `.venv/bin/python scripts/test_frame_dump.py`
Expected: PASS (since we fixed the code)

**Step 3: Commit**

```bash
git add scripts/test_frame_dump.py
git commit -m "test(integration): add frame dump verification test

This test catches the bugs we shipped:
- Verifies frame dump file is created without -b flag
- Verifies --output-directory is not used
- Uses fresh Slippi Launcher config (not modified by configparser)

Run manually: .venv/bin/python scripts/test_frame_dump.py

Built with Claude Code"
```

---

### Task 5: Run full test suite and fix any regressions

**Step 1: Run pyright**

Run: `.venv/bin/pyright src/`
Expected: 0 errors

**Step 2: Run all unit tests**

Run: `.venv/bin/pytest tests/ -v`
Expected: All PASS

**Step 3: Run integration test**

Run: `.venv/bin/python scripts/test_frame_dump.py`
Expected: PASS

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address test suite regressions

Built with Claude Code"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `tests/test_dolphin.py` | Update tests to reject `-b` and `--output-directory`, verify INI files NOT modified |
| `scripts/test_frame_dump.py` | NEW: Integration test verifying actual frame dump creation |

## Gaps Closed

| Gap | Solution |
|-----|----------|
| `-b` flag silently disables dumping | Test explicitly asserts `-b` NOT in default command |
| `--output-directory` conflicts | Test explicitly asserts flag NOT in command |
| `configparser` corrupts INI | Test verifies INI files NOT modified; integration test uses real config |
