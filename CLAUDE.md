# Slippi Clip Analyzer

A tool for scanning Super Smash Bros. Melee replay files (.slp) to detect gameplay moments (ledgehogs, combos, etc.) and capture video clips via Dolphin frame dumps.

## Project Structure

```
src/
├── cli.py           # Click CLI: scan, find, capture, compile commands
├── scanner.py       # Replay parsing and parallel scanning
├── database.py      # SQLite storage for replays/moments/tags
├── config.py        # TOML config (~/.config/slippi-clip/config.toml)
├── models.py        # TaggedMoment, FrameData dataclasses
├── detectors/       # Moment detection plugins
│   ├── base.py      # BaseDetector protocol, DetectorRegistry
│   └── ledgehog.py  # Ledgehog detection with timing tags
└── capture/         # Video capture pipeline
    ├── pipeline.py  # Orchestrates Dolphin + ffmpeg
    ├── dolphin.py   # Slippi Dolphin controller
    └── ffmpeg.py    # AVI→MP4 encoding
```

## Python Environment

- ALWAYS use the project's virtual environment (`.venv/`) for Python operations
- Run Python commands via `.venv/bin/python` or `.venv/bin/<tool>` (e.g., `.venv/bin/pytest`)
- NEVER use `uv` or other global package managers - keep dependencies isolated in the venv

## Code Quality

- Run `.venv/bin/pyright src/` before committing to catch type errors and unused imports
- The project uses `typeCheckingMode = "strict"` - all code must pass strict type checking
- ALWAYS remove unused imports after refactoring

## Testing Guidelines

Project-specific test coverage:
- Unit tests for all logic: detectors, clip boundaries, database operations, filename generation
- Skip tests for non-logic code (HTML templates, static config, etc.)
- Integration tests for capture pipeline (with mocked Dolphin/ffmpeg)

## Data Locations

- Database: `~/.local/share/slippi-clip/moments.db`
- Config: `~/.config/slippi-clip/config.toml`
- Dolphin profile: `~/.local/share/slippi-clip/dolphin/`

## Key Dependencies

- `py-slippi>=2.0.0` - Replay file parsing
- `click>=8.0.0` - CLI framework

## CLI Commands

```bash
slippi-clip scan /path/to/replays    # Parse replays, detect moments
slippi-clip find --tag ledgehog      # Query moments by tag
slippi-clip capture --tag ledgehog   # Render clips via Dolphin
slippi-clip compile clips/ -o out.mp4  # Concatenate clips
```

## Ledgehog Detection

Tags are hierarchical - all ledgehogs get the base tag, clutch variants add timing info:
- `ledgehog` - Any ledgehog (opponent grabbed ledge within 120 frames of player)
- `ledgehog:clutch` - Reaction within 60 frames
- `ledgehog:clutch:30`, `:15`, `:10`, `:5`, `:1` - Tighter timing windows

Technique tags: `ledgehog:wavedash`, `ledgehog:ramen`, `ledgehog:jump`, `ledgehog:recovery`
