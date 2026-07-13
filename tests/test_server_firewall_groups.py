"""Tests for firewall group CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._firewall_groups import (
    FIREWALL_GROUP_TOOLS,
    _handle_create_firewall_group,
    _handle_delete_firewall_group,
    _handle_get_firewall_groups,
    _handle_update_firewall_group,
    format_firewall_groups,
)


class TestHandleFirewallGroups:
    """Tests for firewall group tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_firewall_groups(self) -> None:
        """Test _handle_get_firewall_groups."""
        mock_client = AsyncMock()
        mock_client.get_firewall_groups = AsyncMock(
            return_value=[
                {
                    "name": "Blocklist",
                    "group_type": "address-group",
                    "group_members": [],
                }
            ]
        )

        result = await _handle_get_firewall_groups(mock_client, {})

        assert "Blocklist" in result
        mock_client.get_firewall_groups.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_firewall_group(self) -> None:
        """Test _handle_create_firewall_group."""
        mock_client = AsyncMock()
        mock_client.create_firewall_group = AsyncMock(
            return_value={"_id": "fg1", "name": "Blocklist"}
        )

        result = await _handle_create_firewall_group(
            mock_client,
            {"group": {"name": "Blocklist", "group_type": "address-group"}},
        )

        assert "Blocklist" in result
        mock_client.create_firewall_group.assert_called_once_with(
            {"name": "Blocklist", "group_type": "address-group"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_firewall_group(self) -> None:
        """Test _handle_update_firewall_group."""
        mock_client = AsyncMock()
        mock_client.update_firewall_group = AsyncMock()

        result = await _handle_update_firewall_group(
            mock_client,
            {"group_id": "fg1", "group": {"name": "Blocklist"}},
        )

        assert "updated" in result
        mock_client.update_firewall_group.assert_called_once_with(
            "fg1", {"name": "Blocklist"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_firewall_group(self) -> None:
        """Test _handle_delete_firewall_group."""
        mock_client = AsyncMock()
        mock_client.delete_firewall_group = AsyncMock()

        result = await _handle_delete_firewall_group(mock_client, {"group_id": "fg1"})

        assert "deleted" in result
        mock_client.delete_firewall_group.assert_called_once_with("fg1")


class TestFormatFirewallGroups:
    """Tests for format_firewall_groups."""

    def test_format_firewall_groups_empty(self) -> None:
        """Test formatting empty firewall group list."""
        result = format_firewall_groups([])
        assert result == "No firewall groups configured."

    def test_format_firewall_groups_with_data(self) -> None:
        """Test formatting firewall group list."""
        groups = [
            {
                "name": "Blocklist",
                "group_type": "address-group",
                "group_members": ["10.0.0.1", "10.0.0.2"],
            }
        ]
        result = format_firewall_groups(groups)
        assert "Blocklist" in result
        assert "address-group" in result
        assert "2" in result


class TestFirewallGroupTools:
    """Tests for FIREWALL_GROUP_TOOLS."""

    def test_tool_names(self) -> None:
        """Test that all expected tool names are present."""
        names = {tool.name for tool in FIREWALL_GROUP_TOOLS}
        assert names == {
            "get_firewall_groups",
            "create_firewall_group",
            "update_firewall_group",
            "delete_firewall_group",
        }
