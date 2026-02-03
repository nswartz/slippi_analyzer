# Slippi Replay Clipper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool that scans Slippi replays for ledgehog moments and captures them as video clips.

**Architecture:** Three-phase pipeline: (1) Scan replays with py-slippi, run detectors, store moments in SQLite; (2) Query moments by tags; (3) Capture clips via Dolphin frame dump + ffmpeg.

**Tech Stack:** Python 3.10+, py-slippi, Click, SQLite, pytest, pyright

---

## Implementation Status

| Task | Description | Status |
|------|-------------|--------|
| 1 | Project Setup | ✅ Complete |
| 2 | Core Models (TaggedMoment) | ✅ Complete |
| 3 | Database Layer - Schema | ✅ Complete |
| 4 | Database Layer - CRUD Operations | ✅ Complete |
| 5 | Detector Base Protocol | ✅ Complete |
| 6 | Ledgehog Detector - Basic Detection | ✅ Complete |
| 7 | Ledgehog Detector - Strict and Intentional Tags | ✅ Complete |
| 8 | Filename Generation | ✅ Complete |
| 9 | CLI Scaffold | ✅ Complete |
| 10 | FFmpeg Wrapper | ✅ Complete |
| 11 | Integration - Wire Up Scan Command | ✅ Complete |
| 12 | Scanner - Parse Replays with py-slippi | ✅ Complete |
| 13 | Scanner - Run Detectors (Registry + ReplayScanner) | ✅ Complete |
| 14 | Find Command - Query Implementation | ✅ Complete |
| 15 | Dolphin Automation | ✅ Complete |
| 16 | Capture Command - Full Pipeline | ✅ Complete |
| 17 | Compile Command | ✅ Complete |
| 18 | Configuration File Support | ✅ Complete |

**Status:** All 18 tasks complete. The slippi-clip CLI tool is fully implemented.

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/models.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "slippi-clip"
version = "0.1.0"
description = "Scan Slippi replays for gameplay moments and capture video clips"
requires-python = ">=3.10"
dependencies = [
    "py-slippi>=2.0.0",
    "click>=8.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pyright>=1.1.0",
]

[project.scripts]
slippi-clip = "src.cli:main"

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "strict"
```

**Step 2: Create directory structure**

Run:
```bash
mkdir -p src/detectors src/capture tests
touch src/__init__.py src/detectors/__init__.py src/capture/__init__.py tests/__init__.py
```

**Step 3: Create tests/conftest.py**

```python
"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_replay_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test replays."""
    replay_dir = tmp_path / "replays"
    replay_dir.mkdir()
    return replay_dir


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "moments.db"
```

**Step 4: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "chore: initial project structure with pyproject.toml"
```

---

## Task 2: Core Models

**Files:**
- Create: `tests/test_models.py`
- Create: `src/models.py`

**Step 1: Write failing tests for TaggedMoment**

```python
"""Tests for core data models."""

from pathlib import Path
from src.models import TaggedMoment


def test_tagged_moment_creation() -> None:
    """TaggedMoment stores replay path, frame range, tags, and metadata."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "player:sheik"],
        metadata={"opponent": "fox", "stage": "battlefield"},
    )

    assert moment.replay_path == Path("/replays/game.slp")
    assert moment.frame_start == 1000
    assert moment.frame_end == 1500
    assert "ledgehog:basic" in moment.tags
    assert moment.metadata["opponent"] == "fox"


def test_tagged_moment_frame_count() -> None:
    """TaggedMoment can calculate frame count."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=[],
        metadata={},
    )

    assert moment.frame_count == 500


def test_tagged_moment_duration_seconds() -> None:
    """TaggedMoment can calculate duration in seconds (60fps)."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=0,
        frame_end=600,  # 10 seconds at 60fps
        tags=[],
        metadata={},
    )

    assert moment.duration_seconds == 10.0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with "cannot import name 'TaggedMoment'"

**Step 3: Write minimal implementation**

```python
"""Core data models for slippi-clip."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaggedMoment:
    """A detected moment in a Slippi replay with associated tags."""

    replay_path: Path
    frame_start: int
    frame_end: int
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def frame_count(self) -> int:
        """Number of frames in this moment."""
        return self.frame_end - self.frame_start

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds (assuming 60fps)."""
        return self.frame_count / 60.0
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add TaggedMoment dataclass for storing detected moments"
```

---

## Task 3: Database Layer - Schema

**Files:**
- Create: `tests/test_database.py`
- Create: `src/database.py`

**Step 1: Write failing tests for database initialization**

```python
"""Tests for SQLite database operations."""

import sqlite3
from pathlib import Path

from src.database import MomentDatabase


def test_database_creates_tables(tmp_db_path: Path) -> None:
    """Database initializes with required tables."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    # Verify tables exist
    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "moments" in tables
    assert "tags" in tables
    assert "replays" in tables


def test_database_replays_table_schema(tmp_db_path: Path) -> None:
    """Replays table stores path and mtime for incremental scanning."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute("PRAGMA table_info(replays)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert "id" in columns
    assert "path" in columns
    assert "mtime" in columns
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with "cannot import name 'MomentDatabase'"

**Step 3: Write minimal implementation**

```python
"""SQLite database for storing detected moments."""

import sqlite3
from pathlib import Path


class MomentDatabase:
    """SQLite database for moments and replay metadata."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS replays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                mtime REAL NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS moments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                replay_id INTEGER NOT NULL,
                frame_start INTEGER NOT NULL,
                frame_end INTEGER NOT NULL,
                metadata TEXT,
                FOREIGN KEY (replay_id) REFERENCES replays(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moment_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (moment_id) REFERENCES moments(id)
            )
        """)

        conn.commit()
        conn.close()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_database.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add MomentDatabase with schema initialization"
```

---

## Task 4: Database Layer - CRUD Operations

**Files:**
- Modify: `tests/test_database.py`
- Modify: `src/database.py`

**Step 1: Write failing tests for storing and retrieving moments**

Add to `tests/test_database.py`:

```python
from src.models import TaggedMoment


def test_database_store_moment(tmp_db_path: Path) -> None:
    """Can store a TaggedMoment in the database."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "player:sheik"],
        metadata={"opponent": "fox", "stage": "battlefield"},
    )

    moment_id = db.store_moment(moment, mtime=1234567890.0)
    assert moment_id > 0


def test_database_retrieve_moments_by_tag(tmp_db_path: Path) -> None:
    """Can retrieve moments by tag."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    moment1 = TaggedMoment(
        replay_path=Path("/replays/game1.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic"],
        metadata={},
    )
    moment2 = TaggedMoment(
        replay_path=Path("/replays/game2.slp"),
        frame_start=2000,
        frame_end=2500,
        tags=["ledgehog:strict"],
        metadata={},
    )

    db.store_moment(moment1, mtime=1234567890.0)
    db.store_moment(moment2, mtime=1234567891.0)

    basic_moments = db.find_moments_by_tag("ledgehog:basic")
    assert len(basic_moments) == 1
    assert basic_moments[0].frame_start == 1000

    strict_moments = db.find_moments_by_tag("ledgehog:strict")
    assert len(strict_moments) == 1
    assert strict_moments[0].frame_start == 2000


def test_database_check_replay_needs_scan(tmp_db_path: Path) -> None:
    """Can check if replay needs scanning based on mtime."""
    db = MomentDatabase(tmp_db_path)
    db.initialize()

    replay_path = Path("/replays/game.slp")

    # Not in database yet - needs scan
    assert db.needs_scan(replay_path, current_mtime=1000.0) is True

    # Store a moment for this replay
    moment = TaggedMoment(
        replay_path=replay_path,
        frame_start=100,
        frame_end=200,
        tags=["test"],
        metadata={},
    )
    db.store_moment(moment, mtime=1000.0)

    # Same mtime - no scan needed
    assert db.needs_scan(replay_path, current_mtime=1000.0) is False

    # Newer mtime - needs scan
    assert db.needs_scan(replay_path, current_mtime=2000.0) is True
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with "MomentDatabase has no attribute 'store_moment'"

**Step 3: Write implementation**

Add to `src/database.py`:

```python
"""SQLite database for storing detected moments."""

import json
import sqlite3
from pathlib import Path

from src.models import TaggedMoment


class MomentDatabase:
    """SQLite database for moments and replay metadata."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS replays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                mtime REAL NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS moments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                replay_id INTEGER NOT NULL,
                frame_start INTEGER NOT NULL,
                frame_end INTEGER NOT NULL,
                metadata TEXT,
                FOREIGN KEY (replay_id) REFERENCES replays(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moment_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (moment_id) REFERENCES moments(id)
            )
        """)

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def store_moment(self, moment: TaggedMoment, mtime: float) -> int:
        """Store a moment in the database. Returns the moment ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Insert or update replay record
        cursor.execute(
            "INSERT OR REPLACE INTO replays (path, mtime) VALUES (?, ?)",
            (str(moment.replay_path), mtime),
        )
        replay_id = cursor.execute(
            "SELECT id FROM replays WHERE path = ?",
            (str(moment.replay_path),),
        ).fetchone()[0]

        # Insert moment
        cursor.execute(
            """INSERT INTO moments (replay_id, frame_start, frame_end, metadata)
               VALUES (?, ?, ?, ?)""",
            (replay_id, moment.frame_start, moment.frame_end, json.dumps(moment.metadata)),
        )
        moment_id: int = cursor.lastrowid  # type: ignore[assignment]

        # Insert tags
        for tag in moment.tags:
            cursor.execute(
                "INSERT INTO tags (moment_id, tag) VALUES (?, ?)",
                (moment_id, tag),
            )

        conn.commit()
        return moment_id

    def find_moments_by_tag(self, tag: str) -> list[TaggedMoment]:
        """Find all moments with a specific tag."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT r.path, m.frame_start, m.frame_end, m.metadata, m.id
            FROM moments m
            JOIN replays r ON m.replay_id = r.id
            JOIN tags t ON t.moment_id = m.id
            WHERE t.tag = ?
            """,
            (tag,),
        )

        moments: list[TaggedMoment] = []
        for row in cursor.fetchall():
            path, frame_start, frame_end, metadata_json, moment_id = row

            # Get all tags for this moment
            tag_cursor = conn.execute(
                "SELECT tag FROM tags WHERE moment_id = ?",
                (moment_id,),
            )
            tags = [r[0] for r in tag_cursor.fetchall()]

            moments.append(
                TaggedMoment(
                    replay_path=Path(path),
                    frame_start=frame_start,
                    frame_end=frame_end,
                    tags=tags,
                    metadata=json.loads(metadata_json) if metadata_json else {},
                )
            )

        return moments

    def needs_scan(self, replay_path: Path, current_mtime: float) -> bool:
        """Check if a replay needs to be scanned."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT mtime FROM replays WHERE path = ?",
            (str(replay_path),),
        )
        row = cursor.fetchone()

        if row is None:
            return True  # Not in database

        stored_mtime: float = row[0]
        return current_mtime > stored_mtime
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_database.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add CRUD operations for moments database"
```

---

## Task 5: Detector Base Protocol

**Files:**
- Create: `tests/test_detectors_base.py`
- Create: `src/detectors/base.py`

**Step 1: Write failing tests for detector protocol**

```python
"""Tests for detector base protocol."""

