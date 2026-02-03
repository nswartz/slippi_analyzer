# Dolphin Capture Improvements

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix first-clip minimize issue, improve focus restoration timing, and investigate keeping Dolphin running across captures.

**Architecture:** Three improvements: (1) Fix race condition where first Dolphin window appears before minimizer thread is polling. (2) Capture active window RIGHT BEFORE each individual capture starts, not at session start. (3) Explore using Slippi's `commandId` field to reload replays without restarting Dolphin.

**Tech Stack:** Python subprocess, xdotool, Slippi playback JSON protocol

---

## Issue Analysis

### Issue 1: First Clip Doesn't Minimize

**Root cause:** The window minimizer thread starts just before `subprocess.Popen()`, but there's a race condition. The thread polls every 50ms, but Dolphin's window can appear and steal focus before the first poll completes.

**Solution:** Add an explicit initial minimize attempt with `--sync` flag AFTER starting Dolphin, before entering the polling loop. The `--sync` flag waits for the window to exist.

### Issue 2: Focus Returns to Wrong Window

**Root cause:** `_original_window` is captured in `start_capture()`, which is called per-capture. But `CapturePipeline.capture_moments()` iterates through moments, so by the time clip 2 starts, the "original window" is whatever was focused after clip 1 finished (often nothing useful).

**Solution:** Capture the active window immediately before calling `start_capture()`, not at some earlier point. This ensures we always return focus to whatever the user was working in RIGHT BEFORE that specific capture.

### Issue 3: Dolphin Restart Overhead

**Root cause:** Current pipeline closes and reopens Dolphin for every clip. This is slow and causes repeated focus stealing.

**Solution:** Use Slippi's `commandId` field in the playback JSON. Updating `commandId` with a new value triggers Dolphin to reload the replay without restarting. This allows:
- Launch Dolphin once at start of batch
- Minimize it once
- Update playback.txt with new replay + new commandId
- Wait for frame dump to complete
- Repeat for next clip

---

## Phase 1: Fix First-Clip Minimize Race Condition

### Task 1: Add Initial Sync Minimize After Dolphin Launch

**Files:**
- Modify: `src/capture/dolphin.py:376-424` (start_capture method)
- Test: `tests/test_dolphin.py`

**Step 1: Write failing test for initial minimize behavior**

