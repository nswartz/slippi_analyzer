"""Multi-monitor support for Dolphin window placement."""

import re
import subprocess
from dataclasses import dataclass


@dataclass
class Monitor:
    """Represents a display monitor."""

    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = False


def get_monitors() -> list[Monitor]:
    """Get list of connected monitors using xrandr.

    Returns:
        List of Monitor objects, empty if xrandr fails
    """
    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        monitors: list[Monitor] = []
        # Pattern: "NAME connected [primary] WIDTHxHEIGHT+X+Y"
        pattern = r"(\S+) connected\s*(primary)?\s*(\d+)x(\d+)\+(\d+)\+(\d+)"

        for match in re.finditer(pattern, result.stdout):
            name = match.group(1)
            is_primary = match.group(2) == "primary"
            width = int(match.group(3))
            height = int(match.group(4))
            x = int(match.group(5))
            y = int(match.group(6))

            monitors.append(
                Monitor(
                    name=name,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    is_primary=is_primary,
                )
            )

        return monitors
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_window_position(window_id: str) -> tuple[int, int] | None:
    """Get the position of a window using xdotool.

    Returns:
        (x, y) tuple or None if failed
    """
    try:
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", window_id],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        # Parse "Position: X,Y (screen: N)"
        match = re.search(r"Position:\s*(\d+),(\d+)", result.stdout)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_monitor_for_position(monitors: list[Monitor], x: int, y: int) -> Monitor | None:
    """Find which monitor contains the given position."""
    for monitor in monitors:
        if (
            monitor.x <= x < monitor.x + monitor.width
            and monitor.y <= y < monitor.y + monitor.height
        ):
            return monitor
    return None


def get_least_active_monitor(monitors: list[Monitor]) -> Monitor:
    """Get the monitor that is least likely to have user focus.

    Logic:
    1. Get currently focused window position
    2. Return a monitor that does NOT contain the focused window
    3. If only one monitor or can't determine, return non-primary or first

    Args:
        monitors: List of available monitors

    Returns:
        The least-active monitor (never None, falls back to first)
    """
    if len(monitors) <= 1:
        return monitors[0] if monitors else Monitor("default", 0, 0, 1920, 1080, True)

    # Get active window position
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            window_id = result.stdout.strip()
            pos = get_window_position(window_id)
            if pos:
                active_monitor = get_monitor_for_position(monitors, pos[0], pos[1])
                if active_monitor:
                    # Return any monitor that is NOT the active one
                    for monitor in monitors:
                        if monitor.name != active_monitor.name:
                            return monitor
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: prefer non-primary monitor
    for monitor in monitors:
        if not monitor.is_primary:
            return monitor

    return monitors[0]
