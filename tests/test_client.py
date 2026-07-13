"""Tests for UniFi client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from unifi_mcp.unifi_client import (
    UniFiClient,
    UniFiError,
)


class TestUniFiClientInit:
    """Tests for UniFi client initialization."""

    def test_client_initialization_with_params(self) -> None:
        """Test that the client initializes with provided values."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="password",
            site="mysite",
            verify_ssl=False,
            is_unifi_os=True,
        )
        assert client.host == "https://unifi.local"
        assert client.username == "admin"
        assert client.password == "password"
        assert client.site == "mysite"
        assert client.verify_ssl is False
        assert client.is_unifi_os is True

    def test_client_initialization_with_defaults(self) -> None:
        """Test that the client uses defaults for missing values."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="password",
        )
        assert client.site == "default"
        assert client.verify_ssl is True
        assert client.is_unifi_os is False

    def test_client_initialization_from_env(self) -> None:
        """Test that the client reads from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "UNIFI_HOST": "https://env.unifi.local",
                "UNIFI_USERNAME": "envuser",
                "UNIFI_PASSWORD": "envpass",
                "UNIFI_SITE": "envsite",
                "UNIFI_VERIFY_SSL": "false",
                "UNIFI_IS_UNIFI_OS": "true",
            },
        ):
            client = UniFiClient()
            assert client.host == "https://env.unifi.local"
            assert client.username == "envuser"
            assert client.password == "envpass"
            assert client.site == "envsite"
            assert client.verify_ssl is False
            assert client.is_unifi_os is True


class TestUniFiClientApiUrl:
    """Tests for API URL building."""

    def test_api_url_standard_controller(self) -> None:
        """Test API URL for standard controller."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
            site="default",
            is_unifi_os=False,
        )
        url = client._api_url("/api/s/{site}/stat/device")
        assert url == "/api/s/default/stat/device"

    def test_api_url_unifi_os(self) -> None:
        """Test API URL for UniFi OS controller."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
            site="default",
            is_unifi_os=True,
        )
        url = client._api_url("/api/s/{site}/stat/device")
        assert url == "/proxy/network/api/s/default/stat/device"

    def test_api_url_custom_site(self) -> None:
        """Test API URL with custom site."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
            site="mysite",
            is_unifi_os=False,
        )
        url = client._api_url("/api/s/{site}/stat/sta")
        assert url == "/api/s/mysite/stat/sta"


class TestUniFiClientLogin:
    """Tests for login functionality."""

    @pytest.mark.asyncio
    async def test_login_success(self) -> None:
        """Test successful login."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        await client.login()

        assert client._logged_in is True
        mock_http_client.post.assert_called_once_with(
            "/api/login",
            json={"username": "admin", "password": "pass"},
        )

    @pytest.mark.asyncio
    async def test_login_unifi_os_endpoint(self) -> None:
        """Test login uses correct endpoint for UniFi OS."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
            is_unifi_os=True,
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        await client.login()

        mock_http_client.post.assert_called_once_with(
            "/api/auth/login",
            json={"username": "admin", "password": "pass"},
        )

    @pytest.mark.asyncio
    async def test_login_not_initialized(self) -> None:
        """Test login fails when client not initialized."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
        )
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.login()