```python
# tests/test_dolphin.py - add test
from unittest.mock import MagicMock, patch, call
import threading
import time

def test_start_capture_minimizes_window_before_polling_starts() -> None:
    """First Dolphin window should be minimized with --sync before polling."""
    config = DolphinConfig(
        executable=Path("/usr/bin/echo"),  # Mock executable
        user_dir=Path("/tmp/test-dolphin"),
        iso_path=Path("/tmp/test.iso"),
    )
    controller = DolphinController(config)

    # Track subprocess.run calls to verify order
    run_calls: list[list[str]] = []

    def mock_run(cmd: list[str], **kwargs) -> MagicMock:
        run_calls.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stdout = "12345"  # Fake window ID
        return result

    with patch("subprocess.run", side_effect=mock_run):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()

            # Create minimal required files
            Path("/tmp/test-dolphin/Slippi").mkdir(parents=True, exist_ok=True)

            controller.start_capture(
                replay_path=Path("/tmp/test.slp"),
                output_dir=Path("/tmp/output"),
            )

            # Stop the minimizer thread
            controller._stop_window_minimizer()

    # Verify xdotool search --sync was called (initial minimize attempt)
    sync_search_calls = [
        c for c in run_calls
        if "xdotool" in c and "--sync" in c and "search" in c
    ]
    assert len(sync_search_calls) >= 1, "Should have at least one --sync search call"
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_dolphin.py::test_start_capture_minimizes_window_before_polling_starts -v`
Expected: FAIL (current code doesn't do sync search in start_capture)

**Step 3: Implement initial sync minimize**

```python
# src/capture/dolphin.py - modify start_capture method

def start_capture(
    self,
    replay_path: Path,
    output_dir: Path,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> None:
    """Start Dolphin for frame capture."""
    self.setup_frame_dump(output_dir)

    # Create playback config file
    if self.config.user_dir is None:
        raise ValueError("user_dir must be set for playback config")

    playback_config_path = self.config.user_dir / "Slippi" / "playback.txt"
    playback_config_path.parent.mkdir(parents=True, exist_ok=True)

    create_playback_config(
        replay_path=replay_path,
        output_path=playback_config_path,
        start_frame=start_frame,
        end_frame=end_frame,
    )

    cmd = build_dolphin_command(
        config=self.config,
        playback_config_path=playback_config_path,
        output_dir=output_dir,
    )

    # Save current window for focus restoration
    self._original_window = self._get_active_window()

    # Start background thread to minimize windows as they appear
    self._start_window_minimizer()

    # Launch Dolphin
    self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

    # IMMEDIATELY minimize first window with --sync (waits for window to exist)
    # This catches the first window before the polling loop can miss it
    self._minimize_dolphin_window()

    # Mute Dolphin audio output
    self._mute_dolphin_audio()
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_dolphin.py::test_start_capture_minimizes_window_before_polling_starts -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capture/dolphin.py tests/test_dolphin.py
git commit -m "fix: minimize first Dolphin window with --sync before polling loop"
```

---

## Phase 2: Fix Focus Restoration Timing

### Task 2: Capture Active Window Per-Capture in Pipeline

**Files:**
- Modify: `src/capture/dolphin.py:376-424` (start_capture method)
- Modify: `src/capture/pipeline.py:27-77` (capture_moment method)
- Test: `tests/test_pipeline.py`

**Step 1: Write failing test for per-capture focus capture**

```python
# tests/test_pipeline.py - add test
from unittest.mock import MagicMock, patch, PropertyMock

def test_capture_moment_gets_active_window_immediately_before_start() -> None:
    """Active window should be captured right before Dolphin starts, not earlier."""

    # Track when _get_active_window is called relative to start_capture
    call_order: list[str] = []

    original_start_capture = DolphinController.start_capture

    def mock_start_capture(self, *args, **kwargs):
        call_order.append("start_capture_begin")
        # Don't actually run Dolphin

    def mock_get_active_window(self):
        call_order.append("get_active_window")
        return "12345"

    with patch.object(DolphinController, "start_capture", mock_start_capture):
        with patch.object(DolphinController, "_get_active_window", mock_get_active_window):
            with patch.object(DolphinController, "wait_for_completion", return_value=0):
                with patch.object(FFmpegEncoder, "encode_avi"):
                    pipeline = CapturePipeline(
                        output_dir=Path("/tmp/clips"),
                        dolphin_config=DolphinConfig(),
                    )

                    moment = TaggedMoment(
                        replay_path=Path("/tmp/test.slp"),
                        frame_start=100,
                        frame_end=200,
                        tags=["test"],
                        metadata={},
                    )

                    # This should call get_active_window RIGHT BEFORE start_capture
                    pipeline.capture_moment(moment, index=1)

    # Verify order: get_active_window should be immediately before start_capture
    assert "get_active_window" in call_order
    assert "start_capture_begin" in call_order
    # get_active_window should come just before start_capture
    gaw_idx = call_order.index("get_active_window")
    sc_idx = call_order.index("start_capture_begin")
    assert gaw_idx < sc_idx, "get_active_window must be called before start_capture"
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline.py::test_capture_moment_gets_active_window_immediately_before_start -v`
Expected: FAIL (current code captures window inside start_capture, not in pipeline)

**Step 3: Refactor to capture window in pipeline before start_capture**

The key insight: `_get_active_window()` is currently called inside `start_capture()`. We need to either:
- A) Add a parameter to pass the window ID into start_capture
- B) Expose a method to set the original window before calling start_capture

Option A is cleaner:

```python
# src/capture/dolphin.py - modify start_capture signature

def start_capture(
    self,
    replay_path: Path,
    output_dir: Path,
    start_frame: int | None = None,
    end_frame: int | None = None,
    restore_window: str | None = None,  # NEW: window to restore focus to
) -> None:
    """Start Dolphin for frame capture.

    Args:
        replay_path: Path to replay file
        output_dir: Directory for output frames
        start_frame: Optional start frame for capture
        end_frame: Optional end frame for capture
        restore_window: Optional window ID to restore focus to after minimize
    """
    self.setup_frame_dump(output_dir)

    # ... existing playback config setup ...

    # Use provided window ID or capture current
    self._original_window = restore_window or self._get_active_window()

    # ... rest of method unchanged ...
```

