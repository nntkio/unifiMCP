"""Tests for legacy firewall rule and zone-based firewall policy tools."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp.server import (
    call_tool,
    format_firewall_rules,
    format_firewall_zone_matrix,
    format_firewall_zones,
)


class TestCallToolFirewall:
    """Tests for firewall-related call_tool dispatch."""

    @pytest.mark.asyncio
    async def test_call_get_firewall_rules(self) -> None:
        """Test calling get_firewall_rules tool merges legacy rules and zone-based policies."""
        mock_client = AsyncMock()
        mock_client.get_firewall_rules = AsyncMock(
            return_value=[
                {
                    "_id": "rule1",
                    "name": "Block WAN",
                    "ruleset": "WAN_IN",
                    "action": "drop",
                    "enabled": True,
                }
            ]
        )
        mock_client.get_firewall_policies = AsyncMock(
            return_value=[
                {
                    "_id": "policy1",
                    "name": "Block Guest to LAN",
                    "action": "BLOCK",
                    "enabled": False,
                    "predefined": False,
                }
            ]
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_firewall_rules", {})

        assert len(result) == 1
        assert "Block WAN" in result[0].text
        assert "Active" in result[0].text
        assert "Block Guest to LAN" in result[0].text
        assert "Inactive" in result[0].text

    @pytest.mark.asyncio
    async def test_call_enable_firewall_rule(self) -> None:
        """Test calling enable_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_rule_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("enable_firewall_rule", {"rule_id": "rule1"})

        assert len(result) == 1
        assert "enabled" in result[0].text
        mock_client.set_firewall_rule_enabled.assert_called_once_with("rule1", True)

    @pytest.mark.asyncio
    async def test_call_disable_firewall_rule(self) -> None:
        """Test calling disable_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_rule_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("disable_firewall_rule", {"rule_id": "rule1"})

        assert len(result) == 1
        assert "disabled" in result[0].text
        mock_client.set_firewall_rule_enabled.assert_called_once_with("rule1", False)

    @pytest.mark.asyncio
    async def test_call_create_firewall_rule(self) -> None:
        """Test calling create_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.create_firewall_rule = AsyncMock(
            return_value={"_id": "rule1", "name": "Block WAN"}
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "create_firewall_rule",
                {"rule": {"name": "Block WAN", "ruleset": "WAN_IN"}},
            )

        assert len(result) == 1
        assert "Block WAN" in result[0].text
        mock_client.create_firewall_rule.assert_called_once_with(
            {"name": "Block WAN", "ruleset": "WAN_IN"}
        )

    @pytest.mark.asyncio
    async def test_call_delete_firewall_rule(self) -> None:
        """Test calling delete_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.delete_firewall_rule = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("delete_firewall_rule", {"rule_id": "rule1"})

        assert len(result) == 1
        assert "deleted" in result[0].text
        mock_client.delete_firewall_rule.assert_called_once_with("rule1")

    @pytest.mark.asyncio
    async def test_call_enable_firewall_policy(self) -> None:
        """Test calling enable_firewall_policy tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_policy_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("enable_firewall_policy", {"policy_id": "policy1"})

        assert len(result) == 1
        assert "enabled" in result[0].text
        mock_client.set_firewall_policy_enabled.assert_called_once_with("policy1", True)

    @pytest.mark.asyncio
    async def test_call_disable_firewall_policy(self) -> None:
        """Test calling disable_firewall_policy tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_policy_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "disable_firewall_policy", {"policy_id": "policy1"}
            )

        assert len(result) == 1
        assert "disabled" in result[0].text
        mock_client.set_firewall_policy_enabled.assert_called_once_with(
            "policy1", False
        )

    @pytest.mark.asyncio
    async def test_call_create_firewall_policy(self) -> None:
        """Test calling create_firewall_policy tool."""
        mock_client = AsyncMock()
        mock_client.create_firewall_policy = AsyncMock(
            return_value={"_id": "policy1", "name": "Block Guest to LAN"}
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "create_firewall_policy",
                {"policy": {"name": "Block Guest to LAN", "action": "BLOCK"}},
            )

        assert len(result) == 1
        assert "Block Guest to LAN" in result[0].text
        mock_client.create_firewall_policy.assert_called_once_with(
            {"name": "Block Guest to LAN", "action": "BLOCK"}
        )

    @pytest.mark.asyncio
    async def test_call_batch_update_firewall_policies(self) -> None:
        """Test calling batch_update_firewall_policies tool."""
        mock_client = AsyncMock()
        mock_client.batch_update_firewall_policies = AsyncMock()
        policies = [{"_id": "policy1", "enabled": False}]
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "batch_update_firewall_policies", {"policies": policies}
            )

        assert len(result) == 1
        assert "Updated 1" in result[0].text
        mock_client.batch_update_firewall_policies.assert_called_once_with(policies)

    @pytest.mark.asyncio
    async def test_call_batch_delete_firewall_policies(self) -> None:
        """Test calling batch_delete_firewall_policies tool."""
        mock_client = AsyncMock()
        mock_client.batch_delete_firewall_policies = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "batch_delete_firewall_policies", {"policy_ids": ["policy1"]}
            )

        assert len(result) == 1
        assert "Deleted 1" in result[0].text
        mock_client.batch_delete_firewall_policies.assert_called_once_with(["policy1"])


class TestCallToolFirewallZones:
    """Tests for firewall zone-related call_tool dispatch."""

    @pytest.mark.asyncio
    async def test_call_get_firewall_zones(self) -> None:
        """Test calling get_firewall_zones tool."""
        mock_client = AsyncMock()
        mock_client.get_firewall_zones = AsyncMock(
            return_value=[{"_id": "zone1", "name": "Internal"}]
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_firewall_zones", {})

        assert len(result) == 1
        assert "Internal" in result[0].text

    @pytest.mark.asyncio
    async def test_call_get_firewall_zone_matrix(self) -> None:
        """Test calling get_firewall_zone_matrix tool."""
        mock_client = AsyncMock()
        mock_client.get_firewall_zone_matrix = AsyncMock(
            return_value=[
                {
                    "from_zone_name": "Internal",
                    "to_zone_name": "External",
                    "action": "allow",
                }
            ]
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_firewall_zone_matrix", {})

        assert len(result) == 1
        assert "Internal" in result[0].text
        assert "External" in result[0].text


class TestFormatFirewallZones:
    """Tests for format_firewall_zones and format_firewall_zone_matrix."""

    def test_format_firewall_zones_empty(self) -> None:
        """Test formatting empty firewall zone list."""
        result = format_firewall_zones([])
        assert result == "No firewall zones configured."

    def test_format_firewall_zones_with_data(self) -> None:
        """Test formatting firewall zone list."""
        zones = [{"_id": "zone1", "name": "Internal"}]
        result = format_firewall_zones(zones)
        assert "Internal" in result
        assert "zone1" in result

    def test_format_firewall_zone_matrix_empty(self) -> None:
        """Test formatting empty firewall zone matrix."""
        result = format_firewall_zone_matrix([])
        assert result == "No firewall zone matrix data available."

    def test_format_firewall_zone_matrix_with_data(self) -> None:
        """Test formatting firewall zone matrix."""
        matrix = [
            {
                "from_zone_name": "Internal",
                "to_zone_name": "External",
                "action": "allow",
            }
        ]
        result = format_firewall_zone_matrix(matrix)
        assert "Internal" in result
        assert "External" in result
        assert "allow" in result


class TestFormatFirewallRules:
    """Tests for format_firewall_rules."""

    def test_format_firewall_rules_empty(self) -> None:
        """Test formatting empty firewall rule/policy lists."""
        result = format_firewall_rules([], [])
        assert result == "No firewall rules or policies configured."

    def test_format_firewall_rules_with_data(self) -> None:
        """Test formatting legacy firewall rules."""
        rules = [
            {
                "_id": "rule1",
                "name": "Block WAN",
                "ruleset": "WAN_IN",
                "action": "drop",
                "enabled": True,
            },
            {
                "_id": "rule2",
                "name": "Allow LAN",
                "ruleset": "LAN_IN",
                "action": "accept",
                "enabled": False,
            },
        ]
        result = format_firewall_rules(rules, [])
        assert "Block WAN" in result
        assert "WAN_IN" in result
        assert "DROP" in result
        assert "Active" in result
        assert "Allow LAN" in result
        assert "Inactive" in result

    def test_format_firewall_rules_with_policies(self) -> None:
        """Test formatting zone-based firewall policies."""
        policies = [
            {
                "_id": "policy1",
                "name": "Block Guest to LAN",
                "action": "BLOCK",
                "enabled": True,
                "predefined": False,
            },
            {
                "_id": "policy2",
                "name": "Allow Established/Related",
                "action": "ALLOW",
                "enabled": True,
                "predefined": True,
            },
        ]
        result = format_firewall_rules([], policies)
        assert "Block Guest to LAN" in result
        assert "Zone Policy" in result
        assert "Allow Established/Related" in result
        assert "Yes" in result
        assert "No" in result