from pathlib import Path
from typing import Protocol

from src.detectors.base import Detector, FrameData
from src.models import TaggedMoment


def test_frame_data_structure() -> None:
    """FrameData contains player positions and states."""
    frame = FrameData(
        frame_number=100,
        player_x=0.0,
        player_y=0.0,
        player_action_state=0,
        player_stocks=4,
        opponent_x=-50.0,
        opponent_y=-100.0,
        opponent_action_state=185,  # Example: Fall
        opponent_stocks=3,
        stage_id=2,  # Fountain of Dreams
    )

    assert frame.frame_number == 100
    assert frame.opponent_stocks == 3


def test_detector_protocol_compliance() -> None:
    """Detector protocol requires name and detect methods."""

    class MockDetector:
        @property
        def name(self) -> str:
            return "mock"

        def detect(
            self, frames: list[FrameData], replay_path: Path
        ) -> list[TaggedMoment]:
            return []

    detector = MockDetector()
    # This should pass type checking - protocol compliance
    assert detector.name == "mock"
    assert detector.detect([], Path("/test.slp")) == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_detectors_base.py -v`
Expected: FAIL with "cannot import name 'Detector'"

**Step 3: Write implementation**

```python
"""Base protocol for moment detectors."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.models import TaggedMoment


@dataclass
class FrameData:
    """Game state for a single frame."""

    frame_number: int

    # Player (user) state
    player_x: float
    player_y: float
    player_action_state: int
    player_stocks: int

    # Opponent state
    opponent_x: float
    opponent_y: float
    opponent_action_state: int
    opponent_stocks: int

    # Stage
    stage_id: int


class Detector(Protocol):
    """Protocol for moment detectors."""

    @property
    def name(self) -> str:
        """Unique identifier for this detector."""
        ...

    def detect(
        self, frames: list[FrameData], replay_path: Path
    ) -> list[TaggedMoment]:
        """Analyze frames and return detected moments."""
        ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_detectors_base.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/detectors/base.py tests/test_detectors_base.py
git commit -m "feat: add Detector protocol and FrameData dataclass"
```

---

## Task 6: Ledgehog Detector - Basic Detection

**Files:**
- Create: `tests/test_ledgehog_detector.py`
- Create: `src/detectors/ledgehog.py`

**Step 1: Write failing tests for basic ledgehog detection**

```python
"""Tests for ledgehog detector."""

from pathlib import Path

from src.detectors.base import FrameData
from src.detectors.ledgehog import LedgehogDetector, ActionState, STAGE_EDGES


def make_frame(
    frame_number: int,
    player_x: float = 0.0,
    player_y: float = 0.0,
    player_action: int = 0,
    player_stocks: int = 4,
    opponent_x: float = 0.0,
    opponent_y: float = 0.0,
    opponent_action: int = 0,
    opponent_stocks: int = 4,
    stage_id: int = 2,  # Fountain of Dreams
) -> FrameData:
    """Helper to create FrameData for tests."""
    return FrameData(
        frame_number=frame_number,
        player_x=player_x,
        player_y=player_y,
        player_action_state=player_action,
        player_stocks=player_stocks,
        opponent_x=opponent_x,
        opponent_y=opponent_y,
        opponent_action_state=opponent_action,
        opponent_stocks=opponent_stocks,
        stage_id=stage_id,
    )


def test_ledgehog_detector_name() -> None:
    """Detector has correct name."""
    detector = LedgehogDetector()
    assert detector.name == "ledgehog"


def test_no_detection_when_not_on_ledge() -> None:
    """No ledgehog detected when player is not on ledge."""
    detector = LedgehogDetector()
    frames = [
        make_frame(i, player_action=ActionState.WAIT)
        for i in range(100)
    ]

    moments = detector.detect(frames, Path("/test.slp"))
    assert len(moments) == 0


def test_basic_ledgehog_detection() -> None:
    """Detect basic ledgehog: player on ledge, opponent offstage, opponent dies."""
    detector = LedgehogDetector()
    stage_id = 2  # Fountain of Dreams
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames (frames 0-99)
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id))

    # Player grabs ledge, opponent is offstage (frames 100-150)
    for i in range(100, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,  # Past the edge
                opponent_y=-50.0,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock (frame 150+)
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                player_x=0.0,
                player_action=ActionState.WAIT,
                opponent_stocks=2,  # Lost a stock
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:basic" in moments[0].tags
    # Moment should start 5 seconds (300 frames) before the ledgehog,
    # but clamped to frame 0 since the ledgehog is at frame 100
    assert moments[0].frame_start >= 0
    # Moment should end after the stock loss
    assert moments[0].frame_end >= 150
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ledgehog_detector.py -v`
Expected: FAIL with "cannot import name 'LedgehogDetector'"

**Step 3: Write implementation**

```python
"""Ledgehog moment detector."""

from dataclasses import dataclass
from pathlib import Path

from src.detectors.base import FrameData
from src.models import TaggedMoment


class ActionState:
    """Melee action state constants (subset relevant for detection)."""

    WAIT = 14  # Standing
    CLIFF_WAIT = 253  # Holding ledge
    CLIFF_CATCH = 252  # Grabbing ledge
    DAMAGE_FALL = 38  # Tumble
    FALL = 29  # Falling
    FALL_SPECIAL = 35  # Helpless fall


# Stage edge x-coordinates (absolute value, edges are symmetric)
# These are approximate values for legal stages
STAGE_EDGES: dict[int, float] = {
    2: 63.35,   # Fountain of Dreams
    3: 56.0,    # Pokemon Stadium
    8: 68.4,    # Yoshi's Story
    28: 71.3,   # Dream Land
    31: 68.4,   # Battlefield
    32: 85.6,   # Final Destination
}


@dataclass
class LedgehogEvent:
    """Internal tracking for a potential ledgehog."""

    ledge_grab_frame: int
    opponent_offstage_frame: int
    initiating_hit_frame: int | None = None


class LedgehogDetector:
    """Detects ledgehog moments in replays."""

    FRAMES_BEFORE = 300  # 5 seconds at 60fps
    FRAMES_AFTER = 120   # 2 seconds at 60fps

    @property
    def name(self) -> str:
        return "ledgehog"

    def detect(
        self, frames: list[FrameData], replay_path: Path
    ) -> list[TaggedMoment]:
        """Analyze frames and return detected ledgehog moments."""
        if not frames:
            return []

        moments: list[TaggedMoment] = []
        stage_id = frames[0].stage_id
        edge_x = STAGE_EDGES.get(stage_id, 70.0)  # Default if unknown stage

        # Track state across frames
        tracking_event: LedgehogEvent | None = None
        prev_opponent_stocks = frames[0].opponent_stocks if frames else 4

        for frame in frames:
            player_on_ledge = frame.player_action_state in (
                ActionState.CLIFF_WAIT,
                ActionState.CLIFF_CATCH,
            )
            opponent_offstage = abs(frame.opponent_x) > edge_x

            # Start tracking when player grabs ledge and opponent is offstage
            if player_on_ledge and opponent_offstage and tracking_event is None:
                tracking_event = LedgehogEvent(
                    ledge_grab_frame=frame.frame_number,
                    opponent_offstage_frame=frame.frame_number,
                )

            # Check for stock loss while tracking
            if tracking_event is not None:
                if frame.opponent_stocks < prev_opponent_stocks:
                    # Ledgehog confirmed!
                    frame_start = max(
                        0, tracking_event.ledge_grab_frame - self.FRAMES_BEFORE
                    )
                    frame_end = min(
                        len(frames) - 1,
                        frame.frame_number + self.FRAMES_AFTER,
                    )

                    moments.append(
                        TaggedMoment(
                            replay_path=replay_path,
                            frame_start=frame_start,
                            frame_end=frame_end,
                            tags=["ledgehog:basic"],
                            metadata={},
                        )
                    )
                    tracking_event = None

                # Cancel tracking if player leaves ledge without opponent dying
                elif not player_on_ledge:
                    tracking_event = None

            prev_opponent_stocks = frame.opponent_stocks

        return moments
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ledgehog_detector.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/detectors/ledgehog.py tests/test_ledgehog_detector.py
git commit -m "feat: add basic ledgehog detection"
```

---

## Task 7: Ledgehog Detector - Strict and Intentional Tags

**Files:**
- Modify: `tests/test_ledgehog_detector.py`
- Modify: `src/detectors/ledgehog.py`

**Step 1: Write failing tests for strict and intentional detection**

Add to `tests/test_ledgehog_detector.py`:

```python
def test_strict_ledgehog_detection() -> None:
    """Detect strict ledgehog: opponent in helpless/recovery state."""
    detector = LedgehogDetector()
    stage_id = 2
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id))

    # Player on ledge, opponent in helpless fall (recovery state)
    for i in range(100, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,
                opponent_y=-50.0,
                opponent_action=ActionState.FALL_SPECIAL,  # Helpless
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=2,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:basic" in moments[0].tags
    assert "ledgehog:strict" in moments[0].tags


def test_intentional_ledgehog_detection() -> None:
    """Detect intentional ledgehog: grabbed ledge within 60 frames of opponent recovery."""
    detector = LedgehogDetector()
    stage_id = 2
    edge_x = STAGE_EDGES[stage_id]

    frames: list[FrameData] = []

    # Neutral frames
    for i in range(100):
        frames.append(make_frame(i, stage_id=stage_id))

    # Opponent goes into recovery state at frame 100
    for i in range(100, 110):
        frames.append(
            make_frame(
                i,
                opponent_x=edge_x + 20.0,
                opponent_y=-50.0,
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    # Player grabs ledge at frame 110 (within 60 frames of recovery start)
    for i in range(110, 150):
        frames.append(
            make_frame(
                i,
                player_x=edge_x,
                player_y=-10.0,
                player_action=ActionState.CLIFF_WAIT,
                opponent_x=edge_x + 20.0,
                opponent_y=-80.0,
                opponent_action=ActionState.FALL_SPECIAL,
                opponent_stocks=3,
                stage_id=stage_id,
            )
        )

    # Opponent loses stock
    for i in range(150, 200):
        frames.append(
            make_frame(
                i,
                opponent_stocks=2,
                stage_id=stage_id,
            )
        )

    moments = detector.detect(frames, Path("/test.slp"))

    assert len(moments) == 1
    assert "ledgehog:basic" in moments[0].tags
    assert "ledgehog:strict" in moments[0].tags
    assert "ledgehog:intentional" in moments[0].tags
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ledgehog_detector.py -v`
Expected: FAIL - "ledgehog:strict" not in tags

**Step 3: Update implementation**

Replace `src/detectors/ledgehog.py` with:

```python
"""Ledgehog moment detector."""

from dataclasses import dataclass
from pathlib import Path

from src.detectors.base import FrameData
from src.models import TaggedMoment


class ActionState:
    """Melee action state constants (subset relevant for detection)."""

    WAIT = 14  # Standing
    CLIFF_WAIT = 253  # Holding ledge
    CLIFF_CATCH = 252  # Grabbing ledge
    DAMAGE_FALL = 38  # Tumble
    FALL = 29  # Falling
    FALL_SPECIAL = 35  # Helpless fall

    RECOVERY_STATES = {DAMAGE_FALL, FALL, FALL_SPECIAL}


# Stage edge x-coordinates (absolute value, edges are symmetric)
STAGE_EDGES: dict[int, float] = {
    2: 63.35,   # Fountain of Dreams
    3: 56.0,    # Pokemon Stadium
    8: 68.4,    # Yoshi's Story
    28: 71.3,   # Dream Land
    31: 68.4,   # Battlefield
    32: 85.6,   # Final Destination
}


@dataclass
class LedgehogEvent:
    """Internal tracking for a potential ledgehog."""

    ledge_grab_frame: int
    opponent_offstage_frame: int
    opponent_recovery_start_frame: int | None = None
    opponent_was_in_recovery: bool = False


class LedgehogDetector:
    """Detects ledgehog moments in replays."""

    FRAMES_BEFORE = 300  # 5 seconds at 60fps
    FRAMES_AFTER = 120   # 2 seconds at 60fps
    INTENTIONAL_WINDOW = 60  # ~1 second

    @property
    def name(self) -> str:
        return "ledgehog"

    def detect(
        self, frames: list[FrameData], replay_path: Path
    ) -> list[TaggedMoment]:
        """Analyze frames and return detected ledgehog moments."""
        if not frames:
            return []

        moments: list[TaggedMoment] = []
        stage_id = frames[0].stage_id
        edge_x = STAGE_EDGES.get(stage_id, 70.0)

        tracking_event: LedgehogEvent | None = None
        prev_opponent_stocks = frames[0].opponent_stocks
        opponent_recovery_start: int | None = None
        prev_opponent_in_recovery = False

        for frame in frames:
            player_on_ledge = frame.player_action_state in (
                ActionState.CLIFF_WAIT,
                ActionState.CLIFF_CATCH,
            )
            opponent_offstage = abs(frame.opponent_x) > edge_x
            opponent_in_recovery = (
                frame.opponent_action_state in ActionState.RECOVERY_STATES
            )

            # Track when opponent enters recovery state
            if opponent_in_recovery and not prev_opponent_in_recovery:
                opponent_recovery_start = frame.frame_number

            # Start tracking when player grabs ledge and opponent is offstage
            if player_on_ledge and opponent_offstage and tracking_event is None:
                tracking_event = LedgehogEvent(
                    ledge_grab_frame=frame.frame_number,
                    opponent_offstage_frame=frame.frame_number,
                    opponent_recovery_start_frame=opponent_recovery_start,
                    opponent_was_in_recovery=opponent_in_recovery,
                )

            # Update tracking if opponent enters recovery while we're tracking
            if tracking_event is not None and opponent_in_recovery:
                tracking_event.opponent_was_in_recovery = True
                if tracking_event.opponent_recovery_start_frame is None:
                    tracking_event.opponent_recovery_start_frame = frame.frame_number

            # Check for stock loss while tracking
            if tracking_event is not None:
                if frame.opponent_stocks < prev_opponent_stocks:
                    # Ledgehog confirmed!
                    tags = ["ledgehog:basic"]

                    # Strict: opponent was in recovery state
                    if tracking_event.opponent_was_in_recovery:
                        tags.append("ledgehog:strict")

                        # Intentional: grabbed ledge within window of recovery start
                        if tracking_event.opponent_recovery_start_frame is not None:
                            frames_since_recovery = (
                                tracking_event.ledge_grab_frame
                                - tracking_event.opponent_recovery_start_frame
                            )
                            if 0 <= frames_since_recovery <= self.INTENTIONAL_WINDOW:
                                tags.append("ledgehog:intentional")

                    frame_start = max(
                        0, tracking_event.ledge_grab_frame - self.FRAMES_BEFORE
                    )
                    frame_end = min(
                        len(frames) - 1,
                        frame.frame_number + self.FRAMES_AFTER,
                    )

                    moments.append(
                        TaggedMoment(
                            replay_path=replay_path,
                            frame_start=frame_start,
                            frame_end=frame_end,
                            tags=tags,
                            metadata={},
                        )
                    )
                    tracking_event = None
                    opponent_recovery_start = None

                elif not player_on_ledge:
                    tracking_event = None

            prev_opponent_stocks = frame.opponent_stocks
            prev_opponent_in_recovery = opponent_in_recovery

        return moments
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ledgehog_detector.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/detectors/ledgehog.py tests/test_ledgehog_detector.py
git commit -m "feat: add strict and intentional ledgehog detection"
```

---

## Task 8: Filename Generation

**Files:**
- Create: `tests/test_filename.py`
- Modify: `src/models.py`

**Step 1: Write failing tests for filename generation**

```python
"""Tests for filename generation."""

from datetime import date
from pathlib import Path

from src.models import TaggedMoment, generate_clip_filename


def test_generate_clip_filename_basic() -> None:
    """Generate descriptive filename from moment metadata."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:strict"],
        metadata={
            "date": "2025-01-15",
            "player": "sheik",
            "opponent": "fox",
            "stage": "battlefield",
        },
    )

    filename = generate_clip_filename(moment, index=1)
    assert filename == "2025-01-15_sheik_vs-fox_battlefield_ledgehog-strict_001.mp4"


