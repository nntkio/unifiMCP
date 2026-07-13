"""Tests for site inventory and health tools."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp.server import call_tool, format_health, format_sdn_status, format_sites


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


class TestFormatSdnStatus:
    """Tests for format_sdn_status."""

    def test_format_sdn_status_empty(self) -> None:
        """Test formatting empty SDN status data."""
        result = format_sdn_status([])
        assert result == "No SDN status data available."

    def test_format_sdn_status_with_data(self) -> None:
        """Test formatting SDN status data."""
        status = [{"state": "connected"}]
        result = format_sdn_status(status)
        assert "connected" in result


class TestCallToolSdnStatus:
    """Tests for the get_sdn_status call_tool dispatch."""

    @pytest.mark.asyncio
    async def test_call_get_sdn_status(self) -> None:
        """Test calling get_sdn_status tool."""
        mock_client = AsyncMock()
        mock_client.get_sdn_status = AsyncMock(return_value=[{"state": "connected"}])
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_sdn_status", {})

        assert len(result) == 1
        assert "connected" in result[0].text
