"""Port profile CRUD (`rest/portconf`)."""

from typing import Any


class _PortProfileMixin:
    """Switch port profile management."""

    async def get_port_profiles(self) -> list[dict[str, Any]]:
        """Get all port profiles.

        Returns:
            List of port profile dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/portconf")

    async def create_port_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a new port profile.

        Args:
            profile: Port profile fields (e.g. `name`, `poe_mode`,
                `native_networkconf_id`, `tagged_networkconf_ids`).

        Returns:
            The created port profile, as returned by the controller.
        """
        created = await self._request(
            "POST", "/api/s/{site}/rest/portconf", json=profile
        )
        return created[0] if created else {}

    async def update_port_profile(
        self, profile_id: str, profile: dict[str, Any]
    ) -> bool:
        """Update an existing port profile.

        The controller's REST endpoint replaces the whole port profile object
        on PUT, so callers should pass the full object with their changes
        applied.

        Args:
            profile_id: Port profile ID (`_id`).
            profile: Full port profile object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request(
            "PUT", "/api/s/{site}/rest/portconf/" + profile_id, json=profile
        )
        return True

    async def delete_port_profile(self, profile_id: str) -> bool:
        """Delete a port profile.

        Args:
            profile_id: Port profile ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/portconf/" + profile_id)
        return True
