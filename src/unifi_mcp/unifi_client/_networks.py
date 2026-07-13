"""Network configuration CRUD (`rest/networkconf`)."""

from typing import Any


class _NetworkMixin:
    """Network configuration management."""

    async def get_networks(self) -> list[dict[str, Any]]:
        """Get all network configurations.

        Returns:
            List of network configuration dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/networkconf")

    async def create_network(self, network: dict[str, Any]) -> dict[str, Any]:
        """Create a new network configuration (e.g. a VLAN).

        Args:
            network: Network fields (e.g. `name`, `purpose`, `vlan`,
                `ip_subnet`).

        Returns:
            The created network, as returned by the controller.
        """
        created = await self._request(
            "POST", "/api/s/{site}/rest/networkconf", json=network
        )
        return created[0] if created else {}

    async def update_network(self, network_id: str, network: dict[str, Any]) -> bool:
        """Update an existing network configuration.

        The controller's REST endpoint replaces the whole network object on
        PUT, so callers should pass the full object with their changes applied.

        Args:
            network_id: Network ID (`_id`).
            network: Full network object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request(
            "PUT", "/api/s/{site}/rest/networkconf/" + network_id, json=network
        )
        return True

    async def delete_network(self, network_id: str) -> bool:
        """Delete a network configuration.

        Args:
            network_id: Network ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/networkconf/" + network_id)
        return True
