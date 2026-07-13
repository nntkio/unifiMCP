"""Connected-client inventory and `cmd/stamgr` control actions."""

from typing import Any


class _ClientMixin:
    """Client management: inventory and control actions."""

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

    async def forget_client(self, mac: str) -> bool:
        """Remove a client from the controller's known-clients list.

        Args:
            mac: Client MAC address.

        Returns:
            True if the forget command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "forget-sta", "macs": [mac.lower()]},
        )
        return True

    async def authorize_guest(self, mac: str, minutes: int | None = None) -> bool:
        """Authorize a client through the guest portal.

        Args:
            mac: Client MAC address.
            minutes: Session length in minutes, if the authorization should
                expire automatically.

        Returns:
            True if the authorize command was sent successfully.
        """
        payload: dict[str, Any] = {"cmd": "authorize-guest", "mac": mac.lower()}
        if minutes is not None:
            payload["minutes"] = minutes
        await self._request("POST", "/api/s/{site}/cmd/stamgr", json=payload)
        return True

    async def unauthorize_guest(self, mac: str) -> bool:
        """Revoke a client's guest portal authorization.

        Args:
            mac: Client MAC address.

        Returns:
            True if the unauthorize command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "unauthorize-guest", "mac": mac.lower()},
        )
        return True
