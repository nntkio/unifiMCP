"""Tests for site inventory and health tools."""

from unifi_mcp.server import format_health, format_sites


class TestFormatSites:
    """Tests for format_sites."""

    def test_format_sites_empty(self) -> None:
        """Test formatting empty site list."""
        result = format_sites([])
        assert result == "No sites found."

    def test_format_sites_with_data(self) -> None:
        """Test formatting site list."""
        sites = [{"name": "default", "desc": "Default Site", "_id": "abc123"}]
        result = format_sites(sites)
        assert "Default Site" in result
        assert "default" in result


class TestFormatHealth:
    """Tests for format_health."""

    def test_format_health_empty(self) -> None:
        """Test formatting empty health data."""
        result = format_health([])
        assert result == "No health data available."

    def test_format_health_with_data(self) -> None:
        """Test formatting health data."""
        health = [
            {"subsystem": "wan", "status": "ok", "gw_mac": "aa:bb:cc:dd:ee:ff"},
            {"subsystem": "wlan", "status": "ok", "num_ap": 3, "num_user": 10},
        ]
        result = format_health(health)
        assert "WAN" in result
        assert "WLAN" in result
        assert "ok" in result
        assert "Access Points: 3" in result
