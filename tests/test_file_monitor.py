"""Tests for file monitoring utilities."""

import tempfile
import threading
import time
from pathlib import Path

from src.capture.file_monitor import wait_for_file_stable


def test_wait_for_file_stable_detects_completion(tmp_path: Path) -> None:
    """wait_for_file_stable should return when file stops growing."""
    test_file = tmp_path / "test.avi"
    test_file.touch()

    def write_data() -> None:
        """Simulate Dolphin writing frame data."""
        for i in range(5):
            time.sleep(0.1)
            with open(test_file, "ab") as f:
                f.write(b"x" * 1000)

    writer = threading.Thread(target=write_data)
    writer.start()

    # Wait for file to stabilize (should happen after ~0.5 sec of writing)
    result = wait_for_file_stable(
        test_file,
        stable_seconds=0.3,
        timeout=5.0,
        check_interval=0.1,
    )

    writer.join()

    assert result is True
    assert test_file.stat().st_size == 5000


def test_wait_for_file_stable_timeout_on_continuous_write(tmp_path: Path) -> None:
    """wait_for_file_stable should timeout if file keeps growing."""
    test_file = tmp_path / "test.avi"
    test_file.touch()
    stop_writing = threading.Event()

    def write_data() -> None:
        """Write continuously until told to stop."""
        while not stop_writing.is_set():
            time.sleep(0.05)
            with open(test_file, "ab") as f:
                f.write(b"x" * 100)

    writer = threading.Thread(target=write_data)
    writer.start()

    try:
        # Short timeout - file keeps growing so should timeout
        result = wait_for_file_stable(
            test_file,
            stable_seconds=0.5,
            timeout=0.3,  # Timeout before stable_seconds is reached
            check_interval=0.05,
        )

        assert result is False  # Should timeout
    finally:
        stop_writing.set()
        writer.join()


def test_wait_for_file_stable_immediate_if_no_activity(tmp_path: Path) -> None:
    """wait_for_file_stable returns True immediately for stable files."""
    test_file = tmp_path / "test.avi"
    test_file.write_bytes(b"x" * 1000)  # File already exists and is stable

    result = wait_for_file_stable(
        test_file,
        stable_seconds=0.1,
        timeout=1.0,
        check_interval=0.05,
    )

    assert result is True
