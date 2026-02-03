"""File monitoring utilities for capture pipeline."""

import time
from pathlib import Path


def wait_for_file_stable(
    file_path: Path,
    stable_seconds: float = 2.0,
    timeout: float = 300.0,
    check_interval: float = 0.5,
) -> bool:
    """Wait for a file to stop growing (become stable).

    Uses polling with configurable interval. For systems with inotify,
    consider using watchdog library for better performance.

    Args:
        file_path: Path to monitor
        stable_seconds: How long file must be unchanged to consider complete
        timeout: Maximum time to wait
        check_interval: How often to check file size

    Returns:
        True if file stabilized, False if timeout occurred
    """
    start_time = time.time()
    last_size = -1
    stable_since: float | None = None

    while time.time() - start_time < timeout:
        if not file_path.exists():
            time.sleep(check_interval)
            continue

        current_size = file_path.stat().st_size

        if current_size == last_size:
            # File hasn't changed
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= stable_seconds:
                return True
        else:
            # File changed, reset stability timer
            stable_since = None
            last_size = current_size

        time.sleep(check_interval)

    return False
