"""Traffic routes: policy-based routing (`/v2/api/site/{site}/trafficroutes`)."""

from typing import Any


class _TrafficRouteMixin:
    """Traffic route management: policy-based routing over VPN/secondary WAN."""

    async def get_traffic_routes(self) -> list[dict[str, Any]]:
        """Get all traffic routes.

        Returns:
            List of traffic route dictionaries.
        """
        return await self._request_v2("GET", "/trafficroutes")

    async def create_traffic_route(self, route: dict[str, Any]) -> dict[str, Any]:
        """Create a new traffic route.

        Args:
            route: Traffic route fields (e.g. `description`, `enabled`,
                `matching_target`, `network_id`, `target_devices`).

        Returns:
            The created traffic route, as returned by the controller.
        """
        created = await self._request_v2("POST", "/trafficroutes", json=route)
        return created[0] if created else {}

    async def update_traffic_route(self, route_id: str, route: dict[str, Any]) -> bool:
        """Update an existing traffic route.

        The controller's v2 endpoint replaces the whole route object on PUT,
        so callers should pass the full object with their changes applied.

        Args:
            route_id: Traffic route ID (`_id`).
            route: Full traffic route object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/trafficroutes/" + route_id, json=route)
        return True

    async def delete_traffic_route(self, route_id: str) -> bool:
        """Delete a traffic route.

        Args:
            route_id: Traffic route ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/trafficroutes/" + route_id)
        return True
