"""Tests for UniFi client QoS rules."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._qos_rules import _QosRuleMixin


class TestUniFiClientQosRules:
    """Tests for QoS rule methods."""

    @pytest.fixture
    def mock_client(self) -> _QosRuleMixin:
        """Create a mock client for testing."""
        client = _QosRuleMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_qos_rules(self, mock_client: _QosRuleMixin) -> None:
        """Test get_qos_rules method."""
        mock_client._request_v2.return_value = [{"_id": "rule1", "name": "Limit Guest"}]

        result = await mock_client.get_qos_rules()

        assert len(result) == 1
        mock_client._request_v2.assert_called_once_with("GET", "/qos-rules")

    @pytest.mark.asyncio
    async def test_create_qos_rule(self, mock_client: _QosRuleMixin) -> None:
        """Test create_qos_rule method."""
        mock_client._request_v2.return_value = [{"_id": "rule1", "name": "Limit Guest"}]

        result = await mock_client.create_qos_rule(
            {"name": "Limit Guest", "enabled": True}
        )

        assert result == {"_id": "rule1", "name": "Limit Guest"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/qos-rules",
            json={"name": "Limit Guest", "enabled": True},
        )

    @pytest.mark.asyncio
    async def test_update_qos_rule(self, mock_client: _QosRuleMixin) -> None:
        """Test update_qos_rule method."""
        mock_client._request_v2.return_value = []
        rule = {"_id": "rule1", "name": "Limit Guest", "enabled": False}

        result = await mock_client.update_qos_rule("rule1", rule)

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT", "/qos-rules/rule1", json=rule
        )

    @pytest.mark.asyncio
    async def test_delete_qos_rule(self, mock_client: _QosRuleMixin) -> None:
        """Test delete_qos_rule method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_qos_rule("rule1")

        assert result is True
        mock_client._request_v2.assert_called_once_with("DELETE", "/qos-rules/rule1")

    @pytest.mark.asyncio
    async def test_batch_update_qos_rules(self, mock_client: _QosRuleMixin) -> None:
        """Test batch_update_qos_rules method."""
        mock_client._request_v2.return_value = []
        rules = [{"_id": "rule1", "name": "Limit Guest", "enabled": False}]

        result = await mock_client.batch_update_qos_rules(rules)

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT", "/qos-rules/batch", json=rules
        )
