"""Tests for UniFi client legacy firewall rules and zone-based firewall policies."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client import (
    UniFiClient,
    UniFiError,
)


class TestUniFiClientFirewall:
    """Tests for firewall rule and policy methods."""

    @pytest.fixture
    def mock_client(self) -> UniFiClient:
        """Create a mock client for testing."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
        )
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_firewall_rules(self, mock_client: UniFiClient) -> None:
        """Test get_firewall_rules method."""
        mock_client._request.return_value = [{"name": "Block WAN"}]

        result = await mock_client.get_firewall_rules()

        assert len(result) == 1
        mock_client._request.assert_called_once_with(
            "GET", "/api/s/{site}/rest/firewallrule"
        )

    @pytest.mark.asyncio
    async def test_get_firewall_rules_zone_based_migrated(
        self, mock_client: UniFiClient
    ) -> None:
        """Test get_firewall_rules returns [] when the console has migrated to zone-based firewall."""
        mock_client._request.side_effect = UniFiError("api.err.InvalidObject")

        result = await mock_client.get_firewall_rules()

        assert result == []

    @pytest.mark.asyncio
    async def test_set_firewall_rule_enabled(self, mock_client: UniFiClient) -> None:
        """Test set_firewall_rule_enabled enables a rule found by ID."""
        mock_client.get_firewall_rules = AsyncMock(
            return_value=[
                {"_id": "rule1", "name": "Block WAN", "enabled": False},
                {"_id": "rule2", "name": "Allow LAN", "enabled": True},
            ]
        )

        result = await mock_client.set_firewall_rule_enabled("rule1", True)

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/firewallrule/rule1",
            json={"_id": "rule1", "name": "Block WAN", "enabled": True},
        )

    @pytest.mark.asyncio
    async def test_set_firewall_rule_enabled_not_found(
        self, mock_client: UniFiClient
    ) -> None:
        """Test set_firewall_rule_enabled raises when the rule ID doesn't exist."""
        mock_client.get_firewall_rules = AsyncMock(return_value=[])

        with pytest.raises(UniFiError, match="Firewall rule not found"):
            await mock_client.set_firewall_rule_enabled("missing", True)

    @pytest.mark.asyncio
    async def test_create_firewall_rule(self, mock_client: UniFiClient) -> None:
        """Test create_firewall_rule method."""
        mock_client._request.return_value = [{"_id": "rule1", "name": "Block WAN"}]

        result = await mock_client.create_firewall_rule(
            {"name": "Block WAN", "ruleset": "WAN_IN", "action": "drop"}
        )

        assert result == {"_id": "rule1", "name": "Block WAN"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/firewallrule",
            json={"name": "Block WAN", "ruleset": "WAN_IN", "action": "drop"},
        )

    @pytest.mark.asyncio
    async def test_delete_firewall_rule(self, mock_client: UniFiClient) -> None:
        """Test delete_firewall_rule method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_firewall_rule("rule1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/firewallrule/rule1"
        )

    @pytest.mark.asyncio
    async def test_get_firewall_policies(self, mock_client: UniFiClient) -> None:
        """Test get_firewall_policies method."""
        mock_client._request_v2 = AsyncMock(
            return_value=[{"_id": "policy1", "name": "Block Guest to LAN"}]
        )

        result = await mock_client.get_firewall_policies()

        assert len(result) == 1
        mock_client._request_v2.assert_called_once_with("GET", "/firewall-policies")

    @pytest.mark.asyncio
    async def test_set_firewall_policy_enabled(self, mock_client: UniFiClient) -> None:
        """Test set_firewall_policy_enabled enables a policy found by ID."""
        mock_client.get_firewall_policies = AsyncMock(
            return_value=[
                {"_id": "policy1", "name": "Block Guest to LAN", "enabled": False},
            ]
        )
        mock_client._request_v2 = AsyncMock()

        result = await mock_client.set_firewall_policy_enabled("policy1", True)

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/firewall-policies/policy1",
            json={"_id": "policy1", "name": "Block Guest to LAN", "enabled": True},
        )

    @pytest.mark.asyncio
    async def test_set_firewall_policy_enabled_not_found(
        self, mock_client: UniFiClient
    ) -> None:
        """Test set_firewall_policy_enabled raises when the policy ID doesn't exist."""
        mock_client.get_firewall_policies = AsyncMock(return_value=[])

        with pytest.raises(UniFiError, match="Firewall policy not found"):
            await mock_client.set_firewall_policy_enabled("missing", True)

    @pytest.mark.asyncio
    async def test_create_firewall_policy(self, mock_client: UniFiClient) -> None:
        """Test create_firewall_policy method."""
        mock_client._request_v2 = AsyncMock(
            return_value=[{"_id": "policy1", "name": "Block Guest to LAN"}]
        )

        result = await mock_client.create_firewall_policy(
            {"name": "Block Guest to LAN", "action": "BLOCK"}
        )

        assert result == {"_id": "policy1", "name": "Block Guest to LAN"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/firewall-policies",
            json={"name": "Block Guest to LAN", "action": "BLOCK"},
        )

    @pytest.mark.asyncio
    async def test_batch_update_firewall_policies(
        self, mock_client: UniFiClient
    ) -> None:
        """Test batch_update_firewall_policies method."""
        mock_client.get_firewall_policies = AsyncMock(
            return_value=[
                {"_id": "policy1", "name": "Block Guest to LAN", "predefined": False},
            ]
        )
        mock_client._request_v2 = AsyncMock()
        policies = [{"_id": "policy1", "name": "Block Guest to LAN", "enabled": False}]

        result = await mock_client.batch_update_firewall_policies(policies)

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT", "/firewall-policies/batch", json=policies
        )

    @pytest.mark.asyncio
    async def test_batch_update_firewall_policies_rejects_predefined(
        self, mock_client: UniFiClient
    ) -> None:
        """Test batch_update_firewall_policies raises for predefined policies."""
        mock_client.get_firewall_policies = AsyncMock(
            return_value=[
                {"_id": "policy1", "name": "Allow Established", "predefined": True},
            ]
        )
        mock_client._request_v2 = AsyncMock()

        with pytest.raises(UniFiError, match="Predefined firewall policies"):
            await mock_client.batch_update_firewall_policies(
                [{"_id": "policy1", "enabled": False}]
            )
        mock_client._request_v2.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_delete_firewall_policies(
        self, mock_client: UniFiClient
    ) -> None:
        """Test batch_delete_firewall_policies method."""
        mock_client.get_firewall_policies = AsyncMock(
            return_value=[
                {"_id": "policy1", "name": "Block Guest to LAN", "predefined": False},
            ]
        )
        mock_client._request_v2 = AsyncMock()

        result = await mock_client.batch_delete_firewall_policies(["policy1"])

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "POST", "/firewall-policies/batch-delete", json=["policy1"]
        )

    @pytest.mark.asyncio
    async def test_batch_delete_firewall_policies_rejects_predefined(
        self, mock_client: UniFiClient
    ) -> None:
        """Test batch_delete_firewall_policies raises for predefined policies."""
        mock_client.get_firewall_policies = AsyncMock(
            return_value=[
                {"_id": "policy1", "name": "Allow Established", "predefined": True},
            ]
        )
        mock_client._request_v2 = AsyncMock()

        with pytest.raises(UniFiError, match="Predefined firewall policies"):
            await mock_client.batch_delete_firewall_policies(["policy1"])
        mock_client._request_v2.assert_not_called()
