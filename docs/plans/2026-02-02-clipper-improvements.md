# Clipper Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up unused code, improve detection accuracy with technique classification, and optimize capture performance through GPU encoding and better parallelization.

**Architecture:** Four phases: (1) Code cleanup and hygiene, (2) Manual integration testing, (3) Detection enhancements with technique classification, (4) Performance optimizations. Each phase builds on the previous and can be tested independently.

**Tech Stack:** Python 3.14, pytest, ffmpeg with hardware acceleration, ThreadPoolExecutor, inotify/watchdog

---

## Phase 1: Code Cleanup

### Task 1: Remove Unused `get_xdg_cache_home()` Function

**Files:**
- Modify: `src/config.py:25-27`
- Test: `tests/test_config.py`

**Step 1: Verify function is unused**

Run: `grep -r "get_xdg_cache_home" src/ tests/`
Expected: Only definition in config.py, no usages

**Step 2: Remove the function**

Delete lines 25-27 from `src/config.py`:
```python
# DELETE THIS:
def get_xdg_cache_home() -> Path:
    """Get XDG cache home directory."""
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
```

**Step 3: Run tests to verify no breakage**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/config.py
git commit -m "chore: remove unused get_xdg_cache_home function"
```

---

### Task 2: Remove Unused `FFmpegEncoder.encode()` Method

**Files:**
- Modify: `src/capture/ffmpeg.py:96-129`
- Modify: `tests/test_ffmpeg.py`

**Step 1: Verify method is unused in production code**

Run: `grep -r "\.encode(" src/capture/ src/cli.py | grep -v "encode_avi"`
Expected: No results (only encode_avi and encode_avi_async are used)

**Step 2: Remove the unused encode method and build_encode_command**

In `src/capture/ffmpeg.py`, delete:
- `build_encode_command()` function (lines ~38-69)
- `FFmpegEncoder.encode()` method (lines ~96-129)

**Step 3: Remove tests for deleted functions**

In `tests/test_ffmpeg.py`, delete:
- `test_build_encode_command()`
- `test_build_encode_command_no_audio()`
- `test_ffmpeg_encoder_encode()`

**Step 4: Run remaining tests**

Run: `.venv/bin/pytest tests/test_ffmpeg.py -v`
Expected: PASS (remaining tests for encode_avi* should pass)

**Step 5: Commit**

```bash
git add src/capture/ffmpeg.py tests/test_ffmpeg.py
git commit -m "chore: remove unused PNG frame encoding (encode method)"
```

---

### Task 3: Remove Unused `crf` and `preset` Parameters

**Files:**
- Modify: `src/capture/ffmpeg.py`

**Step 1: Verify parameters are never passed**

Run: `grep -r "crf=" src/ && grep -r "preset=" src/`
Expected: Only in function signatures, never in calls

**Step 2: Remove unused parameters from build_avi_encode_command**

In `src/capture/ffmpeg.py`, modify `build_avi_encode_command()`:

```python
def build_avi_encode_command(
    video_file: Path,
    output_file: Path,
    audio_file: Path | None = None,
) -> list[str]:
    """Build ffmpeg command to encode AVI to MP4.

    Args:
        video_file: Path to input AVI file
        output_file: Path for output MP4 file
        audio_file: Optional path to WAV audio file

    Returns:
        List of command arguments for subprocess
    """
```

**Step 3: Remove unused parameters from encode_avi**

Modify `FFmpegEncoder.encode_avi()`:

```python
def encode_avi(
    self,
    video_file: Path,
    output_file: Path,
    audio_file: Path | None = None,
) -> None:
    """Encode AVI video to MP4.

    Args:
        video_file: Path to Dolphin's frame dump AVI
        output_file: Path for output MP4 file
        audio_file: Optional path to audio file
    """
