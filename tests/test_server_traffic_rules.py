"""Tests for legacy traffic rule tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._traffic_rules import (
    TRAFFIC_RULE_TOOLS,
    _handle_create_traffic_rule,
    _handle_delete_traffic_rule,
    _handle_disable_traffic_rule,
    _handle_enable_traffic_rule,
    _handle_get_traffic_rules,
    _handle_update_traffic_rule,
    format_traffic_rules,
)


class TestTrafficRuleHandlers:
    """Tests for traffic rule tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_traffic_rules(self) -> None:
        """Test _handle_get_traffic_rules formats the rules from the client."""
        mock_client = AsyncMock()
        mock_client.get_traffic_rules = AsyncMock(
            return_value=[
                {
                    "_id": "rule1",
                    "description": "Block Streaming",
                    "action": "BLOCK",
                    "enabled": True,
                }
            ]
        )

        result = await _handle_get_traffic_rules(mock_client, {})

        assert "Block Streaming" in result
        assert "BLOCK" in result
        assert "Enabled" in result
        mock_client.get_traffic_rules.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_traffic_rule(self) -> None:
        """Test _handle_create_traffic_rule creates and reports the new rule."""
        mock_client = AsyncMock()
        mock_client.create_traffic_rule = AsyncMock(
            return_value={"_id": "rule1", "description": "Block Streaming"}
        )

        result = await _handle_create_traffic_rule(
            mock_client, {"rule": {"description": "Block Streaming", "action": "BLOCK"}}
        )

        assert "Block Streaming" in result
        mock_client.create_traffic_rule.assert_called_once_with(
            {"description": "Block Streaming", "action": "BLOCK"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_traffic_rule(self) -> None:
        """Test _handle_update_traffic_rule passes rule_id and rule through."""
        mock_client = AsyncMock()
        mock_client.update_traffic_rule = AsyncMock()

        result = await _handle_update_traffic_rule(
            mock_client,
            {"rule_id": "rule1", "rule": {"description": "Block Streaming"}},
        )

        assert "rule1" in result
        assert "updated" in result
        mock_client.update_traffic_rule.assert_called_once_with(
            "rule1", {"description": "Block Streaming"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_traffic_rule(self) -> None:
        """Test _handle_delete_traffic_rule deletes by rule_id."""
        mock_client = AsyncMock()
        mock_client.delete_traffic_rule = AsyncMock()

        result = await _handle_delete_traffic_rule(mock_client, {"rule_id": "rule1"})

        assert "rule1" in result
        assert "deleted" in result
        mock_client.delete_traffic_rule.assert_called_once_with("rule1")

    @pytest.mark.asyncio
    async def test_handle_enable_traffic_rule(self) -> None:
        """Test _handle_enable_traffic_rule enables by rule_id."""
        mock_client = AsyncMock()
        mock_client.set_traffic_rule_enabled = AsyncMock()

        result = await _handle_enable_traffic_rule(mock_client, {"rule_id": "rule1"})

        assert "enabled" in result
        mock_client.set_traffic_rule_enabled.assert_called_once_with("rule1", True)

    @pytest.mark.asyncio
    async def test_handle_disable_traffic_rule(self) -> None:
        """Test _handle_disable_traffic_rule disables by rule_id."""
        mock_client = AsyncMock()
        mock_client.set_traffic_rule_enabled = AsyncMock()

        result = await _handle_disable_traffic_rule(mock_client, {"rule_id": "rule1"})

        assert "disabled" in result
        mock_client.set_traffic_rule_enabled.assert_called_once_with("rule1", False)


class TestFormatTrafficRules:
    """Tests for format_traffic_rules."""

    def test_format_traffic_rules_empty(self) -> None:
        """Test formatting empty traffic rule list."""
        result = format_traffic_rules([])
        assert result == "No traffic rules configured."

    def test_format_traffic_rules_with_data(self) -> None:
        """Test formatting a non-empty traffic rule list."""
        rules = [
            {
                "_id": "rule1",
                "description": "Block Streaming",
                "action": "BLOCK",
                "enabled": True,
            },
            {
                "_id": "rule2",
                "description": "Allow Gaming",
                "action": "ALLOW",
                "enabled": False,
            },
        ]

        result = format_traffic_rules(rules)

        assert "Block Streaming" in result
        assert "BLOCK" in result
        assert "Enabled" in result
        assert "Allow Gaming" in result
        assert "Disabled" in result


class TestTrafficRuleTools:
    """Tests for the TRAFFIC_RULE_TOOLS registry."""

    def test_traffic_rule_tools_names(self) -> None:
        """Test TRAFFIC_RULE_TOOLS contains all expected tool names."""
        names = {tool.name for tool in TRAFFIC_RULE_TOOLS}
        assert names == {
            "get_traffic_rules",
            "create_traffic_rule",
            "update_traffic_rule",
            "delete_traffic_rule",
            "enable_traffic_rule",
            "disable_traffic_rule",
        }
