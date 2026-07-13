"""Tests for UniFi client network object CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._objects import _NetworkObjectMixin


class TestUniFiClientObjects:
    """Tests for network object methods."""

    @pytest.fixture
    def mock_client(self) -> _NetworkObjectMixin:
        """Create a mock client for testing."""
        client = _NetworkObjectMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_objects(self, mock_client: _NetworkObjectMixin) -> None:
        """Test get_objects method."""
        mock_client._request_v2.return_value = [{"_id": "obj1", "name": "Servers"}]

        result = await mock_client.get_objects()

        assert result == [{"_id": "obj1", "name": "Servers"}]
        mock_client._request_v2.assert_called_once_with("GET", "/objects")

    @pytest.mark.asyncio
    async def test_create_object(self, mock_client: _NetworkObjectMixin) -> None:
        """Test create_object method."""
        mock_client._request_v2.return_value = [{"_id": "obj1", "name": "Servers"}]

        result = await mock_client.create_object(
            {"name": "Servers", "object_type": "address_group"}
        )

        assert result == {"_id": "obj1", "name": "Servers"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/objects",
            json={"name": "Servers", "object_type": "address_group"},
        )

    @pytest.mark.asyncio
    async def test_update_object(self, mock_client: _NetworkObjectMixin) -> None:
        """Test update_object method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.update_object(
            "obj1", {"_id": "obj1", "name": "Servers", "object_type": "address_group"}
        )

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/objects/obj1",
            json={"_id": "obj1", "name": "Servers", "object_type": "address_group"},
        )

    @pytest.mark.asyncio
    async def test_delete_object(self, mock_client: _NetworkObjectMixin) -> None:
        """Test delete_object method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_object("obj1")

        assert result is True
        mock_client._request_v2.assert_called_once_with("DELETE", "/objects/obj1")
