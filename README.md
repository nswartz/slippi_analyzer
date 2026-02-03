# Slippi Clip

A CLI tool that scans Super Smash Bros. Melee replay files (.slp) for notable gameplay moments and captures them as video clips.

## Overview

Slippi Clip uses a three-phase pipeline:

1. **Scan** - Parse .slp replays with py-slippi, run detectors, store moments in SQLite
2. **Find** - Query moments by tags, opponent, stage, etc.
3. **Capture** - Render clips via Dolphin frame dump + ffmpeg

## Installation

```bash
# Clone and enter the project
cd slippi-clip

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

## Usage

```bash
# Scan replays for moments
slippi-clip scan /path/to/replays --db moments.db

# Find moments by tag
slippi-clip find --tag ledgehog:strict --db moments.db

# Capture clips (not yet implemented)
slippi-clip capture --tag ledgehog:strict -o clips/ --db moments.db

# Compile clips into single video (not yet implemented)
slippi-clip compile clips/ -o highlight.mp4
```

## Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_ledgehog_detector.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run a single test
pytest tests/test_filename.py::test_generate_clip_filename_basic -v
```

## Moment Tags

Moments are tagged hierarchically. More specific tags imply less specific ones.

### Ledgehog Tags

| Tag | Description |
|-----|-------------|
| `ledgehog:basic` | Player on ledge while opponent offstage, opponent dies. May include false positives (e.g., opponent launched off and dying without attempting recovery). |
| `ledgehog:strict` | Opponent was in FALL_SPECIAL (helpless) state before dying. Indicates opponent used a recovery move or air dodge and couldn't grab ledge. Filters out false positives. |
| `ledgehog:intentional` | Player grabbed ledge within 60 frames (~1 second) of opponent entering recovery. Indicates a read/prediction. *(Not yet implemented)* |

### How Detection Works

1. Track when player grabs/holds ledge (CLIFF_CATCH/CLIFF_WAIT states)
2. Track opponent position (offstage = past stage edge X coordinate)
3. Track opponent state (FALL_SPECIAL = helpless after recovery/air dodge)
4. If opponent loses a stock while player was on ledge → ledgehog detected
5. If opponent was ever in FALL_SPECIAL during the sequence → add `strict` tag

### Stage Edge Coordinates

| Stage | Edge X |
|-------|--------|
| Fountain of Dreams | 63.35 |
| Pokémon Stadium | 56.0 |
| Yoshi's Story | 68.4 |
| Dream Land | 71.3 |
| Battlefield | 68.4 |
| Final Destination | 85.6 |

## Clip Filename Format

Generated clips follow this naming convention:

```
{date}_{player}_vs-{opponent}_{stage}_{tag}_{index}.mp4
```

Example: `2025-01-15_sheik_vs-fox_battlefield_ledgehog-strict_001.mp4`

## Project Structure

```
src/
├── cli.py              # Click-based CLI interface
├── database.py         # SQLite storage for moments
├── models.py           # TaggedMoment dataclass, filename generation
├── detectors/
│   ├── base.py         # Detector protocol, FrameData dataclass
│   └── ledgehog.py     # Ledgehog moment detector
└── capture/
    └── (ffmpeg.py)     # Video encoding (planned)

tests/
├── conftest.py         # Pytest fixtures
├── test_cli.py
├── test_database.py
├── test_detectors_base.py
├── test_filename.py
├── test_ledgehog_detector.py
├── test_models.py
└── fixtures/
    └── *.slp           # Sample replay files for integration tests
```

## Development Status

### Completed
- [x] Task 1-3: Project setup, models, database schema
- [x] Task 4: Database CRUD operations
- [x] Task 5: Detector protocol and FrameData
- [x] Task 6: Basic ledgehog detection
- [x] Task 7: Strict ledgehog detection (FALL_SPECIAL tracking)
- [x] Task 8: Filename generation
- [x] Task 9: CLI scaffold

### Remaining
- [ ] Task 10: FFmpeg wrapper
- [ ] Task 11: Wire up scan command with py-slippi parsing
- [ ] Task 12: Scanner - parse replays to FrameData
- [ ] Task 13: Scanner - run detectors and store moments
- [ ] Task 14: Find command - query implementation
- [ ] Task 15: Dolphin automation for frame dumping
- [ ] Task 16: Capture command - full pipeline
- [ ] Task 17: Compile command
- [ ] Task 18: Configuration file support

## Tech Stack

- Python 3.10+
- [py-slippi](https://github.com/hohav/py-slippi) - Replay parsing
- Click - CLI framework
- SQLite - Moment storage
- pytest - Testing
- pyright - Type checking

## License

MIT
