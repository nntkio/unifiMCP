"""Tests for QoS rule tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._qos_rules import (
    QOS_RULE_TOOLS,
    _handle_batch_update_qos_rules,
    _handle_create_qos_rule,
    _handle_delete_qos_rule,
    _handle_get_qos_rules,
    _handle_update_qos_rule,
    format_qos_rules,
)


class TestQosRuleHandlers:
    """Tests for QoS rule tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_qos_rules(self) -> None:
        """Test _handle_get_qos_rules formats the rules from the client."""
        mock_client = AsyncMock()
        mock_client.get_qos_rules = AsyncMock(
            return_value=[{"_id": "rule1", "name": "Limit Guest", "enabled": True}]
        )

        result = await _handle_get_qos_rules(mock_client, {})

        assert "Limit Guest" in result
        assert "Enabled" in result
        mock_client.get_qos_rules.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_qos_rule(self) -> None:
        """Test _handle_create_qos_rule."""
        mock_client = AsyncMock()
        mock_client.create_qos_rule = AsyncMock(
            return_value={"_id": "rule1", "name": "Limit Guest"}
        )

        result = await _handle_create_qos_rule(
            mock_client, {"rule": {"name": "Limit Guest"}}
        )

        assert "Limit Guest" in result
        mock_client.create_qos_rule.assert_called_once_with({"name": "Limit Guest"})

    @pytest.mark.asyncio
    async def test_handle_update_qos_rule(self) -> None:
        """Test _handle_update_qos_rule."""
        mock_client = AsyncMock()
        mock_client.update_qos_rule = AsyncMock()

        result = await _handle_update_qos_rule(
            mock_client,
            {"rule_id": "rule1", "rule": {"_id": "rule1", "enabled": False}},
        )

        assert "rule1" in result
        assert "updated" in result
        mock_client.update_qos_rule.assert_called_once_with(
            "rule1", {"_id": "rule1", "enabled": False}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_qos_rule(self) -> None:
        """Test _handle_delete_qos_rule."""
        mock_client = AsyncMock()
        mock_client.delete_qos_rule = AsyncMock()

        result = await _handle_delete_qos_rule(mock_client, {"rule_id": "rule1"})

        assert "rule1" in result
        assert "deleted" in result
        mock_client.delete_qos_rule.assert_called_once_with("rule1")

    @pytest.mark.asyncio
    async def test_handle_batch_update_qos_rules(self) -> None:
        """Test _handle_batch_update_qos_rules."""
        mock_client = AsyncMock()
        mock_client.batch_update_qos_rules = AsyncMock()
        rules = [{"_id": "rule1", "enabled": False}]

        result = await _handle_batch_update_qos_rules(mock_client, {"rules": rules})

        assert "Updated 1" in result
        mock_client.batch_update_qos_rules.assert_called_once_with(rules)


class TestFormatQosRules:
    """Tests for format_qos_rules."""

    def test_format_qos_rules_empty(self) -> None:
        """Test formatting an empty QoS rule list."""
        result = format_qos_rules([])
        assert result == "No QoS rules configured."

    def test_format_qos_rules_with_data(self) -> None:
        """Test formatting QoS rules with data."""
        rules = [
            {"_id": "rule1", "name": "Limit Guest", "enabled": True},
            {"_id": "rule2", "name": "Limit IoT", "enabled": False},
        ]

        result = format_qos_rules(rules)

        assert "Limit Guest" in result
        assert "Enabled" in result
        assert "Limit IoT" in result
        assert "Disabled" in result


class TestQosRuleTools:
    """Tests for QOS_RULE_TOOLS."""

    def test_qos_rule_tools_names(self) -> None:
        """Test QOS_RULE_TOOLS contains all expected tool names."""
        names = {tool.name for tool in QOS_RULE_TOOLS}
        assert names == {
            "get_qos_rules",
            "create_qos_rule",
            "update_qos_rule",
            "delete_qos_rule",
            "batch_update_qos_rules",
        }