def test_generate_clip_filename_multiple_tags() -> None:
    """Use most specific ledgehog tag in filename."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "ledgehog:strict", "ledgehog:intentional"],
        metadata={
            "date": "2025-01-15",
            "player": "sheik",
            "opponent": "marth",
            "stage": "yoshis",
        },
    )

    filename = generate_clip_filename(moment, index=5)
    # Should use intentional (most specific)
    assert filename == "2025-01-15_sheik_vs-marth_yoshis_ledgehog-intentional_005.mp4"


def test_generate_clip_filename_missing_metadata() -> None:
    """Handle missing metadata gracefully."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic"],
        metadata={},
    )

    filename = generate_clip_filename(moment, index=1)
    assert filename == "unknown_unknown_vs-unknown_unknown_ledgehog-basic_001.mp4"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_filename.py -v`
Expected: FAIL with "cannot import name 'generate_clip_filename'"

**Step 3: Add implementation to models.py**

Add to `src/models.py`:

```python
def generate_clip_filename(moment: TaggedMoment, index: int) -> str:
    """Generate a descriptive filename for a clip.

    Format: {date}_{player}_vs-{opponent}_{stage}_{primary_tag}_{index:03d}.mp4
    """
    # Get metadata with defaults
    date_str = moment.metadata.get("date", "unknown")
    player = moment.metadata.get("player", "unknown")
    opponent = moment.metadata.get("opponent", "unknown")
    stage = moment.metadata.get("stage", "unknown")

    # Find the most specific ledgehog tag
    tag_priority = ["ledgehog:intentional", "ledgehog:strict", "ledgehog:basic"]
    primary_tag = "unknown"
    for tag in tag_priority:
        if tag in moment.tags:
            primary_tag = tag.replace(":", "-")
            break

    return f"{date_str}_{player}_vs-{opponent}_{stage}_{primary_tag}_{index:03d}.mp4"
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_filename.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/models.py tests/test_filename.py
git commit -m "feat: add clip filename generation"
```

---

## Task 9: CLI Scaffold

**Files:**
- Create: `tests/test_cli.py`
- Create: `src/cli.py`

**Step 1: Write failing tests for CLI basics**

```python
"""Tests for CLI interface."""

from click.testing import CliRunner

from src.cli import main


