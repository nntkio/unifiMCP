"""Port forwarding rule CRUD (`rest/portforward`)."""

from typing import Any


class _PortForwardingMixin:
    """Port forwarding rule management."""

    async def get_port_forwards(self) -> list[dict[str, Any]]:
        """Get all port forwarding rules.

        Returns:
            List of port forwarding rule dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/portforward")

    async def create_port_forward(self, forward: dict[str, Any]) -> dict[str, Any]:
        """Create a new port forwarding rule.

        Args:
            forward: Port forward fields (e.g. `name`, `fwd`, `dst_port`,
                `src`, `proto`).

        Returns:
            The created port forwarding rule, as returned by the controller.
        """
        created = await self._request(
            "POST", "/api/s/{site}/rest/portforward", json=forward
        )
        return created[0] if created else {}

    async def update_port_forward(
        self, forward_id: str, forward: dict[str, Any]
    ) -> bool:
        """Update an existing port forwarding rule.

        The controller's REST endpoint replaces the whole port forward object
        on PUT, so callers should pass the full object with their changes
        applied.

        Args:
            forward_id: Port forward ID (`_id`).
            forward: Full port forward object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request(
            "PUT", "/api/s/{site}/rest/portforward/" + forward_id, json=forward
        )
        return True

    async def delete_port_forward(self, forward_id: str) -> bool:
        """Delete a port forwarding rule.

        Args:
            forward_id: Port forward ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/portforward/" + forward_id)
        return True
