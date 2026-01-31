# Slippi Replay Clipper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool that scans Slippi replays for ledgehog moments and captures them as video clips.

**Architecture:** Three-phase pipeline: (1) Scan replays with py-slippi, run detectors, store moments in SQLite; (2) Query moments by tags; (3) Capture clips via Dolphin frame dump + ffmpeg.

**Tech Stack:** Python 3.10+, py-slippi, Click, SQLite, pytest, pyright

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
            "opponent": "fox",
            "stage": "battlefield",
        },
    )

    filename = generate_clip_filename(moment, index=1)
    assert filename == "2025-01-15_vs-fox_battlefield_ledgehog-strict_001.mp4"


def test_generate_clip_filename_multiple_tags() -> None:
    """Use most specific ledgehog tag in filename."""
    moment = TaggedMoment(
        replay_path=Path("/replays/game.slp"),
        frame_start=1000,
        frame_end=1500,
        tags=["ledgehog:basic", "ledgehog:strict", "ledgehog:intentional"],
        metadata={
            "date": "2025-01-15",
            "opponent": "marth",
            "stage": "yoshis",
        },
    )

    filename = generate_clip_filename(moment, index=5)
    # Should use intentional (most specific)
    assert filename == "2025-01-15_vs-marth_yoshis_ledgehog-intentional_005.mp4"


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
    assert filename == "unknown_vs-unknown_unknown_ledgehog-basic_001.mp4"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_filename.py -v`
Expected: FAIL with "cannot import name 'generate_clip_filename'"

**Step 3: Add implementation to models.py**

Add to `src/models.py`:

```python
def generate_clip_filename(moment: TaggedMoment, index: int) -> str:
    """Generate a descriptive filename for a clip.

    Format: {date}_vs-{opponent}_{stage}_{primary_tag}_{index:03d}.mp4
    """
    # Get metadata with defaults
    date_str = moment.metadata.get("date", "unknown")
    opponent = moment.metadata.get("opponent", "unknown")
    stage = moment.metadata.get("stage", "unknown")

    # Find the most specific ledgehog tag
    tag_priority = ["ledgehog:intentional", "ledgehog:strict", "ledgehog:basic"]
    primary_tag = "unknown"
    for tag in tag_priority:
        if tag in moment.tags:
            primary_tag = tag.replace(":", "-")
            break

    return f"{date_str}_vs-{opponent}_{stage}_{primary_tag}_{index:03d}.mp4"
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

## Remaining Tasks (Summary)

The following tasks follow the same pattern. Each implements one piece:

### Task 12: Scanner - Parse Replays with py-slippi
- Create `src/scanner.py`
- Parse .slp files to FrameData
- Requires py-slippi library

### Task 13: Scanner - Run Detectors
- Integrate detector registry
- Run all detectors on parsed frames
- Store moments in database

### Task 14: Find Command - Query Implementation
- Wire up `find` command to query database
- Display results to user

### Task 15: Dolphin Automation
- Create `src/capture/dolphin.py`
- Configure and launch Dolphin for frame dumping
- Handle start/stop at specific frames

### Task 16: Capture Command - Full Pipeline
- Wire up `capture` command
- Dolphin frame dump → FFmpeg encode → organized output

### Task 17: Compile Command
- Concatenate multiple clips with FFmpeg
- Consistent formatting

### Task 18: Configuration File Support
- Parse `~/.config/slippi-clip/config.toml`
- Apply defaults from config

---

## Execution Notes

- **TDD Required:** Use `superpowers:test-driven-development` for each task
- **Before any edit:** Run `touch /tmp/.superpowers-tdd-session-$(date +%Y%m%d)` to enable the TDD guard
- **Commit frequently:** Each task ends with a commit
- **Type checking:** Run `pyright src/` periodically to catch type errors

---

Plan saved to: `docs/plans/2026-01-31-implementation-plan.md`
