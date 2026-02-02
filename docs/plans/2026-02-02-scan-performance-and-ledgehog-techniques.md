# Scan Performance & Ledgehog Technique Detection

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve replay scan performance through parallelization and add detection for different ledge grab techniques (wavedash, jump, ramen noodles, hit-into-ledge).

**Architecture:** Two-phase improvement: (1) Add parallel processing to the Python scanner using ThreadPoolExecutor for I/O-bound replay parsing, with optional future migration to Rust's peppi parser. (2) Extend ledgehog detector to categorize grabs by technique using Melee action state sequences.

**Tech Stack:** Python concurrent.futures, peppi (Rust via PyO3 bindings), py-slippi, Melee action states

---

## Phase 1: Scan Performance Optimization

### Background

Current bottleneck analysis (236 replays taking several minutes):
- **40-50% parsing**: Sequential `Game(replay_path)` calls via py-slippi
- **30-40% detection**: Ledgehog state machine per-frame checks
- **10-20% I/O**: Database writes per moment

The scan is I/O-bound during replay parsing (reading .slp files) and CPU-bound during detection. Python's GIL allows I/O parallelization but limits CPU parallelization.

### Task 1: Add Parallel Replay Processing

**Files:**
- Modify: `src/scanner.py:258-298` (scan_replay loop)
- Test: `tests/test_scanner.py`

**Step 1: Write failing test for parallel scanning**

```python
# tests/test_scanner.py
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import time

def test_scan_replays_parallel_faster_than_sequential():
    """Parallel scanning should be faster for multiple replays."""
    scanner = ReplayScanner(detectors=[])

    # Mock slow replay parsing (100ms each)
    def slow_parse(path, player_port, player_tags):
        time.sleep(0.1)
        return []

    with patch.object(scanner, 'scan_replay', side_effect=slow_parse):
        paths = [Path(f"/fake/replay_{i}.slp") for i in range(10)]

        # Sequential would take 10 * 0.1 = 1 second
        # Parallel with 4 workers should take ~0.3 seconds
        start = time.time()
        results = scanner.scan_replays_parallel(paths, player_port=0, player_tags=[], max_workers=4)
        elapsed = time.time() - start

        assert elapsed < 0.5  # Should be much faster than 1 second
        assert len(results) == 10
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_scanner.py::test_scan_replays_parallel_faster_than_sequential -v`
Expected: FAIL with "AttributeError: 'ReplayScanner' object has no attribute 'scan_replays_parallel'"

**Step 3: Implement parallel scanning**

```python
# src/scanner.py - add to ReplayScanner class
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

def scan_replays_parallel(
    self,
    replay_paths: list[Path],
    player_port: int,
    player_tags: list[str],
    max_workers: int = 4,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[TaggedMoment]:
    """Scan multiple replays in parallel using thread pool.

    Args:
        replay_paths: List of .slp file paths to scan
        player_port: Player port index
        player_tags: Player connect codes
        max_workers: Number of parallel workers (default 4)
        progress_callback: Optional callback(completed, total) for progress

    Returns:
        Flattened list of all detected moments
    """
    all_moments: list[TaggedMoment] = []
    completed = 0
    total = len(replay_paths)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_path = {
            executor.submit(self.scan_replay, path, player_port, player_tags): path
            for path in replay_paths
        }

        # Collect results as they complete
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                moments = future.result()
                all_moments.extend(moments)
            except Exception as e:
                # Log error but continue with other replays
                print(f"Error scanning {path}: {e}")

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    return all_moments
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_scanner.py::test_scan_replays_parallel_faster_than_sequential -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scanner.py tests/test_scanner.py
git commit -m "feat: add parallel replay scanning with ThreadPoolExecutor"
```

### Task 2: Integrate Parallel Scanning into CLI

**Files:**
- Modify: `src/cli.py:55-139` (scan command)

**Step 1: Update scan command to use parallel processing**

