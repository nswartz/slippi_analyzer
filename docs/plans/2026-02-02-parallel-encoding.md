# Parallel Encoding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable encoding of clip N to run in the background while Dolphin captures clip N+1, reducing total batch capture time. Also improve multi-monitor handling to minimize Dolphin visibility.

**Architecture:**
- Revert to batch mode (`-b` flag) per clip since persistent mode doesn't support frame dumping
- Add `encode_avi_async()` method to `FFmpegEncoder` that launches encoding in a background thread
- Add multi-monitor awareness: launch/minimize Dolphin on the least-active monitor
- Pipeline tracks pending encode tasks and waits at end of batch

**Tech Stack:** Python `concurrent.futures.ThreadPoolExecutor`, `xdotool`, `xrandr` for monitor detection

**IMPORTANT CONTEXT:** Persistent Dolphin sessions (without `-b` flag) do NOT trigger frame dumping. Frame dumping is tied to batch mode. Therefore, we MUST launch a fresh Dolphin per clip with `-b` flag.

---

### Task 0: Revert to batch mode per clip

**Files:**
- Modify: `src/capture/pipeline.py`
- Modify: `src/capture/dolphin.py`

**Problem:** The persistent Dolphin approach (without `-b` flag) doesn't trigger frame dumping. We must revert to launching Dolphin with batch mode for each clip.

**Step 1: Update pipeline.py capture_moments()**

Revert to simpler per-clip Dolphin launches:

```python
def capture_moments(
    self,
    moments: list[TaggedMoment],
) -> list[Path]:
    """Capture multiple moments as video clips.

    Launches a fresh Dolphin instance per clip (batch mode required for frame dumping).

    Args:
        moments: List of moments to capture

    Returns:
        List of paths to generated video clips
    """
    if not moments:
        return []

    results: list[Path] = []

    for i, moment in enumerate(moments, start=1):
        # Capture active window RIGHT BEFORE each Dolphin launch
        active_window = self._dolphin.get_active_window()

        # Create temp directory for frames
        with tempfile.TemporaryDirectory() as temp_dir:
            frame_dir = Path(temp_dir) / "frames"
            frame_dir.mkdir()

            # Start Dolphin capture (batch mode - exits after replay)
            self._dolphin.start_capture(
                replay_path=moment.replay_path,
                output_dir=frame_dir,
                start_frame=moment.frame_start,
                end_frame=moment.frame_end,
                restore_window=active_window,
            )

            # Wait for capture to complete
            return_code = self._dolphin.wait_for_completion(frame_dir=frame_dir)
            if return_code != 0:
                continue

            # Find Dolphin's output files
            video_file = frame_dir / "Frames" / "framedump0.avi"
            audio_file = frame_dir / "Audio" / "dspdump.wav"

            # Generate output filename
            filename = generate_clip_filename(moment, i)
            output_path = self.output_dir / filename

            # Encode AVI+WAV to MP4
            self._ffmpeg.encode_avi(
                video_file=video_file,
                output_file=output_path,
                audio_file=audio_file if audio_file.exists() else None,
            )

            # Write sidecar metadata file
            write_sidecar_file(output_path, moment)

            results.append(output_path)

    return results
```

**Step 2: Remove persistent mode from start_capture()**

Update `start_capture()` to always use batch mode (remove `persistent` parameter or default to False).

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_capture_pipeline.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/capture/pipeline.py src/capture/dolphin.py
git commit -m "fix(capture): revert to batch mode per clip - persistent mode doesn't dump frames"
```

---

### Task 1: Add async encoding method to FFmpegEncoder

**Files:**
- Modify: `src/capture/ffmpeg.py:92-159`
- Test: `tests/test_ffmpeg.py`

**Step 1: Write the failing test**

Add to `tests/test_ffmpeg.py`:

```python
from concurrent.futures import Future
from unittest.mock import patch, MagicMock


def test_encode_avi_async_returns_future(tmp_path: Path) -> None:
    """encode_avi_async returns a Future that completes when encoding finishes."""
    encoder = FFmpegEncoder()

    video_file = tmp_path / "framedump0.avi"
    audio_file = tmp_path / "dspdump.wav"
    output_file = tmp_path / "output.mp4"
    video_file.write_bytes(b"dummy video")
    audio_file.write_bytes(b"dummy audio")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        future = encoder.encode_avi_async(
            video_file=video_file,
            output_file=output_file,
            audio_file=audio_file,
        )

        assert isinstance(future, Future)
        future.result(timeout=5)
        mock_run.assert_called_once()