def test_cli_help() -> None:
    """CLI shows help message."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "slippi-clip" in result.output.lower() or "usage" in result.output.lower()


def test_cli_scan_command_exists() -> None:
    """CLI has scan command."""
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--help"])

    assert result.exit_code == 0
    assert "scan" in result.output.lower()


def test_cli_find_command_exists() -> None:
    """CLI has find command."""
    runner = CliRunner()
    result = runner.invoke(main, ["find", "--help"])

    assert result.exit_code == 0
    assert "find" in result.output.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with "cannot import name 'main'"

**Step 3: Write implementation**

```python
"""CLI interface for slippi-clip."""

from pathlib import Path

import click


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Slippi-clip: Scan replays for moments and capture video clips."""
    pass


@main.command()
@click.argument("replay_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--full-rescan", is_flag=True, help="Re-scan all files, ignoring cache")
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def scan(replay_dir: Path, full_rescan: bool, db: Path) -> None:
    """Scan replay directory for moments."""
    click.echo(f"Scanning {replay_dir}...")
    click.echo(f"Database: {db}")
    if full_rescan:
        click.echo("Full rescan enabled")
    # TODO: Implement scanning logic
    click.echo("Scan complete (not implemented yet)")


@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("--opponent", help="Filter by opponent character")
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def find(tag: tuple[str, ...], opponent: str | None, db: Path) -> None:
    """Find moments matching criteria."""
    click.echo(f"Finding moments in {db}")
    if tag:
        click.echo(f"Tags: {', '.join(tag)}")
    if opponent:
        click.echo(f"Opponent: {opponent}")
    # TODO: Implement query logic
    click.echo("Find complete (not implemented yet)")


@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def capture(tag: tuple[str, ...], output: Path, db: Path) -> None:
    """Capture video clips for matching moments."""
    click.echo(f"Capturing clips to {output}")
    # TODO: Implement capture logic
    click.echo("Capture complete (not implemented yet)")


