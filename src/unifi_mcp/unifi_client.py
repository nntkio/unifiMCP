"""UniFi API client for communicating with UniFi Controller."""

import asyncio
import os
from typing import Any

import httpx


class UniFiError(Exception):
    """Base exception for UniFi API errors."""

    pass


class UniFiAuthenticationError(UniFiError):
    """Raised when authentication fails."""

    pass


class UniFiConnectionError(UniFiError):
    """Raised when connection to controller fails."""

    pass


def _normalize_mac(mac: str) -> str:
    """Normalize a MAC address for case/format-insensitive comparison."""
    return mac.lower().replace(":", "").replace("-", "")


def _env_bool(name: str, default: str, override: bool | None) -> bool:
    """Resolve a boolean setting from an explicit override or an environment variable."""
    if override is not None:
        return override
    return os.environ.get(name, default).lower() == "true"


class UniFiClient:
    """Client for interacting with UniFi Controller API."""

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        site: str | None = None,
        verify_ssl: bool | None = None,
        is_unifi_os: bool | None = None,
    ) -> None:
        """Initialize the UniFi client.

        Args:
            host: UniFi Controller host URL
            username: UniFi Controller username
            password: UniFi Controller password
            site: UniFi site name
            verify_ssl: Whether to verify SSL certificates
            is_unifi_os: Whether the controller is a UniFi OS device (UDM/UDM Pro)
        """
        self.host = host or os.environ.get("UNIFI_HOST", "")
        self.username = username or os.environ.get("UNIFI_USERNAME", "")
        self.password = password or os.environ.get("UNIFI_PASSWORD", "")
        self.site = site or os.environ.get("UNIFI_SITE", "default")
        self.verify_ssl = _env_bool("UNIFI_VERIFY_SSL", "true", verify_ssl)
        self.is_unifi_os = _env_bool("UNIFI_IS_UNIFI_OS", "false", is_unifi_os)
        self._client: httpx.AsyncClient | None = None
        self._logged_in: bool = False

    @property
    def _api_prefix(self) -> str:
        """Get the API prefix based on controller type."""
        return "/proxy/network" if self.is_unifi_os else ""

    def _api_url(self, endpoint: str) -> str:
        """Build the full API URL for an endpoint.

        Args:
            endpoint: The API endpoint (e.g., "/api/s/{site}/stat/device")

        Returns:
            The full URL with proper prefixing for UniFi OS if needed.
        """
        # Replace {site} placeholder with actual site
        endpoint = endpoint.replace("{site}", self.site)
        return f"{self._api_prefix}{endpoint}"

    async def connect(self) -> "UniFiClient":
        """Open the underlying HTTP client and log in."""
        self._client = httpx.AsyncClient(
            base_url=self.host,
            verify=self.verify_ssl,
            timeout=30.0,
        )
        await self.login()
        return self

    async def close(self) -> None:
        """Log out and close the underlying HTTP client."""
        if self._client:
            await self.logout()
            await self._client.aclose()

    async def __aenter__(self) -> "UniFiClient":
        """Enter async context."""
        return await self.connect()

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""
        await self.close()

    async def login(self) -> None:
        """Authenticate with the UniFi Controller."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        try:
            # UniFi OS uses a different login endpoint
            login_url = "/api/auth/login" if self.is_unifi_os else "/api/login"
            response = await self._client.post(
                login_url,
                json={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
            self._logged_in = True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise UniFiAuthenticationError("Invalid credentials") from e
            raise UniFiError(f"Login failed: {e}") from e
        except httpx.ConnectError as e:
            raise UniFiConnectionError(f"Failed to connect to {self.host}") from e

    async def logout(self) -> None:
        """Logout from the UniFi Controller."""
        if not self._client or not self._logged_in:
            return
        try:
            await self._client.post("/api/logout")
            self._logged_in = False
        except httpx.HTTPError:
            pass  # Ignore logout errors

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | None = None,
        _retry_on_expired_session: bool = True,
    ) -> list[dict[str, Any]]:
        """Make an API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json: JSON body for POST/PUT requests
            _retry_on_expired_session: Re-login and retry once on a 401,
                since a long-lived client's session cookie can expire
                between requests.

        Returns:
            The data array from the response.

        Raises:
            UniFiError: If the request fails.
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        url = self._api_url(endpoint)
        try:
            response = await self._client.request(method, url, json=json)
            if response.status_code == 401 and _retry_on_expired_session:
                await self.login()
                return await self._request(
                    method, endpoint, json=json, _retry_on_expired_session=False
                )
            response.raise_for_status()
            data = response.json()

            # Check for API-level errors
            meta = data.get("meta", {})
            if meta.get("rc") == "error":
                raise UniFiError(meta.get("msg", "Unknown API error"))

            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            raise UniFiError(f"Request failed: {e}") from e

    # Device Management
    async def get_devices(self) -> list[dict[str, Any]]:
        """Get all network devices.

        Returns:
            List of device dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/device")

    async def get_device(self, mac: str) -> dict[str, Any] | None:
        """Get a specific device by MAC address.

        Falls back to scanning the full device list if the single-device
        endpoint returns nothing, so callers can rely on a single lookup.

        Args:
            mac: Device MAC address.

        Returns:
            Device dictionary or None if not found.
        """
        devices = await self._request("GET", "/api/s/{site}/stat/device/" + mac)
        if devices:
            return devices[0]

        mac_normalized = _normalize_mac(mac)
        for device in await self.get_devices():
            if _normalize_mac(device.get("mac", "")) == mac_normalized:
                return device
        return None

    async def restart_device(self, mac: str) -> bool:
        """Restart a network device.

        Args:
            mac: Device MAC address.

        Returns:
            True if restart command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "restart", "mac": mac.lower()},
        )
        return True

    # Client Management
    async def get_clients(self) -> list[dict[str, Any]]:
        """Get all currently connected clients.

        Returns:
            List of client dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/sta")

    async def get_all_clients(self) -> list[dict[str, Any]]:
        """Get all known clients (including offline).

        Returns:
            List of client dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/alluser")

    async def block_client(self, mac: str) -> bool:
        """Block a client from the network.

        Args:
            mac: Client MAC address.

        Returns:
            True if block command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "block-sta", "mac": mac.lower()},
        )
        return True

    async def unblock_client(self, mac: str) -> bool:
        """Unblock a client from the network.

        Args:
            mac: Client MAC address.

        Returns:
            True if unblock command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "unblock-sta", "mac": mac.lower()},
        )
        return True

    async def disconnect_client(self, mac: str) -> bool:
        """Force disconnect a client.

        Args:
            mac: Client MAC address.

        Returns:
            True if disconnect command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "kick-sta", "mac": mac.lower()},
        )
        return True

    # Site Management
    async def get_sites(self) -> list[dict[str, Any]]:
        """Get all sites.

        Returns:
            List of site dictionaries.
        """
        return await self._request("GET", "/api/self/sites")

    async def get_site_health(self) -> list[dict[str, Any]]:
        """Get site health statistics.

        Returns:
            List of health metric dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/health")

    # Network Configuration
    async def get_networks(self) -> list[dict[str, Any]]:
        """Get all network configurations.

        Returns:
            List of network configuration dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/networkconf")

    # Device Activity
    async def get_device_clients(self, device_mac: str) -> list[dict[str, Any]]:
        """Get clients connected to a specific device (AP or switch).

        Args:
            device_mac: MAC address of the device.

        Returns:
            List of client dictionaries connected to this device.
        """
        all_clients = await self.get_clients()
        device_mac_normalized = _normalize_mac(device_mac)

        connected_clients = []
        for client in all_clients:
            # Check if client is connected to this AP (wireless) or switch (wired)
            ap_mac = _normalize_mac(client.get("ap_mac", ""))
            sw_mac = _normalize_mac(client.get("sw_mac", ""))

            if device_mac_normalized in (ap_mac, sw_mac):
                connected_clients.append(client)

        return connected_clients

    async def get_device_activity(self, device_mac: str) -> dict[str, Any]:
        """Get activity summary for a specific device.

        This includes the device info, connected clients, and their traffic.

        Args:
            device_mac: MAC address of the device.

        Returns:
            Dictionary with device info and connected clients.
        """
        device, clients = await asyncio.gather(
            self.get_device(device_mac), self.get_device_clients(device_mac)
        )

        total_tx = sum(c.get("tx_bytes", 0) for c in clients)
        total_rx = sum(c.get("rx_bytes", 0) for c in clients)

        return {
            "device": device,
            "clients": clients,
            "client_count": len(clients),
            "total_tx_bytes": total_tx,
            "total_rx_bytes": total_rx,
        }
