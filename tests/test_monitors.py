"""Tests for multi-monitor support."""

from unittest.mock import MagicMock, patch

from src.capture.monitors import Monitor, get_least_active_monitor, get_monitors


def test_get_monitors_parses_xrandr_output() -> None:
    """get_monitors parses xrandr output to extract monitor info."""
    xrandr_output = """Screen 0: minimum 8 x 8, current 3840 x 1080, maximum 32767 x 32767
DP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+
HDMI-1 connected 1920x1080+1920+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=xrandr_output)

        monitors = get_monitors()

        assert len(monitors) == 2
        assert monitors[0].name == "DP-1"
        assert monitors[0].x == 0
        assert monitors[0].y == 0
        assert monitors[0].width == 1920
        assert monitors[0].height == 1080
        assert monitors[0].is_primary

        assert monitors[1].name == "HDMI-1"
        assert monitors[1].x == 1920
        assert not monitors[1].is_primary


def test_get_least_active_monitor_returns_non_focused() -> None:
    """get_least_active_monitor returns monitor without the focused window."""
    monitors = [
        Monitor("DP-1", 0, 0, 1920, 1080, True),
        Monitor("HDMI-1", 1920, 0, 1920, 1080, False),
    ]

    # Active window is on DP-1 (x=500)
    with patch("subprocess.run") as mock_run:
        def run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            if "getactivewindow" in cmd:
                return MagicMock(returncode=0, stdout="12345")
            elif "getwindowgeometry" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout="Window 12345\n  Position: 500,200 (screen: 0)\n  Geometry: 800x600",
                )
            return MagicMock(returncode=1)

        mock_run.side_effect = run_side_effect

        result = get_least_active_monitor(monitors)

        # Should return HDMI-1 since active window is on DP-1
        assert result.name == "HDMI-1"


def test_get_least_active_monitor_single_monitor() -> None:
    """get_least_active_monitor returns the only monitor if just one exists."""
    monitors = [Monitor("DP-1", 0, 0, 1920, 1080, True)]

    result = get_least_active_monitor(monitors)

    assert result.name == "DP-1"


def test_get_monitors_returns_empty_on_xrandr_failure() -> None:
    """get_monitors returns empty list if xrandr fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        monitors = get_monitors()

        assert monitors == []


def test_get_least_active_monitor_fallback_to_non_primary() -> None:
    """If can't determine active window, prefer non-primary monitor."""
    monitors = [
        Monitor("DP-1", 0, 0, 1920, 1080, True),
        Monitor("HDMI-1", 1920, 0, 1920, 1080, False),
    ]

    with patch("subprocess.run") as mock_run:
        # xdotool fails
        mock_run.return_value = MagicMock(returncode=1)

        result = get_least_active_monitor(monitors)

        # Should return HDMI-1 (non-primary)
        assert result.name == "HDMI-1"