@main.command()
@click.argument("clips_dir", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
def compile(clips_dir: Path, output: Path) -> None:
    """Compile clips into a single video."""
    click.echo(f"Compiling {clips_dir} to {output}")
    # TODO: Implement compile logic
    click.echo("Compile complete (not implemented yet)")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: add CLI scaffold with scan, find, capture, compile commands"
```

---

## Task 10: FFmpeg Wrapper

**Files:**
- Create: `tests/test_ffmpeg.py`
- Create: `src/capture/ffmpeg.py`

**Step 1: Write failing tests for ffmpeg command building**

```python
"""Tests for ffmpeg wrapper."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.capture.ffmpeg import FFmpegEncoder, build_encode_command


def test_build_encode_command() -> None:
    """Build correct ffmpeg command for encoding frames to video."""
    cmd = build_encode_command(
        frame_pattern=Path("/tmp/frames/frame_%05d.png"),
        audio_file=Path("/tmp/audio.wav"),
        output_file=Path("/output/clip.mp4"),
        fps=60,
    )

    assert "ffmpeg" in cmd[0]
    assert "-framerate" in cmd
    assert "60" in cmd
    assert "-i" in cmd
    assert str(Path("/tmp/frames/frame_%05d.png")) in cmd
    assert str(Path("/output/clip.mp4")) in cmd


def test_build_encode_command_no_audio() -> None:
    """Build ffmpeg command without audio."""
    cmd = build_encode_command(
        frame_pattern=Path("/tmp/frames/frame_%05d.png"),
        audio_file=None,
        output_file=Path("/output/clip.mp4"),
        fps=60,
    )

    assert "-i" in cmd
    # Should only have one -i (for video), not two
    assert cmd.count("-i") == 1


def test_ffmpeg_encoder_encode(tmp_path: Path) -> None:
    """FFmpegEncoder calls subprocess with correct command."""
    encoder = FFmpegEncoder()

    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()

    # Create dummy frame files
    for i in range(10):
        (frame_dir / f"frame_{i:05d}.png").touch()

    output_file = tmp_path / "output.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        encoder.encode(
            frame_dir=frame_dir,
            output_file=output_file,
            fps=60,
        )

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args[0]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ffmpeg.py -v`
Expected: FAIL with "cannot import name 'FFmpegEncoder'"

**Step 3: Write implementation**

```python
"""FFmpeg wrapper for encoding video clips."""

import subprocess
from pathlib import Path


def build_encode_command(
    frame_pattern: Path,
    audio_file: Path | None,
    output_file: Path,
    fps: int = 60,
) -> list[str]:
    """Build ffmpeg command for encoding frames to video.

    Args:
        frame_pattern: Path pattern for input frames (e.g., /tmp/frame_%05d.png)
        audio_file: Optional path to audio file
        output_file: Path for output video
        fps: Frames per second

    Returns:
        Command as list of strings
    """
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-framerate", str(fps),
        "-i", str(frame_pattern),
    ]

    if audio_file is not None:
        cmd.extend(["-i", str(audio_file)])
        cmd.extend(["-c:a", "aac"])

    cmd.extend([
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        str(output_file),
    ])

    return cmd


class FFmpegEncoder:
    """Encodes frame sequences to video files."""

    def encode(
        self,
        frame_dir: Path,
        output_file: Path,
        fps: int = 60,
        audio_file: Path | None = None,
    ) -> None:
        """Encode frames in directory to video file.

        Args:
            frame_dir: Directory containing numbered frame images
            output_file: Output video path
            fps: Frames per second
            audio_file: Optional audio file to mux
        """
        # Find frame pattern
        frames = sorted(frame_dir.glob("frame_*.png"))
        if not frames:
            raise ValueError(f"No frames found in {frame_dir}")

        # Determine pattern (assumes frame_00000.png format)
        frame_pattern = frame_dir / "frame_%05d.png"

        cmd = build_encode_command(
            frame_pattern=frame_pattern,
            audio_file=audio_file,
            output_file=output_file,
            fps=fps,
        )

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ffmpeg.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/capture/ffmpeg.py tests/test_ffmpeg.py
git commit -m "feat: add FFmpeg encoder wrapper"
```

---

## Task 11: Integration - Wire Up Scan Command

**Files:**
- Modify: `src/cli.py`
- Modify: `tests/test_cli.py`

**Note:** This task connects the pieces. Full integration with py-slippi requires real replay files, so we'll structure the code to be testable with mocks and verify the wiring works.

**Step 1: Write integration test for scan command**

Add to `tests/test_cli.py`:

```python
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_scan_initializes_database(tmp_path: Path) -> None:
    """Scan command initializes database."""
    runner = CliRunner()

    replay_dir = tmp_path / "replays"
    replay_dir.mkdir()

    db_path = tmp_path / "test.db"

    result = runner.invoke(main, [
        "scan",
        str(replay_dir),
        "--db", str(db_path),
    ])

    assert result.exit_code == 0
    assert db_path.exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_scan_initializes_database -v`
Expected: FAIL - database not created

**Step 3: Update CLI to initialize database**

Update the `scan` function in `src/cli.py`:

```python
from src.database import MomentDatabase


@main.command()
@click.argument("replay_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--full-rescan", is_flag=True, help="Re-scan all files, ignoring cache")
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def scan(replay_dir: Path, full_rescan: bool, db: Path) -> None:
    """Scan replay directory for moments."""
    # Ensure parent directory exists
    db.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Scanning {replay_dir}...")
    click.echo(f"Database: {db}")

    # Initialize database
    database = MomentDatabase(db)
    database.initialize()

    if full_rescan:
        click.echo("Full rescan enabled")

    # Find all .slp files
    replay_files = list(replay_dir.glob("**/*.slp"))
    click.echo(f"Found {len(replay_files)} replay files")

    # TODO: Parse replays and run detectors
    click.echo("Scan complete")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: wire up scan command with database initialization"
```

---

## Task 12: Scanner - Parse Replays with py-slippi

> **✅ IMPLEMENTED** - This task has been completed. See `src/scanner.py` and `tests/test_scanner.py`.

**Files:**
- Create: `tests/test_scanner.py`
- Create: `src/scanner.py`

**Step 1: Write failing tests for replay parsing**

```python
"""Tests for replay scanner."""

from pathlib import Path

import pytest

from src.detectors.base import FrameData
from src.scanner import parse_replay_to_frames


def test_parse_replay_returns_frame_data_list() -> None:
    """parse_replay_to_frames returns list of FrameData for each opponent."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    # This is a doubles match (4 players), so we get frames for each opponent
    # When player_port=0 (Sheik), opponents are ports 2 and 3 (Fox and Peach)
    result = parse_replay_to_frames(replay_path, player_port=0)

    # Should return a dict mapping opponent port to frame list
    assert isinstance(result, dict)
    # In doubles, Sheik (port 0) has 2 opponents (ports 2, 3)
    assert len(result) >= 1  # At least one opponent

    # Each opponent's frames should be a list of FrameData
    for _, frames in result.items():
        assert isinstance(frames, list)
        assert len(frames) > 0
        assert isinstance(frames[0], FrameData)


def test_frame_data_has_correct_stage_id() -> None:
    """FrameData should have correct stage ID from replay."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    result = parse_replay_to_frames(replay_path, player_port=0)
    # Get frames for any opponent
    frames = next(iter(result.values()))

    # Stage 31 = Battlefield
    assert frames[0].stage_id == 31


def test_frame_data_tracks_positions() -> None:
    """FrameData should track player and opponent positions."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    result = parse_replay_to_frames(replay_path, player_port=0)
    frames = next(iter(result.values()))

    # Positions should be floats
    assert isinstance(frames[0].player_x, float)
    assert isinstance(frames[0].player_y, float)
    assert isinstance(frames[0].opponent_x, float)
    assert isinstance(frames[0].opponent_y, float)


def test_frame_data_tracks_stocks() -> None:
    """FrameData should track player and opponent stocks."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    result = parse_replay_to_frames(replay_path, player_port=0)
    frames = next(iter(result.values()))

    # Game starts with 4 stocks each
    assert frames[0].player_stocks == 4
    assert frames[0].opponent_stocks == 4
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scanner.py -v`
Expected: FAIL with "cannot import name 'parse_replay_to_frames'"

**Step 3: Write implementation**

```python
"""Replay scanner for parsing .slp files to FrameData."""

from pathlib import Path

from slippi import Game

from src.detectors.base import FrameData


def parse_replay_to_frames(
    replay_path: Path,
    player_port: int,
) -> dict[int, list[FrameData]]:
    """Parse a .slp replay file into FrameData for each opponent.

    For singles matches, returns a single entry.
    For doubles matches, returns one entry per opponent (teammates excluded).

    Args:
        replay_path: Path to the .slp file
        player_port: Port index of the player (0-3)

    Returns:
        Dictionary mapping opponent port to list of FrameData
    """
    game = Game(replay_path)

    if game.start is None:
        raise ValueError(f"Replay has no start data: {replay_path}")

    # Determine stage
    stage_id = game.start.stage.value

    # Get player's team (if teams mode)
    player_info = game.start.players[player_port]
    if player_info is None:
        raise ValueError(f"No player at port {player_port}")

    player_team = player_info.team if game.start.is_teams else None

    # Find opponent ports (different team or all others in singles)
    opponent_ports: list[int] = []
    for port_idx, player in enumerate(game.start.players):
        if player is None:
            continue
        if port_idx == player_port:
            continue
        # In teams mode, opponent is on different team
        if player_team is not None:
            if player.team != player_team:
                opponent_ports.append(port_idx)
        else:
            # Singles mode - everyone else is opponent
            opponent_ports.append(port_idx)

    # Build FrameData for each opponent
    result: dict[int, list[FrameData]] = {}

    for opp_port in opponent_ports:
        frames: list[FrameData] = []

        for frame in game.frames:
            # Skip countdown frames (negative index)
            if frame.index < 0:
                continue

            player_port_data = frame.ports[player_port]
            opp_port_data = frame.ports[opp_port]

            # Skip if either port has no data
            if player_port_data is None or opp_port_data is None:
                continue

            player_post = player_port_data.leader.post
            opp_post = opp_port_data.leader.post

            # Skip if post-frame data not available
            if player_post is None or opp_post is None:
                continue

            frames.append(
                FrameData(
                    frame_number=frame.index,
                    player_x=player_post.position.x,
                    player_y=player_post.position.y,
                    player_action_state=player_post.state,
                    player_stocks=player_post.stocks,
                    opponent_x=opp_post.position.x,
                    opponent_y=opp_post.position.y,
                    opponent_action_state=opp_post.state,
                    opponent_stocks=opp_post.stocks,
                    stage_id=stage_id,
                )
            )

        result[opp_port] = frames

    return result
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scanner.py -v`
Expected: PASS (4 tests) - or SKIP if fixture not available

**Step 5: Commit**

```bash
git add src/scanner.py tests/test_scanner.py
git commit -m "feat: add replay scanner for parsing .slp files to FrameData"
```

---

## Task 13: Scanner - Run Detectors (Detector Registry + ReplayScanner)

> **✅ IMPLEMENTED** - This task has been completed. See `src/detectors/registry.py`, `src/scanner.py` (ReplayScanner class), and tests.

**Files:**
- Create: `tests/test_detector_registry.py`
- Create: `src/detectors/registry.py`
- Modify: `src/scanner.py` (add ReplayScanner class)
- Modify: `tests/test_scanner.py` (add ReplayScanner tests)

**Step 1: Write failing tests for detector registry**

```python
"""Tests for detector registry and integration."""

from pathlib import Path

from src.detectors.base import FrameData
from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment


class MockDetector:
    """A mock detector for testing."""

    def __init__(self, name: str = "mock", moments_to_return: list[TaggedMoment] | None = None) -> None:
        self._name = name
        self._moments = moments_to_return or []
        self.detect_called_with: list[FrameData] | None = None

    @property
    def name(self) -> str:
        return self._name

    def detect(self, frames: list[FrameData], replay_path: Path) -> list[TaggedMoment]:
        self.detect_called_with = frames
        return self._moments


def test_registry_register_detector() -> None:
    """Registry can register detectors."""
    registry = DetectorRegistry()
    detector = MockDetector("test")

    registry.register(detector)

    assert "test" in registry.detector_names


def test_registry_get_detector() -> None:
    """Registry can retrieve registered detector by name."""
    registry = DetectorRegistry()
    detector = MockDetector("test")
    registry.register(detector)

    retrieved = registry.get("test")

    assert retrieved is detector


def test_registry_run_all_detectors() -> None:
    """Registry runs all registered detectors on frames."""
    registry = DetectorRegistry()

    # Create mock detectors that return moments
    moment1 = TaggedMoment(
        replay_path=Path("/test.slp"),
        frame_start=100,
        frame_end=200,
        tags=["detector1:tag"],
        metadata={},
    )
    moment2 = TaggedMoment(
        replay_path=Path("/test.slp"),
        frame_start=300,
        frame_end=400,
        tags=["detector2:tag"],
        metadata={},
    )

    detector1 = MockDetector("detector1", [moment1])
    detector2 = MockDetector("detector2", [moment2])

    registry.register(detector1)
    registry.register(detector2)

    frames = [
        FrameData(
            frame_number=i,
            player_x=0.0,
            player_y=0.0,
            player_action_state=0,
            player_stocks=4,
            opponent_x=0.0,
            opponent_y=0.0,
            opponent_action_state=0,
            opponent_stocks=4,
            stage_id=31,
        )
        for i in range(10)
    ]

    moments = registry.run_all(frames, Path("/test.slp"))

    # Both detectors should have been called
    assert detector1.detect_called_with == frames
    assert detector2.detect_called_with == frames

    # Should return moments from both detectors
    assert len(moments) == 2
    assert moment1 in moments
    assert moment2 in moments


def test_registry_default_detectors() -> None:
    """Default registry includes ledgehog detector."""
    registry = DetectorRegistry.with_default_detectors()

    assert "ledgehog" in registry.detector_names
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_detector_registry.py -v`
Expected: FAIL with "cannot import name 'DetectorRegistry'"

**Step 3: Write registry implementation**

Create `src/detectors/registry.py`:

```python
"""Detector registry for managing and running moment detectors."""

from pathlib import Path

from src.detectors.base import Detector, FrameData
from src.models import TaggedMoment


class DetectorRegistry:
    """Registry for managing moment detectors."""

    def __init__(self) -> None:
        self._detectors: dict[str, Detector] = {}

    def register(self, detector: Detector) -> None:
        """Register a detector."""
        self._detectors[detector.name] = detector

    def get(self, name: str) -> Detector | None:
        """Get a detector by name."""
        return self._detectors.get(name)

    @property
    def detector_names(self) -> list[str]:
        """List of registered detector names."""
        return list(self._detectors.keys())

    def run_all(
        self, frames: list[FrameData], replay_path: Path
    ) -> list[TaggedMoment]:
        """Run all registered detectors on frames."""
        all_moments: list[TaggedMoment] = []

        for detector in self._detectors.values():
            moments = detector.detect(frames, replay_path)
            all_moments.extend(moments)

        return all_moments

    @classmethod
    def with_default_detectors(cls) -> "DetectorRegistry":
        """Create a registry with default detectors."""
        from src.detectors.ledgehog import LedgehogDetector

        registry = cls()
        registry.register(LedgehogDetector())
        return registry
```

**Step 4: Write ReplayScanner class tests**

Add to `tests/test_scanner.py`:

```python
from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment
from src.scanner import ReplayScanner


def test_replay_scanner_extracts_metadata() -> None:
    """ReplayScanner extracts metadata from replay."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    scanner = ReplayScanner()
    metadata = scanner.get_metadata(replay_path)

    assert "date" in metadata
    assert "stage" in metadata
    assert "player" in metadata  # Character name


def test_replay_scanner_identifies_teammates_vs_opponents() -> None:
    """ReplayScanner correctly identifies teammates vs opponents in doubles."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    scanner = ReplayScanner()
    # Port 0 = Sheik, Port 1 = Marth (teammate), Ports 2,3 = opponents (Fox, Peach)
    opponents = scanner.get_opponent_ports(replay_path, player_port=0)

    # In doubles, should identify port 2 and 3 as opponents
    # Port 0 and 1 are on the same team
    assert 0 not in opponents  # Self is not an opponent
    assert 1 not in opponents  # Teammate is not an opponent
    assert 2 in opponents or 3 in opponents  # At least one opponent identified


def test_replay_scanner_scan_replay_runs_detectors(tmp_path: Path) -> None:
    """ReplayScanner.scan_replay runs detectors and returns moments."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    scanner = ReplayScanner()
    registry = DetectorRegistry.with_default_detectors()

    # Scan the replay
    moments = scanner.scan_replay(
        replay_path=replay_path,
        player_port=0,
        registry=registry,
    )

    # Should return a list of moments (may be empty if no ledgehogs in this replay)
    assert isinstance(moments, list)
    for moment in moments:
        assert isinstance(moment, TaggedMoment)


def test_replay_scanner_scan_replay_adds_metadata(tmp_path: Path) -> None:
    """ReplayScanner.scan_replay adds replay metadata to moments."""
    replay_path = Path("tests/fixtures/Game_20251114T001152.slp")
    if not replay_path.exists():
        pytest.skip("Test fixture not available")

    # Create a mock detector that always returns a moment
    class AlwaysDetectMock:
        @property
        def name(self) -> str:
            return "always"

        def detect(
            self, frames: list[FrameData], replay_path: Path
        ) -> list[TaggedMoment]:
            if frames:
                return [
                    TaggedMoment(
                        replay_path=replay_path,
                        frame_start=0,
                        frame_end=100,
                        tags=["test:always"],
                        metadata={},
                    )
                ]
            return []

    scanner = ReplayScanner()
    registry = DetectorRegistry()
    registry.register(AlwaysDetectMock())

    moments = scanner.scan_replay(
        replay_path=replay_path,
        player_port=0,
        registry=registry,
    )

    # Should have moments with metadata filled in
    assert len(moments) >= 1
    moment = moments[0]
    assert "date" in moment.metadata
    assert "stage" in moment.metadata
    assert "player" in moment.metadata
    assert "opponent" in moment.metadata
```

**Step 5: Write ReplayScanner implementation**

Add to `src/scanner.py`:

```python
from slippi.id import CSSCharacter

from src.detectors.registry import DetectorRegistry
from src.models import TaggedMoment


# Map stage IDs to readable names (lowercase, no spaces)
STAGE_NAMES: dict[int, str] = {
    2: "fountain",
    3: "stadium",
    8: "yoshis",
    28: "dreamland",
    31: "battlefield",
    32: "fd",
}


def get_character_name(char: CSSCharacter) -> str:
    """Get lowercase character name from CSS character enum."""
    return char.name.lower().replace("_", "")


class ReplayScanner:
    """Scanner for extracting moments from Slippi replays."""

    def get_metadata(self, replay_path: Path) -> dict[str, str]:
        """Extract metadata from a replay file.

        Returns dict with: date, stage, player (character name)
        """
        game = Game(replay_path)

        # Date
        date_str = "unknown"
        if game.metadata is not None and game.metadata.date is not None:
            date_str = game.metadata.date.strftime("%Y-%m-%d")

        # Stage
        stage_name = "unknown"
        player_char = "unknown"
        if game.start is not None:
            stage_id = game.start.stage.value
            stage_name = STAGE_NAMES.get(stage_id, "unknown")

            # Find first human player's character (assume port 0 for now)
            for player in game.start.players:
                if player is not None:
                    player_char = get_character_name(player.character)
                    break

        return {
            "date": date_str,
            "stage": stage_name,
            "player": player_char,
        }

    def get_opponent_ports(self, replay_path: Path, player_port: int) -> list[int]:
        """Get list of opponent port indices.

        In singles, returns all other ports.
        In doubles, returns only ports on opposing team.
        """
        game = Game(replay_path)

        if game.start is None:
            return []

        player_info = game.start.players[player_port]
        if player_info is None:
            return []

        player_team = player_info.team if game.start.is_teams else None

        opponent_ports: list[int] = []
        for port_idx, player in enumerate(game.start.players):
            if player is None:
                continue
            if port_idx == player_port:
                continue
            if player_team is not None:
                if player.team != player_team:
                    opponent_ports.append(port_idx)
            else:
                opponent_ports.append(port_idx)

        return opponent_ports

    def get_opponent_character(
        self, replay_path: Path, opponent_port: int
    ) -> str:
        """Get the character name for an opponent port."""
        game = Game(replay_path)
        if game.start is None:
            return "unknown"
        player = game.start.players[opponent_port]
        if player is None:
            return "unknown"
        return get_character_name(player.character)

    def scan_replay(
        self,
        replay_path: Path,
        player_port: int,
        registry: DetectorRegistry,
    ) -> list[TaggedMoment]:
        """Scan a replay for moments using all registered detectors.

        Parses the replay, runs all detectors, and enriches moments with metadata.

        Args:
            replay_path: Path to the .slp file
            player_port: Port index of the player (0-3)
            registry: DetectorRegistry with detectors to run

        Returns:
            List of detected moments with metadata filled in
        """
        # Get base metadata
        metadata = self.get_metadata(replay_path)

        # Parse replay to frames for each opponent
        frames_by_opponent = parse_replay_to_frames(replay_path, player_port)

        all_moments: list[TaggedMoment] = []

        # Run detectors for each opponent
        for opponent_port, frames in frames_by_opponent.items():
            opponent_char = self.get_opponent_character(replay_path, opponent_port)

            # Run all detectors
            moments = registry.run_all(frames, replay_path)

            # Enrich moments with metadata
            for moment in moments:
                moment.metadata.update(metadata)
                moment.metadata["opponent"] = opponent_char

            all_moments.extend(moments)

        return all_moments
```

**Step 6: Run all tests to verify they pass**

Run: `pytest tests/test_scanner.py tests/test_detector_registry.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/scanner.py src/detectors/registry.py tests/test_scanner.py tests/test_detector_registry.py
git commit -m "feat: add detector registry and ReplayScanner for running detectors"
```

---

## Task 14: Find Command - Query Implementation

> **✅ IMPLEMENTED** - This task has been completed. See `src/cli.py` (find command) and `tests/test_cli.py`.

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/cli.py`

**Step 1: Write failing tests for find command**

Add to `tests/test_cli.py`:

```python
from src.database import MomentDatabase
from src.models import TaggedMoment


def test_find_queries_database_by_tag(tmp_path: Path) -> None:
    """Find command queries database and displays results."""
    db_path = tmp_path / "test.db"

    # Set up database with test moments
    db = MomentDatabase(db_path)
    db.initialize()

    moment1 = TaggedMoment(
        replay_path=Path("/replays/game1.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic"],
        metadata={"opponent": "fox", "stage": "battlefield"},
    )
    moment2 = TaggedMoment(
        replay_path=Path("/replays/game2.slp"),
        frame_start=2000,
        frame_end=2500,
        tags=["ledgehog:strict"],
        metadata={"opponent": "marth", "stage": "fd"},
    )

    db.store_moment(moment1, mtime=1000.0)
    db.store_moment(moment2, mtime=1000.0)

    runner = CliRunner()
    result = runner.invoke(main, [
        "find",
        "--tag", "ledgehog:basic",
        "--db", str(db_path),
    ])

    assert result.exit_code == 0
    # Should show the found moment info
    assert "game1.slp" in result.output
    assert "fox" in result.output or "1000" in result.output


def test_find_displays_count(tmp_path: Path) -> None:
    """Find command shows count of matching moments."""
    db_path = tmp_path / "test.db"

    db = MomentDatabase(db_path)
    db.initialize()

    # Store 3 moments with same tag
    for i in range(3):
        moment = TaggedMoment(
            replay_path=Path(f"/replays/game{i}.slp"),
            frame_start=1000 + i * 100,
            frame_end=1500 + i * 100,
            tags=["ledgehog:basic"],
            metadata={},
        )
        db.store_moment(moment, mtime=1000.0)

    runner = CliRunner()
    result = runner.invoke(main, [
        "find",
        "--tag", "ledgehog:basic",
        "--db", str(db_path),
    ])

    assert result.exit_code == 0
    # Should indicate 3 moments found
    assert "3" in result.output
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_find_queries_database_by_tag -v`
Expected: FAIL - find command doesn't query database

**Step 3: Update find command implementation**

Update the `find` function in `src/cli.py`:

```python
@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("--opponent", help="Filter by opponent character")
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def find(tag: tuple[str, ...], opponent: str | None, db: Path) -> None:
    """Find moments matching criteria."""
    database = MomentDatabase(db)

    # Find moments by tag
    all_moments: list[TaggedMoment] = []
    if tag:
        for t in tag:
            moments = database.find_moments_by_tag(t)
            all_moments.extend(moments)
    else:
        click.echo("No tag specified. Use --tag to filter moments.")
        return

    # Filter by opponent if specified
    if opponent:
        all_moments = [
            m for m in all_moments
            if m.metadata.get("opponent", "").lower() == opponent.lower()
        ]

    click.echo(f"Found {len(all_moments)} moments")

    # Display results
    for moment in all_moments:
        replay_name = moment.replay_path.name
        opp = moment.metadata.get("opponent", "unknown")
        stage = moment.metadata.get("stage", "unknown")
        tags_str = ", ".join(moment.tags)
        click.echo(
            f"  {replay_name}: frames {moment.frame_start}-{moment.frame_end} "
            f"vs {opp} on {stage} [{tags_str}]"
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: add detector registry and implement find command"
```

---

## Task 15: Dolphin Automation

**Files:**
- Create: `tests/test_dolphin.py`
- Create: `src/capture/dolphin.py`

**Step 1: Write failing tests for Dolphin configuration**

```python
"""Tests for Dolphin automation."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.capture.dolphin import (
    DolphinConfig,
    DolphinController,
    build_dolphin_command,
)


def test_dolphin_config_defaults() -> None:
    """DolphinConfig has sensible defaults."""
    config = DolphinConfig()

    assert config.executable == Path("/usr/bin/dolphin-emu")
    assert config.user_dir is not None
    assert config.iso_path is None


def test_dolphin_config_custom_paths() -> None:
    """DolphinConfig accepts custom paths."""
    config = DolphinConfig(
        executable=Path("/custom/dolphin"),
        user_dir=Path("/custom/user"),
        iso_path=Path("/path/to/melee.iso"),
    )

    assert config.executable == Path("/custom/dolphin")
    assert config.iso_path == Path("/path/to/melee.iso")


def test_build_dolphin_command() -> None:
    """Build correct Dolphin launch command."""
    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=Path("/home/user/.dolphin-slippi"),
        iso_path=Path("/games/melee.iso"),
    )

    cmd = build_dolphin_command(
        config=config,
        replay_path=Path("/replays/game.slp"),
        start_frame=1000,
        end_frame=2000,
        output_dir=Path("/tmp/frames"),
    )

    assert "/usr/bin/dolphin-emu" in cmd[0]
    assert "-e" in cmd  # Execute/play mode
    assert "-u" in cmd  # User directory


def test_dolphin_controller_setup_dump_config(tmp_path: Path) -> None:
    """DolphinController sets up frame dump configuration."""
    user_dir = tmp_path / "dolphin"
    user_dir.mkdir()

    config = DolphinConfig(
        executable=Path("/usr/bin/dolphin-emu"),
        user_dir=user_dir,
    )

    controller = DolphinController(config)
    controller.setup_frame_dump(
        output_dir=tmp_path / "frames",
        start_frame=100,
        end_frame=500,
    )

    # Check that config file was created/modified
    gfx_ini = user_dir / "Config" / "GFX.ini"
    assert gfx_ini.exists()

    content = gfx_ini.read_text()
    assert "DumpFrames = True" in content or "DumpFrames=True" in content
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dolphin.py -v`
Expected: FAIL with "cannot import name 'DolphinConfig'"

**Step 3: Write implementation**

```python
"""Dolphin emulator automation for frame dumping."""

import configparser
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DolphinConfig:
    """Configuration for Dolphin emulator."""

    executable: Path = field(default_factory=lambda: Path("/usr/bin/dolphin-emu"))
    user_dir: Path | None = field(
        default_factory=lambda: Path.home() / ".dolphin-slippi"
    )
    iso_path: Path | None = None


def build_dolphin_command(
    config: DolphinConfig,
    replay_path: Path,
    start_frame: int,
    end_frame: int,
    output_dir: Path,
) -> list[str]:
    """Build command to launch Dolphin for frame dumping.

    Args:
        config: Dolphin configuration
        replay_path: Path to .slp replay file
        start_frame: Frame to start recording
        end_frame: Frame to stop recording
        output_dir: Directory for frame dump output

    Returns:
        Command as list of strings
    """
    cmd = [str(config.executable)]

    if config.user_dir:
        cmd.extend(["-u", str(config.user_dir)])

    if config.iso_path:
        cmd.extend(["-e", str(config.iso_path)])

    # Slippi-specific replay playback arguments
    cmd.extend([
        "-i", str(replay_path),  # Input replay
        "--output-directory", str(output_dir),
        "--start-frame", str(start_frame),
        "--end-frame", str(end_frame),
    ])

    return cmd


class DolphinController:
    """Controller for Dolphin emulator frame dumping."""

    def __init__(self, config: DolphinConfig) -> None:
        self.config = config
        self._process: subprocess.Popen[bytes] | None = None

    def setup_frame_dump(
        self,
        output_dir: Path,
        start_frame: int,
        end_frame: int,
    ) -> None:
        """Configure Dolphin for frame dumping.

        Modifies GFX.ini to enable frame dumping.
        """
        if self.config.user_dir is None:
            raise ValueError("user_dir must be set to configure frame dump")

        config_dir = self.config.user_dir / "Config"
        config_dir.mkdir(parents=True, exist_ok=True)

        gfx_ini_path = config_dir / "GFX.ini"

        # Parse existing config or create new
        gfx_config = configparser.ConfigParser()
        if gfx_ini_path.exists():
            gfx_config.read(gfx_ini_path)

        # Ensure Settings section exists
        if "Settings" not in gfx_config:
            gfx_config["Settings"] = {}

        # Enable frame dumping
        gfx_config["Settings"]["DumpFrames"] = "True"
        gfx_config["Settings"]["DumpFramesAsImages"] = "True"
        gfx_config["Settings"]["DumpPath"] = str(output_dir)

        # Write config
        with open(gfx_ini_path, "w") as f:
            gfx_config.write(f)

    def start_capture(
        self,
        replay_path: Path,
        start_frame: int,
        end_frame: int,
        output_dir: Path,
    ) -> None:
        """Start Dolphin for frame capture.

        Args:
            replay_path: Path to replay file
            start_frame: Frame to start capturing
            end_frame: Frame to stop capturing
            output_dir: Directory for output frames
        """
        self.setup_frame_dump(output_dir, start_frame, end_frame)

        cmd = build_dolphin_command(
            config=self.config,
            replay_path=replay_path,
            start_frame=start_frame,
            end_frame=end_frame,
            output_dir=output_dir,
        )

        self._process = subprocess.Popen(cmd)

    def wait_for_completion(self, timeout: float | None = None) -> int:
        """Wait for Dolphin to finish capturing.

        Returns:
            Return code from Dolphin process
        """
        if self._process is None:
            raise RuntimeError("No capture in progress")

        return self._process.wait(timeout=timeout)

    def stop(self) -> None:
        """Stop Dolphin capture."""
        if self._process is not None:
            self._process.terminate()
            self._process.wait(timeout=10)
            self._process = None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dolphin.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/capture/dolphin.py tests/test_dolphin.py
git commit -m "feat: add Dolphin controller for frame dumping"
```

---

## Task 16: Capture Command - Full Pipeline

**Files:**
- Create: `tests/test_capture_pipeline.py`
- Create: `src/capture/pipeline.py`
- Modify: `src/cli.py`

**Step 1: Write failing tests for capture pipeline**

```python
"""Tests for capture pipeline."""

from pathlib import Path
from unittest.mock import patch, MagicMock, call

from src.capture.pipeline import CapturePipeline
from src.models import TaggedMoment


def test_pipeline_captures_single_moment(tmp_path: Path) -> None:
    """Pipeline captures a single moment through Dolphin and FFmpeg."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=2000,
        tags=["ledgehog:basic"],
        metadata={"date": "2025-01-15", "opponent": "fox", "stage": "battlefield"},
    )

    output_dir = tmp_path / "clips"

    with patch("src.capture.pipeline.DolphinController") as mock_dolphin, \
         patch("src.capture.pipeline.FFmpegEncoder") as mock_ffmpeg:

        # Setup mocks
        mock_dolphin_instance = MagicMock()
        mock_dolphin.return_value = mock_dolphin_instance
        mock_dolphin_instance.wait_for_completion.return_value = 0

        mock_ffmpeg_instance = MagicMock()
        mock_ffmpeg.return_value = mock_ffmpeg_instance

        pipeline = CapturePipeline(output_dir=output_dir)
        result = pipeline.capture_moment(moment, index=1)

        # Verify Dolphin was called with correct frames
        mock_dolphin_instance.start_capture.assert_called_once()
        call_kwargs = mock_dolphin_instance.start_capture.call_args
        assert call_kwargs.kwargs["start_frame"] == 1000
        assert call_kwargs.kwargs["end_frame"] == 2000

        # Verify FFmpeg was called
        mock_ffmpeg_instance.encode.assert_called_once()

        # Should return output path
        assert result is not None
        assert result.suffix == ".mp4"


def test_pipeline_captures_multiple_moments(tmp_path: Path) -> None:
    """Pipeline captures multiple moments in sequence."""
    moments = [
        TaggedMoment(
            replay_path=Path(f"/replays/game{i}.slp"),
            frame_start=1000 + i * 1000,
            frame_end=2000 + i * 1000,
            tags=["ledgehog:basic"],
            metadata={},
        )
        for i in range(3)
    ]

    output_dir = tmp_path / "clips"

    with patch("src.capture.pipeline.DolphinController") as mock_dolphin, \
         patch("src.capture.pipeline.FFmpegEncoder") as mock_ffmpeg:

        mock_dolphin_instance = MagicMock()
        mock_dolphin.return_value = mock_dolphin_instance
        mock_dolphin_instance.wait_for_completion.return_value = 0

        mock_ffmpeg_instance = MagicMock()
        mock_ffmpeg.return_value = mock_ffmpeg_instance

        pipeline = CapturePipeline(output_dir=output_dir)
        results = pipeline.capture_moments(moments)

        # All 3 should be captured
        assert len(results) == 3
        assert mock_dolphin_instance.start_capture.call_count == 3
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_capture_pipeline.py -v`
Expected: FAIL with "cannot import name 'CapturePipeline'"

**Step 3: Write pipeline implementation**

```python
"""Capture pipeline for recording moments as video clips."""

import shutil
import tempfile
from pathlib import Path

from src.capture.dolphin import DolphinConfig, DolphinController
from src.capture.ffmpeg import FFmpegEncoder
from src.models import TaggedMoment, generate_clip_filename


class CapturePipeline:
    """Pipeline for capturing moments as video clips."""

    def __init__(
        self,
        output_dir: Path,
        dolphin_config: DolphinConfig | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.dolphin_config = dolphin_config or DolphinConfig()
        self._dolphin = DolphinController(self.dolphin_config)
        self._ffmpeg = FFmpegEncoder()

    def capture_moment(
        self,
        moment: TaggedMoment,
        index: int,
    ) -> Path | None:
        """Capture a single moment as a video clip.

        Args:
            moment: The moment to capture
            index: Index for filename generation

        Returns:
            Path to the generated video clip, or None if capture failed
        """
        # Create temp directory for frames
        with tempfile.TemporaryDirectory() as temp_dir:
            frame_dir = Path(temp_dir) / "frames"
            frame_dir.mkdir()

            # Start Dolphin capture
            self._dolphin.start_capture(
                replay_path=moment.replay_path,
                start_frame=moment.frame_start,
                end_frame=moment.frame_end,
                output_dir=frame_dir,
            )

            # Wait for capture to complete
            return_code = self._dolphin.wait_for_completion()
            if return_code != 0:
                return None

            # Generate output filename
            filename = generate_clip_filename(moment, index)
            output_path = self.output_dir / filename

            # Encode frames to video
            self._ffmpeg.encode(
                frame_dir=frame_dir,
                output_file=output_path,
                fps=60,
            )

            return output_path

    def capture_moments(
        self,
        moments: list[TaggedMoment],
    ) -> list[Path]:
        """Capture multiple moments as video clips.

        Args:
            moments: List of moments to capture

        Returns:
            List of paths to generated video clips
        """
        results: list[Path] = []

        for i, moment in enumerate(moments, start=1):
            result = self.capture_moment(moment, index=i)
            if result is not None:
                results.append(result)

        return results
```

**Step 4: Update capture CLI command**

Update `src/cli.py`:

```python
from src.capture.pipeline import CapturePipeline


@main.command()
@click.option("--tag", multiple=True, help="Filter by tag")
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
@click.option(
    "--db",
    type=click.Path(exists=True, path_type=Path),
    default=Path("~/.config/slippi-clip/moments.db").expanduser(),
    help="Database path",
)
def capture(tag: tuple[str, ...], output: Path, db: Path) -> None:
    """Capture video clips for matching moments."""
    database = MomentDatabase(db)

    # Find moments by tag
    all_moments: list[TaggedMoment] = []
    for t in tag:
        moments = database.find_moments_by_tag(t)
        all_moments.extend(moments)

    if not all_moments:
        click.echo("No moments found matching the specified tags.")
        return

    click.echo(f"Capturing {len(all_moments)} clips to {output}")

    pipeline = CapturePipeline(output_dir=output)
    results = pipeline.capture_moments(all_moments)

    click.echo(f"Captured {len(results)} clips")
    for path in results:
        click.echo(f"  {path}")
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_capture_pipeline.py tests/test_cli.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/capture/pipeline.py src/cli.py tests/test_capture_pipeline.py
git commit -m "feat: add capture pipeline for recording moments as video clips"
```

---

## Task 17: Compile Command

**Files:**
- Create: `tests/test_compile.py`
- Create: `src/capture/compile.py`
- Modify: `src/cli.py`

**Step 1: Write failing tests for clip compilation**

```python
"""Tests for clip compilation."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.capture.compile import build_concat_command, compile_clips


def test_build_concat_command() -> None:
    """Build correct ffmpeg concat command."""
    clips = [
        Path("/clips/clip1.mp4"),
        Path("/clips/clip2.mp4"),
        Path("/clips/clip3.mp4"),
    ]
    output = Path("/output/final.mp4")

    cmd = build_concat_command(clips, output)

    assert "ffmpeg" in cmd[0]
    assert "-f" in cmd
    assert "concat" in cmd
    # Output file should be in command
    assert str(output) in cmd


def test_build_concat_command_creates_list_file(tmp_path: Path) -> None:
    """Concat command creates a list file for ffmpeg."""
    clips = [
        tmp_path / "clip1.mp4",
        tmp_path / "clip2.mp4",
    ]
    # Create dummy files
    for clip in clips:
        clip.touch()

    output = tmp_path / "final.mp4"

    cmd = build_concat_command(clips, output, list_file=tmp_path / "list.txt")

    list_file = tmp_path / "list.txt"
    assert list_file.exists()

    content = list_file.read_text()
    assert "clip1.mp4" in content
    assert "clip2.mp4" in content


def test_compile_clips_calls_ffmpeg(tmp_path: Path) -> None:
    """compile_clips calls ffmpeg with concat command."""
    clips = [
        tmp_path / "clip1.mp4",
        tmp_path / "clip2.mp4",
    ]
    for clip in clips:
        clip.touch()

    output = tmp_path / "final.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        compile_clips(clips, output)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args[0]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_compile.py -v`
Expected: FAIL with "cannot import name 'build_concat_command'"

**Step 3: Write implementation**

```python
"""Clip compilation using FFmpeg."""

import subprocess
import tempfile
from pathlib import Path


def build_concat_command(
    clips: list[Path],
    output: Path,
    list_file: Path | None = None,
) -> list[str]:
    """Build ffmpeg command to concatenate clips.

    Args:
        clips: List of clip paths to concatenate
        output: Output file path
        list_file: Optional path for the concat list file

    Returns:
        Command as list of strings
    """
    # Create list file for ffmpeg concat
    if list_file is None:
        list_file = Path(tempfile.mktemp(suffix=".txt"))

    with open(list_file, "w") as f:
        for clip in clips:
            # FFmpeg concat format requires 'file' prefix
            f.write(f"file '{clip.absolute()}'\n")

    return [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output),
    ]


def compile_clips(
    clips: list[Path],
    output: Path,
) -> None:
    """Compile multiple clips into a single video.

    Args:
        clips: List of clip paths to concatenate
        output: Output file path

    Raises:
        RuntimeError: If ffmpeg fails
    """
    if not clips:
        raise ValueError("No clips to compile")

    # Create temp list file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for clip in clips:
            f.write(f"file '{clip.absolute()}'\n")
        list_file = Path(f.name)

    try:
        cmd = build_concat_command(clips, output, list_file=list_file)
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    finally:
        list_file.unlink(missing_ok=True)
```

**Step 4: Update compile CLI command**

Update `src/cli.py`:

```python
from src.capture.compile import compile_clips as compile_clips_fn


@main.command("compile")
@click.argument("clips_dir", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
def compile_clips(clips_dir: Path, output: Path) -> None:
    """Compile clips into a single video."""
    # Find all mp4 files in directory
    clips = sorted(clips_dir.glob("*.mp4"))

    if not clips:
        click.echo(f"No .mp4 files found in {clips_dir}")
        return

    click.echo(f"Compiling {len(clips)} clips to {output}")

    compile_clips_fn(clips, output)

    click.echo(f"Compilation complete: {output}")
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_compile.py tests/test_cli.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/capture/compile.py src/cli.py tests/test_compile.py
git commit -m "feat: add clip compilation command"
```

---

## Task 18: Configuration File Support

**Files:**
- Create: `tests/test_config.py`
- Create: `src/config.py`
- Modify: `src/cli.py`

**Step 1: Write failing tests for configuration loading**

```python
"""Tests for configuration file support."""

from pathlib import Path

from src.config import Config, load_config


def test_config_defaults() -> None:
    """Config has sensible defaults when no file exists."""
    config = Config()

    assert config.db_path == Path("~/.config/slippi-clip/moments.db").expanduser()
    assert config.player_port == 0


def test_load_config_from_file(tmp_path: Path) -> None:
    """Load configuration from TOML file."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[general]
player_port = 2

[database]
path = "/custom/path/moments.db"

[dolphin]
executable = "/opt/dolphin/dolphin-emu"
iso_path = "/games/melee.iso"
""")

    config = load_config(config_path)

    assert config.player_port == 2
    assert config.db_path == Path("/custom/path/moments.db")
    assert config.dolphin_executable == Path("/opt/dolphin/dolphin-emu")
    assert config.iso_path == Path("/games/melee.iso")


def test_load_config_missing_file() -> None:
    """load_config returns defaults when file doesn't exist."""
    config = load_config(Path("/nonexistent/config.toml"))

    # Should return default config
    assert config.player_port == 0
    assert config.db_path == Path("~/.config/slippi-clip/moments.db").expanduser()


def test_config_partial_override(tmp_path: Path) -> None:
    """Config file can override only some values."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[general]
player_port = 3
""")

    config = load_config(config_path)

    # Overridden value
    assert config.player_port == 3
    # Default values
    assert config.db_path == Path("~/.config/slippi-clip/moments.db").expanduser()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "cannot import name 'Config'"

**Step 3: Write implementation**

```python
"""Configuration file support for slippi-clip."""

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]


