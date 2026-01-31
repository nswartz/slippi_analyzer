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
