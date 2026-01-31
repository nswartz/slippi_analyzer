# Slippi Replay Clipper - Design Document

## Overview

A tool to scan Slippi replay archives, detect gameplay moments of interest, and capture them as video clips for compilation videos. The first detector targets ledgehogs, but the architecture supports any event type.

**Author:** Noah Swartz (using Claude Code)
**Date:** 2026-01-31

## Problem Statement

Finding and clipping specific gameplay moments from thousands of Slippi replays is tedious. This tool automates:
1. Detecting tagged moments in replay files (starting with ledgehogs)
2. Recording those moments as video clips via Dolphin frame dump + ffmpeg
3. Organizing clips with descriptive filenames for video editing

## User Context

- **Player connect codes:** PDL-637, PIE-381 (analyze all games from these perspectives, any character)
- **Replay archive:** Thousands of .slp files
- **Goal:** Compilation videos of gameplay highlights

## Architecture

### Three-Phase Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                           SCAN PHASE                                │
│  .slp files → py-slippi parser → detectors → SQLite database        │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          QUERY PHASE                                │
│  CLI filters → database query → list of tagged moments              │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         CAPTURE PHASE                               │
│  moments → Dolphin frame dump → ffmpeg encode → organized clips     │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Scan

- Parse all .slp files from configured directory
- Identify player by connect code (PDL-637 or PIE-381)
- Run detection algorithms on each game
- Store tagged moments in SQLite database
- **Incremental mode (default):** Compare file mtime against database; only parse new/modified files
  - This is fast: stat() calls on files, no parsing required for unchanged files
- **Full rescan mode (`--full-rescan`):** Re-run all detectors on all files
  - Use case: after adding new detectors to find additional moment types

### Phase 2: Query

- CLI commands to filter moments by tags
- Returns list of moments with metadata (replay path, frame range, tags)
- Can export "clip list" for capture phase

### Phase 3: Capture

- Configure Dolphin for frame dumping (writes raw frames to disk)
- Launch Slippi Dolphin with replay file, seek to frame range
- Dolphin dumps frames for the target segment
- ffmpeg encodes frames to video (60fps, consistent resolution)
- Save with descriptive filename
- **No OBS required** - uses Dolphin's native frame dump feature
- Can run faster than realtime (no frame limiter)

## Detection & Tagging System

### Tagged Event Structure

```python
@dataclass
class TaggedMoment:
    replay_path: Path
    frame_start: int
    frame_end: int
    tags: list[str]
    metadata: dict  # opponent, stage, date, etc.
```

### Ledgehog Detection Logic

1. **ledgehog:basic**
   - Player is in `CliffWait` action state (holding ledge)
   - Opponent is offstage (x-position past stage edge)
   - Opponent subsequently loses a stock

2. **ledgehog:strict**
   - All basic conditions AND
   - Opponent was in helpless/recovery state (`DamageFall`, `Fall`, character-specific `SpecialHi`, etc.)

3. **ledgehog:intentional**
   - All strict conditions AND
   - Player grabbed ledge within 60 frames (~1 second) of opponent entering recovery state

### Auto-Generated Metadata Tags

Applied to all moments:
- `player:<character>` - e.g., `player:sheik`, `player:falcon`
- `opponent:<character>` - e.g., `opponent:fox`
- `stage:<stage>` - e.g., `stage:battlefield`
- `opponent_code:<code>` - e.g., `opponent_code:ABC-123`
- `date:<YYYY-MM-DD>` - from replay metadata

### Extensibility

New detectors (e.g., `edgeguard:spike`, `punish:reaction-tech-chase`) are functions that:
- Take frame data as input
- Return frame ranges + tags
- Scanner runs all registered detectors

## Clip Timing

### Event-Anchored Clips

Clips are anchored to game events, not fixed durations:

- **Start:** 5 seconds before the hit that sent opponent offstage
- **End:** 2 seconds after opponent falls past the hogged ledge (when recovery is clearly impossible)

This naturally adapts to different scenarios:
- Long neutral → quick ledgehog: captures the buildup
- Quick throw → extended edgeguard: starts from the initiating hit

### Note on Blast Zone

The clip ends when the opponent is clearly done (past the ledge with no recovery), NOT when they hit the blast zone. The actual death explosion may or may not be in the clip.

## Video Capture Pipeline

Uses Dolphin's native frame dump feature instead of screen capture. This approach is inspired by [slp-to-video](https://github.com/MiguelTornero/slp-to-video) and [Slippipedia](https://github.com/cbartsch/Slippipedia).

### Why Frame Dump Over OBS

- **Deterministic:** Frames can't drop; every frame is captured
- **Faster than realtime:** With frame limiter disabled, Dolphin renders as fast as possible
- **Simpler pipeline:** No screen capture, no OBS websocket coordination
- **Fewer failure points:** Just Dolphin + ffmpeg

### Workflow Per Clip