@dataclass
class Config:
    """Application configuration."""

    # General
    player_port: int = 0

    # Database
    db_path: Path = field(
        default_factory=lambda: Path("~/.config/slippi-clip/moments.db").expanduser()
    )

    # Dolphin
    dolphin_executable: Path = field(
        default_factory=lambda: Path("/usr/bin/dolphin-emu")
    )
    dolphin_user_dir: Path | None = field(
        default_factory=lambda: Path.home() / ".dolphin-slippi"
    )
    iso_path: Path | None = None

    # FFmpeg
    ffmpeg_crf: int = 18
    ffmpeg_preset: str = "medium"


def load_config(config_path: Path) -> Config:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config.toml file

    Returns:
        Config object with values from file (or defaults if file missing)
    """
    config = Config()

    if not config_path.exists():
        return config

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # General section
    general = data.get("general", {})
    if "player_port" in general:
        config.player_port = general["player_port"]

    # Database section
    database = data.get("database", {})
    if "path" in database:
        config.db_path = Path(database["path"])

    # Dolphin section
    dolphin = data.get("dolphin", {})
    if "executable" in dolphin:
        config.dolphin_executable = Path(dolphin["executable"])
    if "user_dir" in dolphin:
        config.dolphin_user_dir = Path(dolphin["user_dir"])
    if "iso_path" in dolphin:
        config.iso_path = Path(dolphin["iso_path"])

    # FFmpeg section
    ffmpeg = data.get("ffmpeg", {})
    if "crf" in ffmpeg:
        config.ffmpeg_crf = ffmpeg["crf"]
    if "preset" in ffmpeg:
        config.ffmpeg_preset = ffmpeg["preset"]

    return config


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    return Path("~/.config/slippi-clip/config.toml").expanduser()
```

**Step 4: Update CLI to use configuration**

Update `src/cli.py` to load config at startup:

```python
from src.config import load_config, get_default_config_path


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file",
)
@click.pass_context
def main(ctx: click.Context, config: Path | None) -> None:
    """Slippi-clip: Scan replays for moments and capture video clips."""
    ctx.ensure_object(dict)

    config_path = config or get_default_config_path()
    ctx.obj["config"] = load_config(config_path)


@main.command()
@click.argument("replay_dir", type=click.Path(exists=True, path_type=Path))
@click.option("--full-rescan", is_flag=True, help="Re-scan all files, ignoring cache")
@click.option("--db", type=click.Path(path_type=Path), default=None, help="Database path")
@click.option("--player-port", type=int, default=None, help="Player port (0-3)")
@click.pass_context
def scan(
    ctx: click.Context,
    replay_dir: Path,
    full_rescan: bool,
    db: Path | None,
    player_port: int | None,
) -> None:
    """Scan replay directory for moments."""
    config = ctx.obj["config"]

    # Use CLI args or fall back to config
    db_path = db or config.db_path
    port = player_port if player_port is not None else config.player_port

    # ... rest of scan implementation
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py tests/test_cli.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/config.py src/cli.py tests/test_config.py
git commit -m "feat: add configuration file support"
```

---

## Execution Notes

- **TDD Required:** Use `superpowers:test-driven-development` for each task
- **Before any edit:** Run `touch /tmp/.superpowers-tdd-session-$(date +%Y%m%d)` to enable the TDD guard
- **Commit frequently:** Each task ends with a commit
- **Type checking:** Run `pyright src/` periodically to catch type errors

---

Plan saved to: `docs/plans/2026-01-31-implementation-plan.md`