def test_encode_avi_async_raises_on_failure(tmp_path: Path) -> None:
    """encode_avi_async Future raises RuntimeError if ffmpeg fails."""
    encoder = FFmpegEncoder()

    video_file = tmp_path / "framedump0.avi"
    output_file = tmp_path / "output.mp4"
    video_file.write_bytes(b"dummy video")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="encode error")

        future = encoder.encode_avi_async(
            video_file=video_file,
            output_file=output_file,
        )

        import pytest
        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            future.result(timeout=5)
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ffmpeg.py::test_encode_avi_async_returns_future -v`
Expected: FAIL with "AttributeError: 'FFmpegEncoder' object has no attribute 'encode_avi_async'"

**Step 3: Write minimal implementation**

Add imports at top of `src/capture/ffmpeg.py`:

```python
from concurrent.futures import Future, ThreadPoolExecutor
```

Add to `FFmpegEncoder` class:

```python
    _executor: ThreadPoolExecutor | None = None

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor for async encoding."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=2)
        return self._executor

    def encode_avi_async(
        self,
        video_file: Path,
        output_file: Path,
        audio_file: Path | None = None,
        crf: int = 18,
        preset: str = "medium",
    ) -> Future[None]:
        """Encode AVI video to MP4 asynchronously.

        Returns immediately with a Future that completes when encoding finishes.
        """
        def _encode() -> None:
            self.encode_avi(
                video_file=video_file,
                output_file=output_file,
                audio_file=audio_file,
                crf=crf,
                preset=preset,
            )

        return self._get_executor().submit(_encode)
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_ffmpeg.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capture/ffmpeg.py tests/test_ffmpeg.py
git commit -m "feat(ffmpeg): add encode_avi_async for background encoding"
```

---

### Task 2: Add multi-monitor support - detect least-active monitor

**Files:**
- Create: `src/capture/monitors.py`
- Test: `tests/test_monitors.py`

**Goal:** Detect which monitor has the least user activity so Dolphin can be launched/minimized there.

**Step 1: Write the failing test**

Create `tests/test_monitors.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from src.capture.monitors import get_monitors, get_least_active_monitor, Monitor