class TestUniFiClientRequest:
    """Tests for API request functionality."""

    @pytest.mark.asyncio
    async def test_request_success(self) -> None:
        """Test successful API request."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "meta": {"rc": "ok"},
                "data": [{"name": "device1"}, {"name": "device2"}],
            }
        )

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        result = await client._request("GET", "/api/s/{site}/stat/device")

        assert len(result) == 2
        assert result[0]["name"] == "device1"

    @pytest.mark.asyncio
    async def test_request_relogs_in_on_expired_session(self) -> None:
        """Test that a 401 triggers exactly one re-login and retry."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
        )

        unauthorized_response = MagicMock()
        unauthorized_response.status_code = 401

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()
        ok_response.json = MagicMock(
            return_value={"meta": {"rc": "ok"}, "data": [{"name": "device1"}]}
        )

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(
            side_effect=[unauthorized_response, ok_response]
        )
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(raise_for_status=MagicMock())
        )
        client._client = mock_http_client

        result = await client._request("GET", "/api/s/{site}/stat/device")

        assert result == [{"name": "device1"}]
        assert mock_http_client.request.call_count == 2
        mock_http_client.post.assert_called_once_with(
            "/api/login",
            json={"username": "admin", "password": "pass"},
        )

    @pytest.mark.asyncio
    async def test_request_api_error(self) -> None:
        """Test API-level error handling."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
        )
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "meta": {"rc": "error", "msg": "api.err.LoginRequired"},
                "data": [],
            }
        )

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        with pytest.raises(UniFiError, match="api.err.LoginRequired"):
            await client._request("GET", "/api/s/{site}/stat/device")


class TestUniFiClientMethods:
    """Tests for client API methods."""

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
    async def test_get_devices(self, mock_client: UniFiClient) -> None:
        """Test get_devices method."""
        mock_client._request.return_value = [{"name": "AP1"}, {"name": "SW1"}]

        result = await mock_client.get_devices()

        assert len(result) == 2
        mock_client._request.assert_called_once_with("GET", "/api/s/{site}/stat/device")

    @pytest.mark.asyncio
    async def test_get_clients(self, mock_client: UniFiClient) -> None:
        """Test get_clients method."""
        mock_client._request.return_value = [{"hostname": "laptop"}]

        result = await mock_client.get_clients()

        assert len(result) == 1
        mock_client._request.assert_called_once_with("GET", "/api/s/{site}/stat/sta")

    @pytest.mark.asyncio
    async def test_block_client(self, mock_client: UniFiClient) -> None:
        """Test block_client method."""
        mock_client._request.return_value = []

        result = await mock_client.block_client("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "block-sta", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_restart_device(self, mock_client: UniFiClient) -> None:
        """Test restart_device method."""
        mock_client._request.return_value = []

        result = await mock_client.restart_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "restart", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_adopt_device(self, mock_client: UniFiClient) -> None:
        """Test adopt_device method."""
        mock_client._request.return_value = []

        result = await mock_client.adopt_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "adopt", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_force_provision_device(self, mock_client: UniFiClient) -> None:
        """Test force_provision_device method."""
        mock_client._request.return_value = []

        result = await mock_client.force_provision_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "force-provision", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_upgrade_device(self, mock_client: UniFiClient) -> None:
        """Test upgrade_device method."""
        mock_client._request.return_value = []

        result = await mock_client.upgrade_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "upgrade", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_power_cycle_port(self, mock_client: UniFiClient) -> None:
        """Test power_cycle_port method."""
        mock_client._request.return_value = []

        result = await mock_client.power_cycle_port("AA:BB:CC:DD:EE:FF", 3)

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "power-cycle", "mac": "aa:bb:cc:dd:ee:ff", "port_idx": 3},
        )

    @pytest.mark.asyncio
    async def test_set_device_locate(self, mock_client: UniFiClient) -> None:
        """Test set_device_locate method."""
        mock_client._request.return_value = []

        result = await mock_client.set_device_locate("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "set-locate", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_unset_device_locate(self, mock_client: UniFiClient) -> None:
        """Test unset_device_locate method."""
        mock_client._request.return_value = []

        result = await mock_client.unset_device_locate("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "unset-locate", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_forget_client(self, mock_client: UniFiClient) -> None:
        """Test forget_client method."""
        mock_client._request.return_value = []

        result = await mock_client.forget_client("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "forget-sta", "macs": ["aa:bb:cc:dd:ee:ff"]},
        )

    @pytest.mark.asyncio
    async def test_authorize_guest(self, mock_client: UniFiClient) -> None:
        """Test authorize_guest method without a session length."""
        mock_client._request.return_value = []

        result = await mock_client.authorize_guest("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "authorize-guest", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_authorize_guest_with_minutes(self, mock_client: UniFiClient) -> None:
        """Test authorize_guest method with a session length."""
        mock_client._request.return_value = []

        result = await mock_client.authorize_guest("AA:BB:CC:DD:EE:FF", minutes=60)

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={
                "cmd": "authorize-guest",
                "mac": "aa:bb:cc:dd:ee:ff",
                "minutes": 60,
            },
        )

    @pytest.mark.asyncio
    async def test_unauthorize_guest(self, mock_client: UniFiClient) -> None:
        """Test unauthorize_guest method."""
        mock_client._request.return_value = []

        result = await mock_client.unauthorize_guest("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "unauthorize-guest", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_get_site_health(self, mock_client: UniFiClient) -> None:
        """Test get_site_health method."""
        mock_client._request.return_value = [
            {"subsystem": "wan", "status": "ok"},
            {"subsystem": "wlan", "status": "ok"},
        ]

        result = await mock_client.get_site_health()

        assert len(result) == 2
        mock_client._request.assert_called_once_with("GET", "/api/s/{site}/stat/health")

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
    async def test_create_network(self, mock_client: UniFiClient) -> None:
        """Test create_network method."""
        mock_client._request.return_value = [{"_id": "net1", "name": "IoT"}]

        result = await mock_client.create_network({"name": "IoT", "vlan": 20})

        assert result == {"_id": "net1", "name": "IoT"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/networkconf",
            json={"name": "IoT", "vlan": 20},
        )

    @pytest.mark.asyncio
    async def test_update_network(self, mock_client: UniFiClient) -> None:
        """Test update_network method."""
        mock_client._request.return_value = []

        result = await mock_client.update_network(
            "net1", {"_id": "net1", "name": "IoT", "vlan": 21}
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/networkconf/net1",
            json={"_id": "net1", "name": "IoT", "vlan": 21},
        )

    @pytest.mark.asyncio
    async def test_delete_network(self, mock_client: UniFiClient) -> None:
        """Test delete_network method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_network("net1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/networkconf/net1"
        )

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
