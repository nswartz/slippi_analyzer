# Slippi Ledgehog Clipper - Design Document

## Overview

A tool to scan Slippi replay archives, detect ledgehog moments, and capture them as video clips for compilation videos.

**Author:** Noah Swartz (using Claude Code)
**Date:** 2026-01-31

## Problem Statement

Finding and clipping specific gameplay moments (like ledgehogs) from thousands of Slippi replays is tedious. This tool automates:
1. Detecting ledgehog moments in replay files
2. Recording those moments as video clips via Dolphin + OBS
3. Organizing clips with descriptive filenames for video editing

## User Context

- **Player connect codes:** PDL-637, PIE-381 (analyze all games from these perspectives, any character)
- **Replay archive:** Thousands of .slp files
- **Goal:** Compilation videos of ledgehog highlights

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
│  moments → Dolphin playback → OBS recording → ffmpeg post-process   │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Scan

- Parse all .slp files from configured directory
- Identify player by connect code (PDL-637 or PIE-381)
- Run detection algorithms on each game
- Store tagged moments in SQLite database
- Incremental: only re-scan new/modified files

### Phase 2: Query

- CLI commands to filter moments by tags
- Returns list of moments with metadata (replay path, frame range, tags)
- Can export "clip list" for capture phase

### Phase 3: Capture

- Launch Slippi Dolphin with replay file
- Connect to OBS via websocket (obs-websocket, built into OBS 28+)
- Seek to target frame range
- Record the moment
- Post-process with ffmpeg: trim frozen frames, normalize to 60fps
- Save with descriptive filename

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

### Workflow Per Clip

1. **Launch Slippi Dolphin**
   - CLI: `Slippi_Dolphin -e "path/to/replay.slp"`
   - Starts playback from frame 0

2. **Connect to OBS**
   - Library: `obsws-python`
   - Commands: start/stop recording

3. **Seek to target frame**
   - Keyboard automation (pyautogui) to fast-forward
   - Alternative: explore Dolphin's pause-at-frame feature

4. **Capture**
   - Start OBS recording before the moment
   - Let it play through
   - Stop recording after end frame + buffer

5. **Post-process with ffmpeg**
   - Detect and trim frozen/loading frames
   - Normalize to 60fps, consistent resolution
   - Generate filename: `2025-01-15_vs-Fox_battlefield_ledgehog-strict_001.mp4`

### Batch Mode

- Queue all clips from query
- Record sequentially (Dolphin limitation: one instance)
- Post-process in parallel

## Error Handling

### Pre-Flight Checks

Before starting any batch:
- Verify Dolphin executable exists and launches
- Verify OBS websocket connection works
- Verify output directory is writable
- Verify ffmpeg is installed
- Fail immediately if any check fails

### Fail-Fast on Repeated Errors

- Track consecutive failures by error type
- 3 consecutive failures of same type → abort batch with summary
- Examples: Dolphin path wrong, OBS not responding, disk full

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
│   │   ├── dolphin.py      # Dolphin automation
│   │   ├── obs.py          # OBS websocket control
│   │   └── ffmpeg.py       # Post-processing
│   └── models.py           # Typed dataclasses (Moment, Tag, etc.)
├── tests/
├── pyproject.toml
└── README.md
```

## CLI Commands

```bash
# Index all replays in directory
slippi-clip scan /path/to/replays

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

[obs]
websocket_host = "localhost"
websocket_port = 4455
websocket_password = "your-password"

[clips]
seconds_before = 5
seconds_after = 2
```

## Tech Stack

- **Language:** Python 3.10+ with strict type hints (pyright for checking)
- **Replay parsing:** py-slippi
- **Database:** SQLite
- **CLI:** Click
- **OBS control:** obsws-python
- **Video processing:** ffmpeg (subprocess)
- **Keyboard automation:** pyautogui
- **Testing:** pytest, TDD approach

## Testing Strategy

### Unit Tests (TDD)

- **Detectors:** Pure functions, test with mock frame data
- **Clip boundary logic:** Pure functions, test edge cases
- **Database operations:** Test with in-memory SQLite
- **Filename generation:** Pure string formatting

### Integration Tests (Mocked)

- **Dolphin automation:** Mock process interface
- **OBS websocket:** Mock connection
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

```
python >= 3.10
py-slippi
click
obsws-python
pyautogui
pytest
pyright
```

External:
- Slippi Dolphin
- OBS Studio (28+)
- ffmpeg

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