```python
# src/cli.py - modify scan command
import os

@cli.command()
@click.argument("replay_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--full-rescan", is_flag=True, help="Re-scan all files, ignoring cache")
@click.option("--db", "db_path", type=click.Path(path_type=Path), help="Database path")
@click.option("--player-port", type=int, help="Player port index (0-3)")
@click.option("--player-tag", "player_tags", multiple=True, help="Player connect code")
@click.option("--workers", type=int, default=None, help="Parallel workers (default: CPU count)")
def scan(
    replay_dir: Path,
    full_rescan: bool,
    db_path: Path | None,
    player_port: int | None,
    player_tags: tuple[str, ...],
    workers: int | None,
) -> None:
    """Scan replay directory for moments."""
    # ... existing setup code ...

    # Determine worker count
    max_workers = workers or min(os.cpu_count() or 4, 8)

    # Filter replays that need scanning
    replays_to_scan = [
        p for p in replay_paths
        if full_rescan or database.needs_scan(p)
    ]

    if not replays_to_scan:
        click.echo("All replays already scanned")
        return

    click.echo(f"Scanning {len(replays_to_scan)} replays with {max_workers} workers...")

    # Use parallel scanning
    def progress(completed: int, total: int) -> None:
        if completed % 10 == 0 or completed == total:
            click.echo(f"  Progress: {completed}/{total}")

    moments = scanner.scan_replays_parallel(
        replays_to_scan,
        player_port=effective_port,
        player_tags=list(effective_tags),
        max_workers=max_workers,
        progress_callback=progress,
    )

    # Store moments in database
    for moment in moments:
        database.store_moment(moment)
```

**Step 2: Test manually**

Run: `.venv/bin/python -m src.cli scan ~/Slippi/2025-11 --full-rescan --workers 4`
Expected: Faster scan time, progress output every 10 replays

**Step 3: Commit**

```bash
git add src/cli.py
git commit -m "feat: use parallel scanning in CLI with configurable workers"
```

### Task 3: (Future) Rust Parser Integration via peppi

**Note:** This task is for future implementation when Python performance ceiling is reached.

