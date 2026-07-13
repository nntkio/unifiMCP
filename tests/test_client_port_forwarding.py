"""Tests for UniFi client port forwarding rule CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._port_forwarding import _PortForwardingMixin


class TestUniFiClientPortForwarding:
    """Tests for port forwarding rule methods."""

    @pytest.fixture
    def mock_client(self) -> _PortForwardingMixin:
        """Create a mock client for testing."""
        client = _PortForwardingMixin()
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_port_forwards(self, mock_client: _PortForwardingMixin) -> None:
        """Test get_port_forwards method."""
        mock_client._request.return_value = [{"_id": "fwd1", "name": "Web Server"}]

        result = await mock_client.get_port_forwards()

        assert result == [{"_id": "fwd1", "name": "Web Server"}]
        mock_client._request.assert_called_once_with(
            "GET", "/api/s/{site}/rest/portforward"
        )

    @pytest.mark.asyncio
    async def test_create_port_forward(self, mock_client: _PortForwardingMixin) -> None:
        """Test create_port_forward method."""
        mock_client._request.return_value = [{"_id": "fwd1", "name": "Web Server"}]

        result = await mock_client.create_port_forward(
            {"name": "Web Server", "fwd": "192.168.1.10", "fwd_port": "80"}
        )

        assert result == {"_id": "fwd1", "name": "Web Server"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/portforward",
            json={"name": "Web Server", "fwd": "192.168.1.10", "fwd_port": "80"},
        )

    @pytest.mark.asyncio
    async def test_create_port_forward_empty_response(
        self, mock_client: _PortForwardingMixin
    ) -> None:
        """Test create_port_forward returns empty dict when no data is returned."""
        mock_client._request.return_value = []

        result = await mock_client.create_port_forward({"name": "Web Server"})

        assert result == {}

    @pytest.mark.asyncio
    async def test_update_port_forward(self, mock_client: _PortForwardingMixin) -> None:
        """Test update_port_forward method."""
        mock_client._request.return_value = []

        result = await mock_client.update_port_forward(
            "fwd1",
            {"_id": "fwd1", "name": "Web Server", "fwd_port": "8080"},
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/portforward/fwd1",
            json={"_id": "fwd1", "name": "Web Server", "fwd_port": "8080"},
        )

    @pytest.mark.asyncio
    async def test_delete_port_forward(self, mock_client: _PortForwardingMixin) -> None:
        """Test delete_port_forward method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_port_forward("fwd1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/portforward/fwd1"
        )
