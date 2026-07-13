"""WAN SLA profile CRUD (`v2/api/site/{site}/profiles/wansla`)."""

from typing import Any


class _WanSlaProfileMixin:
    """WAN SLA profile management for multi-WAN failover/load-balancing."""

    async def get_wan_sla_profiles(self) -> list[dict[str, Any]]:
        """Get all WAN SLA profiles.

        Returns:
            List of WAN SLA profile dictionaries.
        """
        return await self._request_v2("GET", "/profiles/wansla")

    async def create_wan_sla_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a new WAN SLA profile.

        Args:
            profile: WAN SLA profile fields (e.g. `name`, `type`,
                `wan_networks_group`).

        Returns:
            The created profile, as returned by the controller.
        """
        created = await self._request_v2("POST", "/profiles/wansla", json=profile)
        return created[0] if created else {}

    async def update_wan_sla_profile(
        self, profile_id: str, profile: dict[str, Any]
    ) -> bool:
        """Update an existing WAN SLA profile.

        Args:
            profile_id: WAN SLA profile ID (`_id`).
            profile: Full profile object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/profiles/wansla/" + profile_id, json=profile)
        return True

    async def delete_wan_sla_profile(self, profile_id: str) -> bool:
        """Delete a WAN SLA profile.

        Args:
            profile_id: WAN SLA profile ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/profiles/wansla/" + profile_id)
        return True
