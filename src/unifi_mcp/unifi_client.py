"""UniFi API client for communicating with UniFi Controller."""

import os

import httpx


class UniFiClient:
    """Client for interacting with UniFi Controller API."""

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        site: str | None = None,
        verify_ssl: bool | None = None,
    ) -> None:
        """Initialize the UniFi client.

        Args:
            host: UniFi Controller host URL
            username: UniFi Controller username
            password: UniFi Controller password
            site: UniFi site name
            verify_ssl: Whether to verify SSL certificates
        """
        self.host = host or os.environ.get("UNIFI_HOST", "")
        self.username = username or os.environ.get("UNIFI_USERNAME", "")
        self.password = password or os.environ.get("UNIFI_PASSWORD", "")
        self.site = site or os.environ.get("UNIFI_SITE", "default")
        self.verify_ssl = (
            verify_ssl
            if verify_ssl is not None
            else os.environ.get("UNIFI_VERIFY_SSL", "true").lower() == "true"
        )
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "UniFiClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            base_url=self.host,
            verify=self.verify_ssl,
        )
        await self._login()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""
        if self._client:
            await self._logout()
            await self._client.aclose()

    async def _login(self) -> None:
        """Authenticate with the UniFi Controller."""
        if not self._client:
            raise RuntimeError("Client not initialized")
        response = await self._client.post(
            "/api/login",
            json={"username": self.username, "password": self.password},
        )
        response.raise_for_status()

    async def _logout(self) -> None:
        """Logout from the UniFi Controller."""
        if not self._client:
            return
        await self._client.post("/api/logout")
