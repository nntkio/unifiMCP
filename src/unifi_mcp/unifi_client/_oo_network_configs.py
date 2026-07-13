"""Object-oriented network configuration CRUD (`v2/api/site/{site}/object-oriented-network-config(s)`)."""

from typing import Any


class _OONetworkConfigMixin:
    """Object-oriented network configuration management.

    This is the newer object-oriented network config model (as opposed to
    the classic `rest/networkconf` model in `_networks.py`).
    """

    async def get_oo_network_configs(self) -> list[dict[str, Any]]:
        """Get all object-oriented network configurations.

        Note: the controller's listing endpoint is plural
        (`object-oriented-network-configs`) while the create/update/delete
        endpoints are singular (`object-oriented-network-config`). This is
        not a typo; it matches the controller's actual routes.

        Returns:
            List of object-oriented network configuration dictionaries.
        """
        return await self._request_v2("GET", "/object-oriented-network-configs")

    async def create_oo_network_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Create a new object-oriented network configuration.

        Args:
            config: Object-oriented network config fields (e.g. `name`,
                `purpose`, `vlan`, `ip_subnet`).

        Returns:
            The created config, as returned by the controller.
        """
        created = await self._request_v2(
            "POST", "/object-oriented-network-config", json=config
        )
        return created[0] if created else {}

    async def update_oo_network_config(
        self, config_id: str, config: dict[str, Any]
    ) -> bool:
        """Update an existing object-oriented network configuration.

        Args:
            config_id: Object-oriented network config ID (`_id`).
            config: Full config object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2(
            "PUT", "/object-oriented-network-config/" + config_id, json=config
        )
        return True

    async def delete_oo_network_config(self, config_id: str) -> bool:
        """Delete an object-oriented network configuration.

        Args:
            config_id: Object-oriented network config ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/object-oriented-network-config/" + config_id)
        return True
