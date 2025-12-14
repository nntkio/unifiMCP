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
    async def test_get_site_health(self, mock_client: UniFiClient) -> None:
        """Test get_site_health method."""
        mock_client._request.return_value = [
            {"subsystem": "wan", "status": "ok"},
            {"subsystem": "wlan", "status": "ok"},
        ]

        result = await mock_client.get_site_health()

        assert len(result) == 2
        mock_client._request.assert_called_once_with("GET", "/api/s/{site}/stat/health")
