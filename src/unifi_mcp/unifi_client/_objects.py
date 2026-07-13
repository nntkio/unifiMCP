"""Network objects (address/port groups) CRUD (`v2/api/site/{site}/objects`)."""

from typing import Any


class _NetworkObjectMixin:
    """Network object management.

    Network objects are the address/port groups used by the newer
    object-oriented network config model, distinct from legacy firewall
    groups.
    """

    async def get_objects(self) -> list[dict[str, Any]]:
        """Get all network objects.

        Returns:
            List of network object dictionaries.
        """
        return await self._request_v2("GET", "/objects")

    async def create_object(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Create a new network object.

        Args:
            obj: Network object fields (e.g. `name`, `object_type`).

        Returns:
            The created network object, as returned by the controller.
        """
        created = await self._request_v2("POST", "/objects", json=obj)
        return created[0] if created else {}

    async def update_object(self, object_id: str, obj: dict[str, Any]) -> bool:
        """Update an existing network object.

        Args:
            object_id: Network object ID (`_id`).
            obj: Full network object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/objects/" + object_id, json=obj)
        return True

    async def delete_object(self, object_id: str) -> bool:
        """Delete a network object.

        Args:
            object_id: Network object ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/objects/" + object_id)
        return True