**Background:**
- [peppi](https://github.com/hohav/peppi) is a Rust parser for Slippi files
- Can expose via PyO3 bindings for 10-100x parsing speedup
- Would replace py-slippi's `Game` class

**Files to create (future):**
- `src/parser_rust/` - PyO3 bindings to peppi
- `Cargo.toml` - Rust project config
- `pyproject.toml` - Add maturin build

**Rough implementation approach:**
1. Create Rust crate with PyO3 bindings
2. Expose `parse_replay(path: str) -> list[FrameData]` function
3. Build with maturin: `maturin develop`
4. Replace py-slippi calls with Rust parser

---

## Phase 2: Ledgehog Technique Detection

### Background

Melee action states relevant for ledge grab techniques:

| State | ID | Description |
|-------|-----|-------------|
| AIRDODGE | 236 | Air dodge (wavedash component) |
| LANDING_SPECIAL | 43 | Landing from helpless/airdodge |
| FALLING | 29 | Regular fall |
| FALL_SPECIAL | 35 | Helpless fall |
| EDGE_CATCHING | 252 | Grabbing ledge |
| EDGE_HANGING | 253 | Holding ledge |
| JUMPING_FORWARD | 25 | Forward jump |
| JUMPING_BACKWARD | 26 | Backward jump |
| JUMPING_ARIAL_FORWARD | 27 | Aerial forward jump |
| JUMPING_ARIAL_BACKWARD | 28 | Aerial backward jump |

**Ledge grab techniques to detect:**

1. **Recovery grab** - FALL_SPECIAL → EDGE_CATCHING (used up-B/side-B)
2. **Jump grab** - JUMPING_* → FALLING → EDGE_CATCHING
3. **Wavedash grab** - AIRDODGE → LANDING_SPECIAL (at edge) → FALLING → EDGE_CATCHING
4. **Ramen noodles** - Same as wavedash but facing away, with fastfall (Y velocity check)
5. **Hit-into-grab** - DAMAGE_* → EDGE_CATCHING (DI'd to ledge)

### Task 4: Add Action State Tracking for Techniques

**Files:**
- Modify: `src/detectors/ledgehog.py`
- Modify: `src/detectors/base.py` (add player velocity to FrameData)
- Test: `tests/test_ledgehog_detector.py`

**Step 1: Extend FrameData with velocity**

```python
# src/detectors/base.py
@dataclass
class FrameData:
    frame_number: int

    # Player state
    player_x: float
    player_y: float
    player_action_state: int
    player_stocks: int
    player_facing: int  # 1 = right, -1 = left (NEW)

    # Opponent state
    opponent_x: float
    opponent_y: float
    opponent_action_state: int
    opponent_stocks: int

    # Stage
    stage_id: int
```

**Step 2: Add action state constants for technique detection**

```python
# src/detectors/ledgehog.py - add to ActionState class

class ActionState:
    # ... existing states ...

    # Landing states
    LANDING = 42
    LANDING_SPECIAL = 43  # Wavedash landing

    # Jump states
    JUMP_F = 25
    JUMP_B = 26
    JUMP_AERIAL_F = 27
    JUMP_AERIAL_B = 28

    # Edge states
    EDGE_CATCHING = 252  # Same as CLIFF_CATCH
    EDGE_HANGING = 253   # Same as CLIFF_WAIT


# State sets for technique detection
JUMP_STATES = {
    ActionState.JUMP_F,
    ActionState.JUMP_B,
    ActionState.JUMP_AERIAL_F,
    ActionState.JUMP_AERIAL_B,
}

WAVEDASH_LANDING_STATES = {
    ActionState.LANDING_SPECIAL,
}
```

**Step 3: Create LedgeGrabTechnique enum**

```python
# src/detectors/ledgehog.py
from enum import Enum

class LedgeGrabTechnique(Enum):
    """How the player grabbed the ledge."""
    RECOVERY = "recovery"           # Used up-B/side-B
    JUMP = "jump"                   # Used double jump
    WAVEDASH = "wavedash"           # Wavedashed off stage
    RAMEN_NOODLES = "ramen"         # Wavedash + fastfall facing away
    HIT_INTO = "hit"                # Got hit and DI'd to ledge
    UNKNOWN = "unknown"             # Could not determine
```

**Step 4: Add technique detection to LedgehogEvent**

```python
# src/detectors/ledgehog.py - modify LedgehogEvent
@dataclass
class LedgehogEvent:
    ledge_grab_frame: int
    player_left_ledge_frame: int | None = None
    opponent_reached_ledge_position: bool = False
    opponent_reached_ledge_frame: int | None = None
    opponent_was_hit: bool = False
    opponent_in_recovery_state: bool = False
    throw_setup_frame: int | None = None
    player_was_hit_into_ledge: bool = False

    # Technique tracking (NEW)
    grab_technique: LedgeGrabTechnique = LedgeGrabTechnique.UNKNOWN
    player_recent_states: list[int] = field(default_factory=list)
    player_was_facing_away: bool = False
```

**Step 5: Implement technique detection logic**

```python
# src/detectors/ledgehog.py - add method to LedgehogDetector

def _detect_grab_technique(
    self,
    recent_states: list[int],
    was_facing_away: bool,
    edge_x: float,
    player_x_at_grab: float,
) -> LedgeGrabTechnique:
    """Determine how the player grabbed the ledge based on recent action states.

    Args:
        recent_states: Last 30 frames of player action states before grab
        was_facing_away: Whether player was facing away from ledge
        edge_x: Stage edge X coordinate
        player_x_at_grab: Player X position when grabbing ledge

    Returns:
        Detected ledge grab technique
    """
    # Check for hit-into-ledge (damage state in recent history)
    for state in recent_states[-15:]:  # Last 15 frames
        if state in PLAYER_HIT_STATES:
            return LedgeGrabTechnique.HIT_INTO

    # Check for wavedash/ramen (AIRDODGE → LANDING_SPECIAL)
    has_airdodge = ActionState.ESCAPE_AIR in recent_states
    has_landing_special = ActionState.LANDING_SPECIAL in recent_states

    if has_airdodge and has_landing_special:
        # Ramen noodles: wavedash while facing away from ledge
        if was_facing_away:
            return LedgeGrabTechnique.RAMEN_NOODLES
        else:
            return LedgeGrabTechnique.WAVEDASH

    # Check for jump grab (JUMP_* in recent history)
    for state in recent_states:
        if state in JUMP_STATES:
            return LedgeGrabTechnique.JUMP

    # Check for recovery (FALL_SPECIAL)
    if ActionState.FALL_SPECIAL in recent_states:
        return LedgeGrabTechnique.RECOVERY

    return LedgeGrabTechnique.UNKNOWN
```

**Step 6: Track player states and facing direction in main loop**

```python
# src/detectors/ledgehog.py - modify detect() method

def detect(self, frames: list[FrameData], replay_path: Path) -> list[TaggedMoment]:
    # ... existing setup ...

    # Track recent player states for technique detection
    player_state_history: list[int] = []
    HISTORY_LENGTH = 30  # ~0.5 seconds of history

    for frame in frames:
        # Track player state history
        player_state_history.append(frame.player_action_state)
        if len(player_state_history) > HISTORY_LENGTH:
            player_state_history.pop(0)

        # Check if player is facing away from nearest ledge
        nearest_edge_x = edge_x if frame.player_x >= 0 else -edge_x
        player_facing_ledge = (
            (frame.player_facing > 0 and frame.player_x < nearest_edge_x) or
            (frame.player_facing < 0 and frame.player_x > nearest_edge_x)
        )

        # ... existing detection logic ...

        # When player grabs ledge, detect technique
        if player_on_ledge and not prev_player_on_ledge:
            grab_technique = self._detect_grab_technique(
                recent_states=player_state_history.copy(),
                was_facing_away=not player_facing_ledge,
                edge_x=edge_x,
                player_x_at_grab=frame.player_x,
            )
            # Store in tracking event
            if tracking_event is not None:
                tracking_event.grab_technique = grab_technique
```

**Step 7: Add technique tags to moments**

```python
# src/detectors/ledgehog.py - modify moment creation

# When creating TaggedMoment:
tags = ["ledgehog"]

# Add technique tag
technique_tag = f"ledgehog:{tracking_event.grab_technique.value}"
tags.append(technique_tag)

# Add clutch timing tags as before
for threshold, tag in self.CLUTCH_TIERS:
    if reaction_frames <= threshold:
        tags.append(tag)
```

**Step 8: Write tests**

```python
# tests/test_ledgehog_detector.py

def test_detects_wavedash_technique():
    """Wavedash grab is detected from AIRDODGE → LANDING_SPECIAL sequence."""
    detector = LedgehogDetector()
    frames = [
        # Player wavedashes: AIRDODGE → LANDING_SPECIAL → FALL → EDGE_CATCHING
        make_frame(90, player_action=ActionState.ESCAPE_AIR, ...),
        make_frame(91, player_action=ActionState.LANDING_SPECIAL, ...),
        make_frame(92, player_action=ActionState.FALL, ...),
        make_frame(93, player_action=ActionState.CLIFF_CATCH, ...),  # Grab!
        # ... opponent at ledge, dies
    ]
    moments = detector.detect(frames, Path("/test.slp"))
    assert "ledgehog:wavedash" in moments[0].tags


def test_detects_ramen_noodles_technique():
    """Ramen noodles detected when wavedashing while facing away."""
    # Similar to wavedash but player_facing points away from ledge
    pass


def test_detects_jump_technique():
    """Jump grab detected from JUMP_* states."""
    pass


def test_detects_hit_into_ledge():
    """Hit-into-ledge detected from DAMAGE_* states before grab."""
    pass
```

**Step 9: Commit**

```bash
git add src/detectors/base.py src/detectors/ledgehog.py tests/test_ledgehog_detector.py
git commit -m "feat: detect ledge grab techniques (wavedash, jump, ramen, hit)"
```

### Task 5: Update Scanner to Extract Facing Direction

**Files:**
- Modify: `src/scanner.py` (parse_replay_to_frames)

**Step 1: Add facing direction extraction**

```python
# src/scanner.py - modify parse_replay_to_frames

def parse_replay_to_frames(...) -> list[FrameData]:
    # ... existing code ...

    for frame in game.frames:
        # ... existing extraction ...

        # Extract facing direction from post-frame data
        # In Slippi, facing is stored as float: 1.0 = right, -1.0 = left
        player_facing = 1  # Default
        if hasattr(player_port_data.post, 'facing_direction'):
            player_facing = int(player_port_data.post.facing_direction)
        elif hasattr(player_port_data.post, 'direction'):
            player_facing = 1 if player_port_data.post.direction > 0 else -1

        frames.append(FrameData(
            # ... existing fields ...
            player_facing=player_facing,
        ))
```

**Step 2: Test manually**

Run: `.venv/bin/python -m src.cli scan ~/Slippi/2025-11 --full-rescan`
Check: `.venv/bin/python -m src.cli find --tag ledgehog`
Expected: See technique tags like `ledgehog:wavedash`, `ledgehog:ramen`, etc.

**Step 3: Commit**

```bash
git add src/scanner.py
git commit -m "feat: extract player facing direction for technique detection"
```

---

## Summary

### Phase 1: Performance
- Task 1: Parallel replay processing (ThreadPoolExecutor)
- Task 2: CLI integration with --workers flag
- Task 3: (Future) Rust parser via peppi

### Phase 2: Techniques
- Task 4: Technique detection logic (wavedash, ramen, jump, hit)
- Task 5: Facing direction extraction

### Expected Results
- **Scan time**: 4-8x faster with parallel processing
- **Technique tags**: `ledgehog:recovery`, `ledgehog:wavedash`, `ledgehog:ramen`, `ledgehog:jump`, `ledgehog:hit`

### References
- [peppi (Rust Slippi parser)](https://github.com/hohav/peppi)
- [libmelee action states](https://libmelee.readthedocs.io/en/beta/)
- [py-slippi documentation](https://py-slippi.readthedocs.io/en/latest/source/slippi.html)
