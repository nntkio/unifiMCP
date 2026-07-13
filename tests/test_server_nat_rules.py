"""Tests for NAT rule CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._nat_rules import (
    NAT_RULE_TOOLS,
    _handle_create_nat_rule,
    _handle_delete_nat_rule,
    _handle_get_nat_rules,
    _handle_update_nat_rule,
    format_nat_rules,
)


class TestHandleNatRules:
    """Tests for NAT rule tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_nat_rules(self) -> None:
        """Test _handle_get_nat_rules."""
        mock_client = AsyncMock()
        mock_client.get_nat_rules = AsyncMock(
            return_value=[{"name": "Guest NAT", "enabled": True}]
        )

        result = await _handle_get_nat_rules(mock_client, {})

        assert "Guest NAT" in result
        mock_client.get_nat_rules.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_nat_rule(self) -> None:
        """Test _handle_create_nat_rule."""
        mock_client = AsyncMock()
        mock_client.create_nat_rule = AsyncMock(
            return_value={"_id": "nat1", "name": "Guest NAT"}
        )

        result = await _handle_create_nat_rule(
            mock_client, {"rule": {"name": "Guest NAT", "enabled": True}}
        )

        assert "Guest NAT" in result
        mock_client.create_nat_rule.assert_called_once_with(
            {"name": "Guest NAT", "enabled": True}
        )

    @pytest.mark.asyncio
    async def test_handle_update_nat_rule(self) -> None:
        """Test _handle_update_nat_rule."""
        mock_client = AsyncMock()
        mock_client.update_nat_rule = AsyncMock()

        result = await _handle_update_nat_rule(
            mock_client,
            {"rule_id": "nat1", "rule": {"name": "Guest NAT", "enabled": False}},
        )

        assert "updated" in result
        mock_client.update_nat_rule.assert_called_once_with(
            "nat1", {"name": "Guest NAT", "enabled": False}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_nat_rule(self) -> None:
        """Test _handle_delete_nat_rule."""
        mock_client = AsyncMock()
        mock_client.delete_nat_rule = AsyncMock()

        result = await _handle_delete_nat_rule(mock_client, {"rule_id": "nat1"})

        assert "deleted" in result
        mock_client.delete_nat_rule.assert_called_once_with("nat1")


class TestFormatNatRules:
    """Tests for format_nat_rules."""

    def test_format_nat_rules_empty(self) -> None:
        """Test formatting empty NAT rule list."""
        result = format_nat_rules([])
        assert result == "No NAT rules configured."

    def test_format_nat_rules_with_data(self) -> None:
        """Test formatting NAT rule list."""
        rules = [{"name": "Guest NAT", "enabled": True}]
        result = format_nat_rules(rules)
        assert "Guest NAT" in result
        assert "Enabled" in result


class TestNatRuleTools:
    """Tests for NAT_RULE_TOOLS."""

    def test_nat_rule_tools_contains_expected_tools(self) -> None:
        """Test that NAT_RULE_TOOLS lists all expected tool names."""
        names = {tool.name for tool in NAT_RULE_TOOLS}
        assert names == {
            "get_nat_rules",
            "create_nat_rule",
            "update_nat_rule",
            "delete_nat_rule",
        }