```

**Step 4: Remove unused parameters from encode_avi_async**

Modify `FFmpegEncoder.encode_avi_async()`:

```python
def encode_avi_async(
    self,
    video_file: Path,
    output_file: Path,
    audio_file: Path | None = None,
) -> Future[None]:
    """Encode AVI video to MP4 asynchronously.

    Returns immediately with a Future that completes when encoding finishes.

    Args:
        video_file: Path to Dolphin's frame dump AVI
        output_file: Path for output MP4 file
        audio_file: Optional path to audio file

    Returns:
        Future that resolves when encoding completes
    """
```

**Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_ffmpeg.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/capture/ffmpeg.py
git commit -m "chore: remove unused crf/preset parameters from encode functions"
```

---

### Task 4: Fix Duplicate Imports in dolphin.py

**Files:**
- Modify: `src/capture/dolphin.py`

**Step 1: Identify duplicate imports**

Run: `grep -n "import time" src/capture/dolphin.py && grep -n "import shutil" src/capture/dolphin.py`
Expected: time at line 7 and ~150; shutil at ~605

**Step 2: Remove inline import of time**

Find the `_mute_dolphin_audio` method and remove the local `import time` (it's already imported at module level).

**Step 3: Move shutil import to top of file**

Add `import shutil` to the imports section at the top of the file, then remove the inline import in `copy_output_files()`.

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_dolphin.py -v`
Expected: PASS

**Step 5: Run pyright**

Run: `.venv/bin/pyright src/capture/dolphin.py`
Expected: 0 errors

**Step 6: Commit**

```bash
git add src/capture/dolphin.py
git commit -m "chore: consolidate duplicate imports in dolphin.py"
```

---

### Task 5: Archive Completed Plan Documents

**Files:**
- Move: `docs/plans/2026-01-31-implementation-plan.md` -> `docs/plans/archive/`
- Move: `docs/plans/2026-01-31-slippi-replay-clipper-design.md` -> `docs/plans/archive/`

**Step 1: Create archive directory**

```bash
mkdir -p docs/plans/archive
```

**Step 2: Move completed plans to archive**

```bash
git mv docs/plans/2026-01-31-implementation-plan.md docs/plans/archive/
git mv docs/plans/2026-01-31-slippi-replay-clipper-design.md docs/plans/archive/
```

**Step 3: Commit**

```bash
git commit -m "docs: archive completed implementation plans"
```

---

## Phase 2: Manual Integration Testing

### Task 6: Create Integration Test Script

**Files:**
- Create: `scripts/integration_test.py`

**Goal:** A script to manually test the full capture pipeline with real replays.

**Step 1: Write the integration test script**

```python
#!/usr/bin/env python3
"""Integration test script for the capture pipeline.

Usage:
    .venv/bin/python scripts/integration_test.py

This script:
1. Scans a replay directory for ledgehogs
2. Captures the first N detected moments
3. Reports timing and success/failure

Requires: Dolphin configured, ISO available, replay files in ~/Slippi/
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.capture.dolphin import DolphinConfig, DolphinController
from src.capture.ffmpeg import FFmpegEncoder
from src.capture.pipeline import CapturePipeline
from src.config import get_default_config_path, load_config
from src.database import MomentDatabase
from src.detectors.registry import DetectorRegistry
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
    print(f"  Replay dir: {config.replay_dir}")

    # Verify prerequisites
    if not config.dolphin_executable or not config.dolphin_executable.exists():
        print("\nERROR: Dolphin executable not found")
        sys.exit(1)
    if not config.iso_path or not config.iso_path.exists():
        print("\nERROR: ISO path not found")
        sys.exit(1)

    # Step 1: Scan for moments
    print("\n" + "-" * 60)
    print("STEP 1: Scanning for ledgehog moments...")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        db = MomentDatabase(db_path)
        registry = DetectorRegistry.with_default_detectors()
        scanner = ReplayScanner(registry)

        # Find replays
        replays = list(config.replay_dir.glob("**/*.slp"))[:10]  # Limit to 10
        print(f"Found {len(replays)} replays to scan")

        moments = []
        for replay in replays:
            try:
                found = scanner.scan_replay(
                    replay,
                    player_codes=config.player_tags,
                )
                moments.extend(found)
                if found:
                    print(f"  {replay.name}: {len(found)} moments")
            except Exception as e:
                print(f"  {replay.name}: ERROR - {e}")

        print(f"\nTotal moments found: {len(moments)}")

        if not moments:
            print("\nNo moments found. Try scanning more replays.")
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
```

**Step 2: Test the script runs**

Run: `.venv/bin/python scripts/integration_test.py`
Expected: Script executes, scans replays, attempts captures

**Step 3: Commit**

```bash
git add scripts/integration_test.py
git commit -m "test: add integration test script for capture pipeline"
```

---

## Phase 3: Detection Enhancements

### Task 7: Add Facing Direction to FrameData

**Files:**
- Modify: `src/detectors/base.py`
- Modify: `src/scanner.py`
- Test: `tests/test_scanner.py`

**Step 1: Write the failing test**

Add to `tests/test_scanner.py`:

```python
def test_frame_data_tracks_facing_direction(sample_replay: Path) -> None:
    """FrameData should include player and opponent facing direction."""
    frames = parse_replay_to_frames(sample_replay, player_port=0, opponent_port=1)

    # Check that facing direction is present
    assert hasattr(frames[0], "player_facing")
    assert hasattr(frames[0], "opponent_facing")

    # Facing should be -1 (left) or 1 (right)
    assert frames[0].player_facing in (-1, 1)
    assert frames[0].opponent_facing in (-1, 1)
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_scanner.py::test_frame_data_tracks_facing_direction -v`
Expected: FAIL with AttributeError

**Step 3: Add facing fields to FrameData**

In `src/detectors/base.py`, modify the `FrameData` dataclass:

```python
@dataclass
class FrameData:
    """Frame data extracted from a Slippi replay for detection."""

    frame_number: int
    player_x: float
    player_y: float
    player_action_state: int
    player_stocks: int
    player_facing: int  # 1 = right, -1 = left
    opponent_x: float
    opponent_y: float
    opponent_action_state: int
    opponent_stocks: int
    opponent_facing: int  # 1 = right, -1 = left
    stage_id: int
```

**Step 4: Extract facing direction in scanner.py**

In `src/scanner.py`, modify `parse_replay_to_frames()` to extract facing:

```python
# In the frame loop, after getting post_frame data:
player_facing = 1 if player_post.direction.value > 0 else -1
opponent_facing = 1 if opponent_post.direction.value > 0 else -1

frame_data = FrameData(
    frame_number=frame.index,
    player_x=player_post.position.x,
    player_y=player_post.position.y,
    player_action_state=player_post.state.value,
    player_stocks=player_post.stocks,
    player_facing=player_facing,
    opponent_x=opponent_post.position.x,
    opponent_y=opponent_post.position.y,
    opponent_action_state=opponent_post.state.value,
    opponent_stocks=opponent_post.stocks,
    opponent_facing=opponent_facing,
    stage_id=stage_id,
)
```

**Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_scanner.py::test_frame_data_tracks_facing_direction -v`
Expected: PASS

**Step 6: Run all scanner tests**

Run: `.venv/bin/pytest tests/test_scanner.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/detectors/base.py src/scanner.py tests/test_scanner.py
git commit -m "feat(scanner): add facing direction to FrameData"
```

---

### Task 8: Add Technique Classification to Ledgehog Detector

**Files:**
- Modify: `src/detectors/ledgehog.py`
- Test: `tests/test_ledgehog_detector.py`

**Goal:** Classify ledgehogs by technique used to grab the ledge:
- `ledgehog:recovery` - Player grabbed ledge from offstage (own recovery)
- `ledgehog:wavedash` - Player wavedashed to ledge (facing stage)
- `ledgehog:ramen` - Player fastfell to ledge (facing away from stage, "ramen noodles")
- `ledgehog:jump` - Player jumped to ledge from stage
- `ledgehog:hit` - Player was hit into ledge

**Step 1: Define action state constants for technique detection**

Add to `src/detectors/ledgehog.py`:

```python
# Action states for technique classification
LAND_FALL_SPECIAL = 43  # Landing from special fall
AIRDODGE = 236  # Airdodge (wavedash component)
ESCAPE_AIR = 236  # Same as airdodge
FALL = 30  # Regular falling
FALL_AERIAL = 31  # Falling after aerial
FALL_SPECIAL = 35  # Special fall (up-B used)
JUMP_F = 24  # Forward jump
JUMP_B = 25  # Backward jump
KNEE_BEND = 23  # Jump squat
```

**Step 2: Write failing test for technique classification**

Add to `tests/test_ledgehog_detector.py`:

```python
def test_ledgehog_classifies_recovery_technique() -> None:
    """Ledgehog from player's own recovery should be tagged as ledgehog:recovery."""
    # Player starts offstage, recovers to ledge
    frames = [
        # Frame 0: Player offstage in FALL_SPECIAL (using recovery)
        make_frame(
            frame=0,
            player_x=-80.0, player_y=-20.0,
            player_action=FALL_SPECIAL,
            player_facing=-1,  # Facing away from stage
            opponent_x=0.0, opponent_y=0.0,
            opponent_action=STANDING,
        ),
        # Frame 30: Player grabs ledge from recovery
        make_frame(
            frame=30,
            player_x=-68.4, player_y=-20.0,
            player_action=CLIFF_CATCH,
            player_facing=1,  # Now facing stage
            opponent_x=20.0, opponent_y=50.0,  # Opponent offstage
            opponent_action=FALL_SPECIAL,
        ),
        # ... opponent approaches and dies ...
    ]

    # ... complete the test setup ...

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:recovery" in moments[0].tags
```

**Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ledgehog_detector.py::test_ledgehog_classifies_recovery_technique -v`
Expected: FAIL

**Step 4: Implement technique classification**

In `src/detectors/ledgehog.py`, add technique detection method:

```python
def _classify_ledge_technique(
    self,
    frames: list[FrameData],
    grab_frame_idx: int,
) -> str:
    """Classify the technique used to grab the ledge.

    Looks at player state before the grab to determine technique.

    Returns:
        Tag suffix: "recovery", "wavedash", "ramen", "jump", or "hit"
    """
    if grab_frame_idx < 5:
        return "jump"  # Not enough history, assume jump

    # Look at the 30 frames before grab
    lookback = min(30, grab_frame_idx)
    pre_grab_frames = frames[grab_frame_idx - lookback:grab_frame_idx]

    grab_frame = frames[grab_frame_idx]
    edge_x = STAGE_EDGES.get(grab_frame.stage_id, 68.4)
    player_side = 1 if grab_frame.player_x > 0 else -1  # 1=right edge, -1=left edge

    # Check if player was in FALL_SPECIAL before grab (recovery)
    was_in_fall_special = any(
        f.player_action_state == FALL_SPECIAL for f in pre_grab_frames[-15:]
    )

    # Check if player was hit recently (damage states)
    was_hit = any(
        f.player_action_state in DAMAGE_STATES for f in pre_grab_frames[-30:]
    )

    # Check for airdodge (wavedash/ramen)
    had_airdodge = any(
        f.player_action_state == AIRDODGE for f in pre_grab_frames[-10:]
    )

    # Check player position history - were they on stage before?
    was_on_stage = any(
        abs(f.player_x) < edge_x - 10 and f.player_y > 0
        for f in pre_grab_frames[-30:]
    )

    if was_hit:
        return "hit"
    elif was_in_fall_special and not was_on_stage:
        return "recovery"
    elif had_airdodge and was_on_stage:
        # Wavedash vs ramen: check facing relative to stage
        # Ramen = facing away from stage when grabbing
        facing_away = (player_side * grab_frame.player_facing) < 0
        return "ramen" if facing_away else "wavedash"
    else:
        return "jump"
```

**Step 5: Update detect() to add technique tag**

In the `detect()` method, after creating the moment, add the technique tag:

```python
# After detecting a valid ledgehog, classify technique
technique = self._classify_ledge_technique(frames, grab_frame_idx)
tags.append(f"ledgehog:{technique}")
```

**Step 6: Run tests**

Run: `.venv/bin/pytest tests/test_ledgehog_detector.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/detectors/ledgehog.py tests/test_ledgehog_detector.py
git commit -m "feat(detector): classify ledgehog technique (recovery/wavedash/ramen/jump/hit)"
```

---

## Phase 4: Performance Optimizations

### Task 9: Increase FFmpeg Thread Pool Size

**Files:**
- Modify: `src/capture/ffmpeg.py`
- Test: `tests/test_ffmpeg.py`

**Step 1: Make worker count configurable**

In `src/capture/ffmpeg.py`, modify `FFmpegEncoder`:

```python
class FFmpegEncoder:
    """FFmpeg encoder for video files."""

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize the encoder.

        Args:
            max_workers: Maximum concurrent encoding threads (default: 4)
        """
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor for async encoding."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        return self._executor
```

**Step 2: Write test for configurable workers**

Add to `tests/test_ffmpeg.py`:

```python
def test_ffmpeg_encoder_respects_max_workers() -> None:
    """FFmpegEncoder should use configured max_workers."""
    encoder = FFmpegEncoder(max_workers=8)
    executor = encoder._get_executor()
    assert executor._max_workers == 8
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_ffmpeg.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/capture/ffmpeg.py tests/test_ffmpeg.py
git commit -m "feat(ffmpeg): make encoder thread pool size configurable"
```

---

### Task 10: Add GPU-Accelerated Encoding Option

**Files:**
- Modify: `src/capture/ffmpeg.py`
- Test: `tests/test_ffmpeg.py`

**Goal:** Support hardware-accelerated encoding (NVENC, VAAPI, QSV) when available.

**Step 1: Add hardware encoder detection**

In `src/capture/ffmpeg.py`, add:

```python
def detect_hardware_encoder() -> str | None:
    """Detect available hardware encoder.

    Returns:
        Encoder name (h264_nvenc, h264_vaapi, h264_qsv) or None if unavailable.
    """
    # Check for NVIDIA NVENC
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "h264_nvenc" in result.stdout:
            return "h264_nvenc"
        if "h264_vaapi" in result.stdout:
            return "h264_vaapi"
        if "h264_qsv" in result.stdout:
            return "h264_qsv"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None
```

**Step 2: Modify build_avi_encode_command for hardware encoding**

```python
def build_avi_encode_command(
    video_file: Path,
    output_file: Path,
    audio_file: Path | None = None,
    hardware_encoder: str | None = None,
) -> list[str]:
    """Build ffmpeg command to encode AVI to MP4.

    Args:
        video_file: Path to input AVI file
        output_file: Path for output MP4 file
        audio_file: Optional path to WAV audio file
        hardware_encoder: Optional hardware encoder (h264_nvenc, etc.)

    Returns:
        List of command arguments for subprocess
    """
    cmd = ["ffmpeg", "-y", "-i", str(video_file)]

    if audio_file:
        cmd.extend(["-i", str(audio_file)])

    # Video encoding settings
    if hardware_encoder == "h264_nvenc":
        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "8M"])
    elif hardware_encoder == "h264_vaapi":
        cmd.extend([
            "-vaapi_device", "/dev/dri/renderD128",
            "-c:v", "h264_vaapi", "-b:v", "8M"
        ])
    elif hardware_encoder == "h264_qsv":
        cmd.extend(["-c:v", "h264_qsv", "-preset", "medium", "-b:v", "8M"])
    else:
        # Software fallback (libopenh264)
        cmd.extend(["-c:v", "libopenh264", "-b:v", "8M"])

    # Audio settings
    if audio_file:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.append(str(output_file))
    return cmd
```

**Step 3: Add hardware encoder to FFmpegEncoder**

```python
class FFmpegEncoder:
    """FFmpeg encoder for video files."""

    def __init__(
        self,
        max_workers: int = 4,
        use_hardware: bool = True,
    ) -> None:
        """Initialize the encoder.

        Args:
            max_workers: Maximum concurrent encoding threads
            use_hardware: Try to use hardware encoding if available
        """
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None
        self._hardware_encoder: str | None = None

        if use_hardware:
            self._hardware_encoder = detect_hardware_encoder()
            if self._hardware_encoder:
                print(f"Using hardware encoder: {self._hardware_encoder}")
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_ffmpeg.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capture/ffmpeg.py tests/test_ffmpeg.py
git commit -m "feat(ffmpeg): add GPU-accelerated encoding support"
```

---

### Task 11: Add File Monitoring with Watchdog (Optional)

**Files:**
- Create: `src/capture/file_monitor.py`
- Test: `tests/test_file_monitor.py`

**Goal:** Replace polling-based frame dump detection with inotify-based monitoring for faster response.

**Step 1: Write the failing test**

Create `tests/test_file_monitor.py`:

```python
import tempfile
import threading
import time
from pathlib import Path

from src.capture.file_monitor import wait_for_file_stable


def test_wait_for_file_stable_detects_completion(tmp_path: Path) -> None:
    """wait_for_file_stable should return when file stops growing."""
    test_file = tmp_path / "test.avi"

    # Simulate file being written
    def write_file():
        with open(test_file, "wb") as f:
            for _ in range(5):
                f.write(b"x" * 1000)
                f.flush()
                time.sleep(0.1)

    writer = threading.Thread(target=write_file)
    writer.start()

    # Wait a bit for file to exist
    time.sleep(0.05)

    # This should return after file stops growing
    result = wait_for_file_stable(test_file, stable_seconds=0.3, timeout=5.0)

    writer.join()

    assert result is True
    assert test_file.stat().st_size == 5000
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_file_monitor.py -v`
Expected: FAIL (module doesn't exist)

**Step 3: Implement file monitor**

Create `src/capture/file_monitor.py`:

```python
"""File monitoring utilities for capture pipeline."""

import time
from pathlib import Path


def wait_for_file_stable(
    file_path: Path,
    stable_seconds: float = 2.0,
    timeout: float = 300.0,
    check_interval: float = 0.1,
) -> bool:
    """Wait for a file to stop growing.

    Uses polling with configurable interval. For systems with inotify,
    consider using watchdog library for better performance.

    Args:
        file_path: Path to monitor
        stable_seconds: How long file must be unchanged to consider complete
        timeout: Maximum time to wait
        check_interval: How often to check file size

    Returns:
        True if file stabilized, False if timeout
    """
    start_time = time.time()
    last_size = -1
    stable_since: float | None = None

    while time.time() - start_time < timeout:
        if not file_path.exists():
            time.sleep(check_interval)
            continue

        current_size = file_path.stat().st_size

        if current_size == last_size:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= stable_seconds:
                return True
        else:
            stable_since = None
            last_size = current_size

        time.sleep(check_interval)

    return False
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_file_monitor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capture/file_monitor.py tests/test_file_monitor.py
git commit -m "feat(capture): add file stability monitor utility"
```

---

## Summary

### Phase 1: Code Cleanup (Tasks 1-5)
- Remove unused `get_xdg_cache_home()` function
- Remove unused `FFmpegEncoder.encode()` method
- Remove unused `crf`/`preset` parameters
- Fix duplicate imports in dolphin.py
- Archive completed plan documents

### Phase 2: Manual Integration Testing (Task 6)
- Create integration test script for real-world validation

### Phase 3: Detection Enhancements (Tasks 7-8)
- Add facing direction to FrameData
- Implement technique classification for ledgehogs

### Phase 4: Performance Optimizations (Tasks 9-11)
- Make FFmpeg thread pool configurable
- Add GPU-accelerated encoding support
- Add file monitoring utility

### Expected Outcomes
- Cleaner, more maintainable codebase
- Richer detection tags for ledgehog classification
- 2-5x faster encoding with GPU acceleration
- Foundation for future detection enhancements

---

## References

- [py-slippi documentation](https://py-slippi.readthedocs.io/)
- [FFmpeg hardware acceleration](https://trac.ffmpeg.org/wiki/HWAccelIntro)
- [NVIDIA NVENC](https://developer.nvidia.com/nvidia-video-codec-sdk)