def test_get_monitors_parses_xrandr_output() -> None:
    """get_monitors parses xrandr output to extract monitor info."""
    xrandr_output = """Screen 0: minimum 8 x 8, current 3840 x 1080, maximum 32767 x 32767
DP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+
HDMI-1 connected 1920x1080+1920+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=xrandr_output)

        monitors = get_monitors()

        assert len(monitors) == 2
        assert monitors[0].name == "DP-1"
        assert monitors[0].x == 0
        assert monitors[0].y == 0
        assert monitors[0].width == 1920
        assert monitors[0].height == 1080
        assert monitors[0].is_primary

        assert monitors[1].name == "HDMI-1"
        assert monitors[1].x == 1920
        assert not monitors[1].is_primary


def test_get_least_active_monitor_returns_non_focused() -> None:
    """get_least_active_monitor returns monitor without the focused window."""
    monitors = [
        Monitor("DP-1", 0, 0, 1920, 1080, True),
        Monitor("HDMI-1", 1920, 0, 1920, 1080, False),
    ]

    # Active window is on DP-1 (x=500)
    with patch("subprocess.run") as mock_run:
        def run_side_effect(cmd, **kwargs):
            if "getactivewindow" in cmd:
                return MagicMock(returncode=0, stdout="12345")
            elif "getwindowgeometry" in cmd:
                return MagicMock(returncode=0, stdout="Window 12345\n  Position: 500,200 (screen: 0)\n  Geometry: 800x600")
            return MagicMock(returncode=1)

        mock_run.side_effect = run_side_effect

        result = get_least_active_monitor(monitors)

        # Should return HDMI-1 since active window is on DP-1
        assert result.name == "HDMI-1"


def test_get_least_active_monitor_single_monitor() -> None:
    """get_least_active_monitor returns the only monitor if just one exists."""
    monitors = [Monitor("DP-1", 0, 0, 1920, 1080, True)]

    result = get_least_active_monitor(monitors)

    assert result.name == "DP-1"
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_monitors.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.capture.monitors'"

**Step 3: Write minimal implementation**

Create `src/capture/monitors.py`:

```python
"""Multi-monitor support for Dolphin window placement."""

import subprocess
import re
from dataclasses import dataclass


@dataclass
class Monitor:
    """Represents a display monitor."""
    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = False


def get_monitors() -> list[Monitor]:
    """Get list of connected monitors using xrandr.

    Returns:
        List of Monitor objects, empty if xrandr fails
    """
    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        monitors: list[Monitor] = []
        # Pattern: "NAME connected [primary] WIDTHxHEIGHT+X+Y"
        pattern = r"(\S+) connected\s*(primary)?\s*(\d+)x(\d+)\+(\d+)\+(\d+)"

        for match in re.finditer(pattern, result.stdout):
            name = match.group(1)
            is_primary = match.group(2) == "primary"
            width = int(match.group(3))
            height = int(match.group(4))
            x = int(match.group(5))
            y = int(match.group(6))

            monitors.append(Monitor(
                name=name,
                x=x,
                y=y,
                width=width,
                height=height,
                is_primary=is_primary,
            ))

        return monitors
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_window_position(window_id: str) -> tuple[int, int] | None:
    """Get the position of a window using xdotool.

    Returns:
        (x, y) tuple or None if failed
    """
    try:
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", window_id],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        # Parse "Position: X,Y (screen: N)"
        match = re.search(r"Position:\s*(\d+),(\d+)", result.stdout)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_monitor_for_position(monitors: list[Monitor], x: int, y: int) -> Monitor | None:
    """Find which monitor contains the given position."""
    for monitor in monitors:
        if (monitor.x <= x < monitor.x + monitor.width and
            monitor.y <= y < monitor.y + monitor.height):
            return monitor
    return None


def get_least_active_monitor(monitors: list[Monitor]) -> Monitor:
    """Get the monitor that is least likely to have user focus.

    Logic:
    1. Get currently focused window position
    2. Return a monitor that does NOT contain the focused window
    3. If only one monitor or can't determine, return non-primary or first

    Args:
        monitors: List of available monitors

    Returns:
        The least-active monitor (never None, falls back to first)
    """
    if len(monitors) <= 1:
        return monitors[0] if monitors else Monitor("default", 0, 0, 1920, 1080, True)

    # Get active window position
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            window_id = result.stdout.strip()
            pos = get_window_position(window_id)
            if pos:
                active_monitor = get_monitor_for_position(monitors, pos[0], pos[1])
                if active_monitor:
                    # Return any monitor that is NOT the active one
                    for monitor in monitors:
                        if monitor.name != active_monitor.name:
                            return monitor
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: prefer non-primary monitor
    for monitor in monitors:
        if not monitor.is_primary:
            return monitor

    return monitors[0]
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_monitors.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capture/monitors.py tests/test_monitors.py
git commit -m "feat(monitors): add multi-monitor detection for Dolphin placement"
```

---

### Task 3: Use least-active monitor for Dolphin window

**Files:**
- Modify: `src/capture/dolphin.py`
- Test: `tests/test_dolphin.py`

**Step 1: Write the failing test**

Add to `tests/test_dolphin.py`:

```python
def test_minimize_dolphin_window_uses_least_active_monitor(tmp_path: Path) -> None:
    """Dolphin window is moved to least-active monitor before minimizing."""
    from src.capture.monitors import Monitor

    config = DolphinConfig(executable=Path("/usr/bin/dolphin-emu"), user_dir=tmp_path)
    controller = DolphinController(config)

    monitors = [
        Monitor("DP-1", 0, 0, 1920, 1080, True),
        Monitor("HDMI-1", 1920, 0, 1920, 1080, False),
    ]

    with patch("src.capture.dolphin.get_monitors", return_value=monitors):
        with patch("src.capture.dolphin.get_least_active_monitor") as mock_least:
            mock_least.return_value = monitors[1]  # HDMI-1
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")

                controller._minimize_dolphin_window()

                # Verify windowmove was called with HDMI-1 coordinates
                move_calls = [c for c in mock_run.call_args_list
                             if "windowmove" in str(c)]
                assert len(move_calls) > 0
                # Should move to x=1920 (HDMI-1's x position)
```

**Step 2: Update _minimize_dolphin_window()**

In `src/capture/dolphin.py`, update `_minimize_dolphin_window()`:

```python
from src.capture.monitors import get_monitors, get_least_active_monitor

def _minimize_dolphin_window(self) -> None:
    """Find and minimize Dolphin window on least-active monitor."""
    try:
        # Get monitors and find least active
        monitors = get_monitors()
        target_monitor = get_least_active_monitor(monitors) if monitors else None

        # Wait for Dolphin window to appear
        result = subprocess.run(
            ["xdotool", "search", "--sync", "--name", "Slippi"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0 and result.stdout.strip():
            window_ids = result.stdout.strip().split("\n")
            for window_id in window_ids:
                if window_id:
                    # Move to least-active monitor if we have multi-monitor
                    if target_monitor and len(monitors) > 1:
                        subprocess.run(
                            ["xdotool", "windowmove", window_id,
                             str(target_monitor.x), str(target_monitor.y)],
                            timeout=5,
                        )

                    # Minimize immediately
                    subprocess.run(
                        ["xdotool", "windowminimize", "--sync", window_id],
                        timeout=5,
                    )

        # Restore focus to original window
        if self._original_window:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", self._original_window],
                timeout=5,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_dolphin.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/capture/dolphin.py tests/test_dolphin.py
git commit -m "feat(dolphin): move window to least-active monitor before minimize"
```

---

### Task 4: Update pipeline for parallel encoding with batch mode

**Files:**
- Modify: `src/capture/pipeline.py`
- Test: `tests/test_capture_pipeline.py`

**Step 1: Write the failing test**

```python
def test_capture_moments_encodes_in_background(tmp_path: Path) -> None:
    """capture_moments starts encoding previous clip while capturing next."""
    from concurrent.futures import Future

    encode_async_calls = 0

    def mock_encode_avi_async(**kwargs) -> Future[None]:
        nonlocal encode_async_calls
        encode_async_calls += 1
        future: Future[None] = Future()
        future.set_result(None)
        return future

    # ... setup mocks for DolphinController ...

    # Verify encode_avi_async was called instead of encode_avi
    assert encode_async_calls == 3
```

**Step 2: Update capture_moments() to use async encoding**

```python
def capture_moments(
    self,
    moments: list[TaggedMoment],
) -> list[Path]:
    """Capture multiple moments as video clips.

    Launches a fresh Dolphin per clip. Encodes in background while next captures.
    """
    if not moments:
        return []

    results: list[Path] = []
    pending_encodes: list[tuple[Future[None], Path, TaggedMoment, str]] = []

    for i, moment in enumerate(moments, start=1):
        active_window = self._dolphin.get_active_window()

        temp_dir = tempfile.mkdtemp()
        frame_dir = Path(temp_dir) / "frames"
        frame_dir.mkdir()

        self._dolphin.start_capture(
            replay_path=moment.replay_path,
            output_dir=frame_dir,
            start_frame=moment.frame_start,
            end_frame=moment.frame_end,
            restore_window=active_window,
        )

        return_code = self._dolphin.wait_for_completion(frame_dir=frame_dir)
        if return_code != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            continue

        video_file = frame_dir / "Frames" / "framedump0.avi"
        audio_file = frame_dir / "Audio" / "dspdump.wav"

        filename = generate_clip_filename(moment, i)
        output_path = self.output_dir / filename

        # Start encoding in background
        future = self._ffmpeg.encode_avi_async(
            video_file=video_file,
            output_file=output_path,
            audio_file=audio_file if audio_file.exists() else None,
        )
        pending_encodes.append((future, output_path, moment, temp_dir))

    # Wait for all encodes to complete
    for future, output_path, moment, temp_dir in pending_encodes:
        try:
            future.result(timeout=300)
            write_sidecar_file(output_path, moment)
            results.append(output_path)
        except Exception as e:
            print(f"Encoding failed for {output_path}: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return results
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_capture_pipeline.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/capture/pipeline.py tests/test_capture_pipeline.py
git commit -m "feat(pipeline): encode in background while capturing next clip"
```

---

## Summary

After implementing these tasks:

1. **Batch mode per clip** - Reverted to launching fresh Dolphin with `-b` flag (required for frame dumping)
2. **Async encoding** - `FFmpegEncoder.encode_avi_async()` returns a Future for background encoding
3. **Multi-monitor support** - Dolphin windows moved to least-active monitor before minimizing
4. **Parallel workflow** - While clip N+1 captures, clip N encodes in background

**Expected performance improvement:** Encoding happens in parallel with capture. For N clips, if encoding ≈ capture time, total time reduced by ~40%.

**User experience improvement:** On multi-monitor setups, Dolphin windows appear on the monitor the user isn't actively using, reducing visual interruption.
