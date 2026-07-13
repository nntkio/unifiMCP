"""Static route CRUD (`rest/routing`)."""

from typing import Any


class _StaticRouteMixin:
    """Static route management."""

    async def get_static_routes(self) -> list[dict[str, Any]]:
        """Get all static routes.

        Returns:
            List of static route dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/routing")

    async def create_static_route(self, route: dict[str, Any]) -> dict[str, Any]:
        """Create a new static route.

        Args:
            route: Static route fields (e.g. `name`, `static-route_network`,
                `static-route_nexthop`, `static-route_type`).

        Returns:
            The created static route, as returned by the controller.
        """
        created = await self._request("POST", "/api/s/{site}/rest/routing", json=route)
        return created[0] if created else {}

    async def update_static_route(self, route_id: str, route: dict[str, Any]) -> bool:
        """Update an existing static route.

        The controller's REST endpoint replaces the whole route object on
        PUT, so callers should pass the full object with their changes applied.

        Args:
            route_id: Static route ID (`_id`).
            route: Full static route object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request("PUT", "/api/s/{site}/rest/routing/" + route_id, json=route)
        return True

    async def delete_static_route(self, route_id: str) -> bool:
        """Delete a static route.

        Args:
            route_id: Static route ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/routing/" + route_id)
        return True
