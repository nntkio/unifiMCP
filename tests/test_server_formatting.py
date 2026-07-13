"""Tests for formatting helpers shared across tool domains."""

from unifi_mcp.server import format_bytes, format_uptime


class TestFormatBytes:
    """Tests for format_bytes."""

    def test_format_bytes_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_bytes(500) == "500.0 B"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_bytes(1536) == "1.5 KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_bytes(1572864) == "1.5 MB"

    def test_format_bytes_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_bytes(1610612736) == "1.5 GB"


class TestFormatUptime:
    """Tests for format_uptime."""

    def test_format_uptime_seconds(self) -> None:
        """Test formatting uptime in seconds."""
        assert format_uptime(45) == "45s"

    def test_format_uptime_minutes(self) -> None:
        """Test formatting uptime in minutes."""
        assert format_uptime(125) == "2m 5s"

    def test_format_uptime_hours(self) -> None:
        """Test formatting uptime in hours."""
        assert format_uptime(3665) == "1h 1m 5s"

    def test_format_uptime_days(self) -> None:
        """Test formatting uptime in days."""
        assert format_uptime(90065) == "1d 1h 1m 5s"