```python
# src/capture/pipeline.py - modify capture_moment

def capture_moment(
    self,
    moment: TaggedMoment,
    index: int,
) -> Path | None:
    """Capture a single moment as a video clip."""
    # Capture active window RIGHT BEFORE starting Dolphin
    # This ensures we return focus to whatever user was working in
    active_window = self._dolphin._get_active_window()

    with tempfile.TemporaryDirectory() as temp_dir:
        frame_dir = Path(temp_dir) / "frames"
        frame_dir.mkdir()

        self._dolphin.start_capture(
            replay_path=moment.replay_path,
            output_dir=frame_dir,
            start_frame=moment.frame_start,
            end_frame=moment.frame_end,
            restore_window=active_window,  # Pass captured window
        )

        # ... rest unchanged ...
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_pipeline.py::test_capture_moment_gets_active_window_immediately_before_start -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capture/dolphin.py src/capture/pipeline.py tests/test_pipeline.py
git commit -m "fix: capture active window right before each Dolphin launch"
```

---

## Phase 3: Persistent Dolphin Session (Investigation)

### Task 3: Research Slippi commandId Reload Behavior

**Goal:** Determine if Dolphin can reload replays via `commandId` without full restart.

**Files:**
- Read: Slippi COMM_SPEC.md (already fetched above)
- Test manually with existing codebase

**Step 1: Manual test of commandId behavior**

Create a test script to verify commandId reload works:

```python
# scripts/test_command_id_reload.py
"""Test if updating commandId reloads replay without restarting Dolphin."""
import json
import subprocess
import time
from pathlib import Path

DOLPHIN = Path("/usr/bin/dolphin-emu")  # Or AppImage path
USER_DIR = Path.home() / ".dolphin-slippi"
PLAYBACK_CONFIG = USER_DIR / "Slippi" / "playback.txt"
ISO = Path.home() / "path/to/melee.iso"

def write_config(replay: Path, command_id: str, start: int, end: int):
    config = {
        "mode": "normal",
        "replay": str(replay.absolute()),
        "startFrame": start,
        "endFrame": end,
        "commandId": command_id,
        "isRealTimeMode": False,
    }
    with open(PLAYBACK_CONFIG, "w") as f:
        json.dump(config, f)

# Test 1: Launch with first replay
write_config(Path("~/Slippi/replay1.slp").expanduser(), "cmd-001", 100, 200)
proc = subprocess.Popen([
    str(DOLPHIN), "-u", str(USER_DIR), "-e", str(ISO),
    "-i", str(PLAYBACK_CONFIG), "-b", "--hide-seekbar"
])

time.sleep(10)  # Let it play

# Test 2: Update config with new commandId - does Dolphin reload?
write_config(Path("~/Slippi/replay2.slp").expanduser(), "cmd-002", 300, 400)

time.sleep(10)  # Observe if it switches

proc.terminate()
```

Run: `.venv/bin/python scripts/test_command_id_reload.py`
Observe: Does Dolphin switch to replay2 when commandId changes?

**Step 2: Document findings**

Based on manual test results, document:
- Does commandId reload work?
- Does frame dumping continue seamlessly?
- Are there any timing issues?

If commandId reload works, proceed with Task 4. If not, skip to Task 5.

---

### Task 4: Implement Persistent Dolphin Session (if commandId works)

**Files:**
- Modify: `src/capture/dolphin.py` - add `reload_replay()` method
- Modify: `src/capture/pipeline.py` - use persistent session for batch
- Test: `tests/test_dolphin.py`, `tests/test_pipeline.py`

**Step 1: Write failing test for reload_replay**

