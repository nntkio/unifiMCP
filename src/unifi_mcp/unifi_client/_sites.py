"""Site inventory and health."""

from typing import Any


class _SiteMixin:
    """Site management: site inventory and health."""

    async def get_sites(self) -> list[dict[str, Any]]:
        """Get all sites.

        Returns:
            List of site dictionaries.
        """
        return await self._request("GET", "/api/self/sites")

    async def get_site_health(self) -> list[dict[str, Any]]:
        """Get site health statistics.

        Returns:
            List of health metric dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/health")
