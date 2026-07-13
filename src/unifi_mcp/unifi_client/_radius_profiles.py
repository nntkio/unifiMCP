"""RADIUS profile CRUD (`rest/radiusprofile`)."""

from typing import Any


class _RadiusProfileMixin:
    """RADIUS profile management."""

    async def get_radius_profiles(self) -> list[dict[str, Any]]:
        """Get all RADIUS profiles.

        Returns:
            List of RADIUS profile dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/radiusprofile")

    async def create_radius_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a new RADIUS profile.

        Args:
            profile: RADIUS profile fields (e.g. `name`, `x_auth_server`,
                `x_auth_port`, `x_secret`).

        Returns:
            The created RADIUS profile, as returned by the controller.
        """
        created = await self._request(
            "POST", "/api/s/{site}/rest/radiusprofile", json=profile
        )
        return created[0] if created else {}

    async def update_radius_profile(
        self, profile_id: str, profile: dict[str, Any]
    ) -> bool:
        """Update an existing RADIUS profile.

        The controller's REST endpoint replaces the whole profile object on
        PUT, so callers should pass the full object with their changes applied.

        Args:
            profile_id: RADIUS profile ID (`_id`).
            profile: Full RADIUS profile object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request(
            "PUT", "/api/s/{site}/rest/radiusprofile/" + profile_id, json=profile
        )
        return True

    async def delete_radius_profile(self, profile_id: str) -> bool:
        """Delete a RADIUS profile.

        Args:
            profile_id: RADIUS profile ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/radiusprofile/" + profile_id)
        return True