```python
# tests/test_dolphin.py
def test_reload_replay_updates_playback_config_with_new_command_id() -> None:
    """reload_replay should update playback.txt with new commandId."""
    config = DolphinConfig(
        executable=Path("/usr/bin/echo"),
        user_dir=Path("/tmp/test-dolphin"),
        iso_path=Path("/tmp/test.iso"),
    )
    controller = DolphinController(config)

    # Set up initial state (simulating running Dolphin)
    playback_dir = Path("/tmp/test-dolphin/Slippi")
    playback_dir.mkdir(parents=True, exist_ok=True)

    # Mock that Dolphin is running
    controller._process = MagicMock()
    controller._process.poll.return_value = None  # Still running

    # Reload with new replay
    controller.reload_replay(
        replay_path=Path("/tmp/new_replay.slp"),
        output_dir=Path("/tmp/output"),
        start_frame=100,
        end_frame=200,
    )

    # Verify playback.txt was updated
    playback_config = playback_dir / "playback.txt"
    assert playback_config.exists()

    with open(playback_config) as f:
        config_data = json.load(f)

    assert config_data["replay"] == str(Path("/tmp/new_replay.slp").absolute())
    assert config_data["startFrame"] == 100
    assert config_data["endFrame"] == 200
    assert "commandId" in config_data  # Should have a commandId
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_dolphin.py::test_reload_replay_updates_playback_config_with_new_command_id -v`
Expected: FAIL (reload_replay doesn't exist)

**Step 3: Implement reload_replay method**

```python
# src/capture/dolphin.py - add to DolphinController class
import uuid

def reload_replay(
    self,
    replay_path: Path,
    output_dir: Path,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> None:
    """Reload a new replay into running Dolphin via commandId.

    Dolphin must already be running (started via start_capture).
    Updates playback.txt with new replay and a fresh commandId,
    which triggers Dolphin to reload without restarting.

    Args:
        replay_path: Path to new replay file
        output_dir: Directory for output frames
        start_frame: Optional start frame
        end_frame: Optional end frame
    """
    if self._process is None or self._process.poll() is not None:
        raise RuntimeError("Dolphin is not running. Call start_capture first.")

    if self.config.user_dir is None:
        raise ValueError("user_dir must be set for playback config")

    playback_config_path = self.config.user_dir / "Slippi" / "playback.txt"

    # Generate unique commandId to trigger reload
    command_id = f"cmd-{uuid.uuid4().hex[:8]}"

    create_playback_config_with_command_id(
        replay_path=replay_path,
        output_path=playback_config_path,
        start_frame=start_frame,
        end_frame=end_frame,
        command_id=command_id,
    )


def create_playback_config_with_command_id(
    replay_path: Path,
    output_path: Path,
    start_frame: int | None = None,
    end_frame: int | None = None,
    command_id: str | None = None,
) -> None:
    """Create playback config with optional commandId for reload."""
    config: dict[str, Any] = {
        "mode": "normal",
        "replay": str(replay_path.absolute()),
        "isRealTimeMode": False,
        "outputOverlayFiles": False,
    }

    if start_frame is not None:
        config["startFrame"] = start_frame
    if end_frame is not None:
        config["endFrame"] = end_frame
    if command_id is not None:
        config["commandId"] = command_id

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_dolphin.py::test_reload_replay_updates_playback_config_with_new_command_id -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capture/dolphin.py tests/test_dolphin.py
git commit -m "feat: add reload_replay for persistent Dolphin session"
```

---

### Task 5: Update Pipeline to Use Persistent Session (if commandId works)

**Files:**
- Modify: `src/capture/pipeline.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write failing test for persistent session**

```python
# tests/test_pipeline.py
def test_capture_moments_reuses_single_dolphin_instance() -> None:
    """Batch capture should launch Dolphin once and reload for each clip."""
    start_capture_calls = 0
    reload_calls = 0

    def mock_start_capture(self, *args, **kwargs):
        nonlocal start_capture_calls
        start_capture_calls += 1

    def mock_reload_replay(self, *args, **kwargs):
        nonlocal reload_calls
        reload_calls += 1

    with patch.object(DolphinController, "start_capture", mock_start_capture):
        with patch.object(DolphinController, "reload_replay", mock_reload_replay):
            with patch.object(DolphinController, "wait_for_completion", return_value=0):
                with patch.object(DolphinController, "stop"):
                    with patch.object(FFmpegEncoder, "encode_avi"):
                        pipeline = CapturePipeline(output_dir=Path("/tmp/clips"))

                        moments = [
                            TaggedMoment(Path(f"/tmp/test{i}.slp"), i*100, i*100+50, ["test"], {})
                            for i in range(5)
                        ]

                        pipeline.capture_moments(moments)

    # Should start Dolphin once, then reload for remaining clips
    assert start_capture_calls == 1, "Should only start Dolphin once"
    assert reload_calls == 4, "Should reload for clips 2-5"
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_pipeline.py::test_capture_moments_reuses_single_dolphin_instance -v`
Expected: FAIL (current code starts Dolphin per clip)

**Step 3: Implement persistent session in capture_moments**

```python
# src/capture/pipeline.py

def capture_moments(
    self,
    moments: list[TaggedMoment],
) -> list[Path]:
    """Capture multiple moments as video clips.

    Launches Dolphin once and reloads replays via commandId for efficiency.
    """
    if not moments:
        return []

    results: list[Path] = []

    # Capture active window before starting
    active_window = self._dolphin._get_active_window()

    # Start Dolphin with first moment
    first_moment = moments[0]
    first_temp_dir = tempfile.mkdtemp()
    first_frame_dir = Path(first_temp_dir) / "frames"
    first_frame_dir.mkdir()

    self._dolphin.start_capture(
        replay_path=first_moment.replay_path,
        output_dir=first_frame_dir,
        start_frame=first_moment.frame_start,
        end_frame=first_moment.frame_end,
        restore_window=active_window,
    )

    try:
        for i, moment in enumerate(moments, start=1):
            if i > 1:
                # Reload replay for subsequent clips
                temp_dir = tempfile.mkdtemp()
                frame_dir = Path(temp_dir) / "frames"
                frame_dir.mkdir()

                self._dolphin.reload_replay(
                    replay_path=moment.replay_path,
                    output_dir=frame_dir,
                    start_frame=moment.frame_start,
                    end_frame=moment.frame_end,
                )
            else:
                frame_dir = first_frame_dir

            # Wait for capture to complete
            return_code = self._dolphin.wait_for_completion(frame_dir=frame_dir)
            if return_code != 0:
                continue

            # Encode and save
            video_file = frame_dir / "framedump0.avi"
            audio_file = frame_dir / "dspdump.wav"

            filename = generate_clip_filename(moment, i)
            output_path = self.output_dir / filename

            self._ffmpeg.encode_avi(
                video_file=video_file,
                output_file=output_path,
                audio_file=audio_file if audio_file.exists() else None,
            )

            write_sidecar_file(output_path, moment)
            results.append(output_path)

    finally:
        # Stop Dolphin at the end
        self._dolphin.stop()

    return results
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_pipeline.py::test_capture_moments_reuses_single_dolphin_instance -v`
Expected: PASS

**Step 5: Manual test with real captures**

Run: `.venv/bin/python -m src.cli capture --tag ledgehog --limit 3`
Verify:
- Dolphin launches once
- All 3 clips are captured
- No focus stealing between clips

**Step 6: Commit**

```bash
git add src/capture/pipeline.py tests/test_pipeline.py
git commit -m "feat: reuse single Dolphin instance for batch capture"
```

---

## Summary

### Phase 1: First-Clip Minimize Fix
- Task 1: Add `_minimize_dolphin_window()` call after Popen but before polling loop

### Phase 2: Focus Restoration Fix
- Task 2: Move `_get_active_window()` call to pipeline, pass window ID to start_capture

### Phase 3: Persistent Dolphin Session (Optional)
- Task 3: Research commandId reload behavior
- Task 4: Implement `reload_replay()` method (if commandId works)
- Task 5: Update pipeline to use persistent session (if commandId works)

### Expected Results
- First clip minimizes properly
- Focus returns to correct window after each capture
- (If Phase 3 works) Faster batch capture with no focus stealing after first clip

### References
- [Slippi COMM_SPEC.md](https://github.com/project-slippi/slippi-wiki/blob/master/COMM_SPEC.md)
- [xdotool documentation](https://www.semicomplete.com/projects/xdotool/)
