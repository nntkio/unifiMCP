"""WLAN (Wi-Fi network) configuration CRUD (`rest/wlanconf`)."""

from typing import Any


class _WlanMixin:
    """WLAN configuration management."""

    async def get_wlans(self) -> list[dict[str, Any]]:
        """Get all WLAN (Wi-Fi network) configurations.

        Returns:
            List of WLAN configuration dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/wlanconf")

    async def create_wlan(self, wlan: dict[str, Any]) -> dict[str, Any]:
        """Create a new WLAN (Wi-Fi network) configuration.

        Args:
            wlan: WLAN fields (e.g. `name`, `security`, `x_passphrase`,
                `vlan`, `is_guest`).

        Returns:
            The created WLAN, as returned by the controller.
        """
        created = await self._request("POST", "/api/s/{site}/rest/wlanconf", json=wlan)
        return created[0] if created else {}

    async def update_wlan(self, wlan_id: str, wlan: dict[str, Any]) -> bool:
        """Update an existing WLAN (Wi-Fi network) configuration.

        The controller's REST endpoint replaces the whole WLAN object on
        PUT, so callers should pass the full object with their changes applied.

        Args:
            wlan_id: WLAN ID (`_id`).
            wlan: Full WLAN object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request("PUT", "/api/s/{site}/rest/wlanconf/" + wlan_id, json=wlan)
        return True

    async def delete_wlan(self, wlan_id: str) -> bool:
        """Delete a WLAN (Wi-Fi network) configuration.

        Args:
            wlan_id: WLAN ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/wlanconf/" + wlan_id)
        return True
