"""Connection lifecycle, authentication, and request plumbing shared by all
UniFi API domain mixins.
"""

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


class _BaseClient:
    """Connection lifecycle, authentication, and request plumbing.

    Domain mixins (devices, clients, sites, networks, firewall) are combined
    with this class to form the public `UniFiClient`; they call `_request`/
    `_request_v2` but don't manage the connection themselves.
    """

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

    def _v2_api_url(self, endpoint: str) -> str:
        """Build the full v2 API URL for an endpoint.

        The v2 API backs newer features (e.g. zone-based firewall policies)
        and lives under a different path prefix than the classic API.

        Args:
            endpoint: The v2 API endpoint, relative to the site
                (e.g. "/firewall-policies").

        Returns:
            The full URL with proper prefixing for UniFi OS if needed.
        """
        prefix = "/proxy/network" if self.is_unifi_os else ""
        return f"{prefix}/v2/api/site/{self.site}{endpoint}"

    async def connect(self) -> "_BaseClient":
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

    async def __aenter__(self) -> "_BaseClient":
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
            # A stale session cookie on the client causes UniFi OS consoles to
            # reject a fresh login with 403, so clear it before every attempt
            # (this matters for the re-login-on-expired-session retry path).
            self._client.cookies.clear()

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

    async def _request_v2(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | list[Any] | None = None,
        _retry_on_expired_session: bool = True,
    ) -> list[dict[str, Any]]:
        """Make a v2 API request.

        The v2 API (used by zone-based firewall policies, traffic rules,
        etc.) returns a bare JSON array/object instead of the classic API's
        `{"meta": ..., "data": [...]}` envelope, and reports errors via an
        `errorCode` field rather than `meta.rc == "error"`, so it needs its
        own response handling.

        Args:
            method: HTTP method
            endpoint: v2 API endpoint, relative to the site
            json: JSON body for POST/PUT requests
            _retry_on_expired_session: Re-login and retry once on a 401

        Returns:
            The response data, always as a list.

        Raises:
            UniFiError: If the request fails.
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        url = self._v2_api_url(endpoint)
        try:
            response = await self._client.request(method, url, json=json)
            if response.status_code == 401 and _retry_on_expired_session:
                await self.login()
                return await self._request_v2(
                    method, endpoint, json=json, _retry_on_expired_session=False
                )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and "errorCode" in data:
                raise UniFiError(data.get("message", "Unknown API error"))

            return data if isinstance(data, list) else [data]
        except httpx.HTTPStatusError as e:
            raise UniFiError(f"Request failed: {e}") from e
