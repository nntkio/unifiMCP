"""WLAN rate profile CRUD (`v2/api/site/{site}/profiles/wlanrate`)."""

from typing import Any


class _WlanRateProfileMixin:
    """WLAN rate profile management."""

    async def get_wlan_rate_profiles(self) -> list[dict[str, Any]]:
        """Get all WLAN rate profiles.

        Returns:
            List of WLAN rate profile dictionaries.
        """
        return await self._request_v2("GET", "/profiles/wlanrate")

    async def create_wlan_rate_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a new WLAN rate profile.

        Args:
            profile: WLAN rate profile fields (e.g. `name`, and per-band
                minimum data rate and management frame rate settings).

        Returns:
            The created profile, as returned by the controller.
        """
        created = await self._request_v2("POST", "/profiles/wlanrate", json=profile)
        return created[0] if created else {}

    async def update_wlan_rate_profile(
        self, profile_id: str, profile: dict[str, Any]
    ) -> bool:
        """Update an existing WLAN rate profile.

        Args:
            profile_id: WLAN rate profile ID (`_id`).
            profile: Full profile object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/profiles/wlanrate/" + profile_id, json=profile)
        return True

    async def delete_wlan_rate_profile(self, profile_id: str) -> bool:
        """Delete a WLAN rate profile.

        Args:
            profile_id: WLAN rate profile ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/profiles/wlanrate/" + profile_id)
        return True