1. **Configure Dolphin frame dump**
   - Enable frame dumping in Dolphin settings
   - Set output directory for raw frames
   - Optionally use custom Dolphin build with frame limiter removed

2. **Launch Slippi Dolphin**
   - CLI: `Slippi_Dolphin -e "path/to/replay.slp"`
   - Configure to start at target frame and stop at end frame

3. **Dolphin dumps frames**
   - Raw frames written to configured directory
   - Audio dumped separately

4. **ffmpeg encodes to video**
   - Combine frames + audio into mp4
   - 60fps, consistent resolution
   - Generate filename: `2025-01-15_vs-Fox_battlefield_ledgehog-strict_001.mp4`

5. **Cleanup**
   - Delete raw frame files after encoding

### Batch Mode

- Queue all clips from query
- Process sequentially (Dolphin limitation: one instance)
- Can parallelize ffmpeg encoding while Dolphin processes next clip

## Error Handling

### Pre-Flight Checks

Before starting any batch:
- Verify Dolphin executable exists and launches
- Verify frame dump directory is writable
- Verify output directory is writable
- Verify ffmpeg is installed
- Verify Melee ISO path is configured
- Fail immediately if any check fails

### Fail-Fast on Repeated Errors

- Track consecutive failures by error type
- 3 consecutive failures of same type → abort batch with summary
- Examples: Dolphin path wrong, disk full, ffmpeg encoding failure

### Isolated vs Systemic Failures

- **Isolated** (one bad replay file): skip that clip, log, continue
- **Systemic** (Dolphin won't start): abort early

### Philosophy

Validate everything upfront, then trust the pipeline. Reliable unattended operation after initial testing.

## Project Structure

```
slippi_analyzer/
├── src/
│   ├── __init__.py
│   ├── cli.py              # Click-based CLI entry point
│   ├── scanner.py          # Parses replays, runs detectors
│   ├── database.py         # SQLite storage for moments
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── base.py         # Detector protocol/interface
│   │   └── ledgehog.py     # Ledgehog detection logic
│   ├── capture/
│   │   ├── dolphin.py      # Dolphin frame dump automation
│   │   └── ffmpeg.py       # Video encoding
│   └── models.py           # Typed dataclasses (Moment, Tag, etc.)
├── tests/
├── pyproject.toml
└── README.md
```

## CLI Commands

```bash
# Index all replays in directory (incremental - skips unchanged files)
slippi-clip scan /path/to/replays

# Full rescan - re-run all detectors (use after adding new detectors)
slippi-clip scan /path/to/replays --full-rescan

# Find moments matching criteria
slippi-clip find --tag ledgehog:strict
slippi-clip find --tag ledgehog:intentional --opponent fox

# Record clips for matching moments
slippi-clip capture --tag ledgehog:strict -o ./clips

# Merge clips into compilation
slippi-clip compile ./clips -o compilation.mp4
```

## Configuration

Stored in `~/.config/slippi-clip/config.toml`:

```toml
[player]
connect_codes = ["PDL-637", "PIE-381"]

[paths]
replay_directory = "/path/to/slippi/replays"
output_directory = "./clips"
dolphin_executable = "/path/to/Slippi_Dolphin"
melee_iso = "/path/to/melee.iso"
frame_dump_directory = "/tmp/slippi-clip-frames"

[clips]
seconds_before = 5
seconds_after = 2
```

## Tech Stack

- **Language:** Python 3.10+ with strict type hints (pyright for checking)
- **Replay parsing:** py-slippi
- **Database:** SQLite
- **CLI:** Click
- **Video processing:** ffmpeg (subprocess)
- **Testing:** pytest, TDD approach

## Testing Strategy

### Unit Tests (TDD)

- **Detectors:** Pure functions, test with mock frame data
- **Clip boundary logic:** Pure functions, test edge cases
- **Database operations:** Test with in-memory SQLite
- **Filename generation:** Pure string formatting

### Integration Tests (Mocked)

- **Dolphin automation:** Mock process interface
- **ffmpeg calls:** Mock subprocess, verify command construction

### No Snapshot Tests

Per project requirements.

## Future Enhancements (Not in Prototype)

- PyQt6 desktop UI for browsing/previewing moments
- Additional detectors (spikes, tech chases, combos)
- Configurable clip timing per query
- Video preview before capture
- Cloud sync for moment database

## Dependencies

Python packages:
```
python >= 3.10
py-slippi
click
pytest
pyright
```

External (user must install separately):
- Slippi Playback Dolphin
- ffmpeg
- Super Smash Bros. Melee ISO

## Next Steps

1. Set up project structure with pyproject.toml
2. Implement core models (TaggedMoment, etc.)
3. Build replay scanner with py-slippi
4. Implement ledgehog detector (TDD)
5. Add SQLite storage layer
6. Build CLI with Click
7. Implement capture pipeline
8. Integration testing
9. Documentation
