"""Firewall group CRUD (`rest/firewallgroup`)."""

from typing import Any


class _FirewallGroupMixin:
    """Firewall group management."""

    async def get_firewall_groups(self) -> list[dict[str, Any]]:
        """Get all firewall groups.

        Returns:
            List of firewall group dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/firewallgroup")

    async def create_firewall_group(self, group: dict[str, Any]) -> dict[str, Any]:
        """Create a new firewall group.

        Args:
            group: Firewall group fields (e.g. `name`, `group_type`,
                `group_members`).

        Returns:
            The created firewall group, as returned by the controller.
        """
        created = await self._request(
            "POST", "/api/s/{site}/rest/firewallgroup", json=group
        )
        return created[0] if created else {}

    async def update_firewall_group(self, group_id: str, group: dict[str, Any]) -> bool:
        """Update an existing firewall group.

        The controller's REST endpoint replaces the whole group object on
        PUT, so callers should pass the full object with their changes
        applied.

        Args:
            group_id: Firewall group ID (`_id`).
            group: Full group object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request(
            "PUT", "/api/s/{site}/rest/firewallgroup/" + group_id, json=group
        )
        return True

    async def delete_firewall_group(self, group_id: str) -> bool:
        """Delete a firewall group.

        Args:
            group_id: Firewall group ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/firewallgroup/" + group_id)
        return True
