"""Tests for network object CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._objects import (
    OBJECT_TOOLS,
    _handle_create_object,
    _handle_delete_object,
    _handle_get_objects,
    _handle_update_object,
    format_objects,
)


class TestHandleObjects:
    """Tests for network object handler functions."""

    @pytest.mark.asyncio
    async def test_handle_get_objects(self) -> None:
        """Test _handle_get_objects."""
        mock_client = AsyncMock()
        mock_client.get_objects = AsyncMock(
            return_value=[{"name": "Servers", "object_type": "address_group"}]
        )

        result = await _handle_get_objects(mock_client, {})

        assert "Servers" in result
        mock_client.get_objects.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_object(self) -> None:
        """Test _handle_create_object."""
        mock_client = AsyncMock()
        mock_client.create_object = AsyncMock(
            return_value={"_id": "obj1", "name": "Servers"}
        )

        result = await _handle_create_object(
            mock_client,
            {"object": {"name": "Servers", "object_type": "address_group"}},
        )

        assert "Servers" in result
        assert "created" in result
        mock_client.create_object.assert_called_once_with(
            {"name": "Servers", "object_type": "address_group"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_object(self) -> None:
        """Test _handle_update_object."""
        mock_client = AsyncMock()
        mock_client.update_object = AsyncMock()

        result = await _handle_update_object(
            mock_client,
            {"object_id": "obj1", "object": {"name": "Servers"}},
        )

        assert "obj1" in result
        assert "updated" in result
        mock_client.update_object.assert_called_once_with("obj1", {"name": "Servers"})

    @pytest.mark.asyncio
    async def test_handle_delete_object(self) -> None:
        """Test _handle_delete_object."""
        mock_client = AsyncMock()
        mock_client.delete_object = AsyncMock()

        result = await _handle_delete_object(mock_client, {"object_id": "obj1"})

        assert "obj1" in result
        assert "deleted" in result
        mock_client.delete_object.assert_called_once_with("obj1")


class TestFormatObjects:
    """Tests for format_objects."""

    def test_format_objects_empty(self) -> None:
        """Test formatting empty network object list."""
        result = format_objects([])
        assert result == "No network objects configured."

    def test_format_objects_with_data(self) -> None:
        """Test formatting network object list."""
        objects = [{"name": "Servers", "object_type": "address_group"}]
        result = format_objects(objects)
        assert "Servers" in result
        assert "address_group" in result


class TestObjectTools:
    """Tests for OBJECT_TOOLS."""

    def test_object_tools_names(self) -> None:
        """Test that OBJECT_TOOLS contains all expected tool names."""
        names = {tool.name for tool in OBJECT_TOOLS}
        assert names == {
            "get_objects",
            "create_object",
            "update_object",
            "delete_object",
        }
