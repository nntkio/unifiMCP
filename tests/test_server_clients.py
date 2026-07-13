"""Tests for connected-client inventory and cmd/stamgr tools."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp.server import call_tool, format_clients


class TestCallToolClients:
    """Tests for client-related call_tool dispatch."""

    @pytest.mark.asyncio
    async def test_call_get_clients(self) -> None:
        """Test calling get_clients tool."""
        mock_client = AsyncMock()
        mock_client.get_clients = AsyncMock(
            return_value=[
                {
                    "hostname": "my-laptop",
                    "mac": "11:22:33:44:55:66",
                    "ip": "192.168.1.100",
                    "is_wired": False,
                    "essid": "MyNetwork",
                    "tx_bytes": 1024000,
                    "rx_bytes": 2048000,
                }
            ]
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_clients", {})

        assert len(result) == 1
        assert "my-laptop" in result[0].text
        assert "192.168.1.100" in result[0].text

    @pytest.mark.asyncio
    async def test_call_block_client(self) -> None:
        """Test calling block_client tool."""
        mock_client = AsyncMock()
        mock_client.block_client = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("block_client", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "blocked" in result[0].text
        mock_client.block_client.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_forget_client(self) -> None:
        """Test calling forget_client tool."""
        mock_client = AsyncMock()
        mock_client.forget_client = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("forget_client", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "forgotten" in result[0].text
        mock_client.forget_client.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_authorize_guest(self) -> None:
        """Test calling authorize_guest tool."""
        mock_client = AsyncMock()
        mock_client.authorize_guest = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "authorize_guest", {"mac": "aa:bb:cc:dd:ee:ff", "minutes": 60}
            )

        assert len(result) == 1
        assert "authorized" in result[0].text
        mock_client.authorize_guest.assert_called_once_with("aa:bb:cc:dd:ee:ff", 60)

    @pytest.mark.asyncio
    async def test_call_unauthorize_guest(self) -> None:
        """Test calling unauthorize_guest tool."""
        mock_client = AsyncMock()
        mock_client.unauthorize_guest = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("unauthorize_guest", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "revoked" in result[0].text
        mock_client.unauthorize_guest.assert_called_once_with("aa:bb:cc:dd:ee:ff")


class TestFormatClients:
    """Tests for format_clients."""

    def test_format_clients_empty(self) -> None:
        """Test formatting empty client list."""
        result = format_clients([])
        assert result == "No clients found."

    def test_format_clients_with_data(self) -> None:
        """Test formatting client list."""
        clients = [
            {
                "hostname": "laptop",
                "mac": "11:22:33:44:55:66",
                "ip": "192.168.1.50",
                "is_wired": True,
                "tx_bytes": 1024,
                "rx_bytes": 2048,
            }
        ]
        result = format_clients(clients)
        assert "laptop" in result
        assert "Wired" in result
        assert "192.168.1.50" in result
