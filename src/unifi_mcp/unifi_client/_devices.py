"""Device inventory, `cmd/devmgr` lifecycle commands, and per-device activity."""

import asyncio
from typing import Any

from unifi_mcp.unifi_client._base import _normalize_mac


class _DeviceMixin:
    """Device management: inventory, lifecycle commands, and activity."""

    # Device Management
    async def get_devices(self) -> list[dict[str, Any]]:
        """Get all network devices.

        Returns:
            List of device dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/device")

    async def get_device(self, mac: str) -> dict[str, Any] | None:
        """Get a specific device by MAC address.

        Falls back to scanning the full device list if the single-device
        endpoint returns nothing, so callers can rely on a single lookup.

        Args:
            mac: Device MAC address.

        Returns:
            Device dictionary or None if not found.
        """
        devices = await self._request("GET", "/api/s/{site}/stat/device/" + mac)
        if devices:
            return devices[0]

        mac_normalized = _normalize_mac(mac)
        for device in await self.get_devices():
            if _normalize_mac(device.get("mac", "")) == mac_normalized:
                return device
        return None

    async def restart_device(self, mac: str) -> bool:
        """Restart a network device.

        Args:
            mac: Device MAC address.

        Returns:
            True if restart command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "restart", "mac": mac.lower()},
        )
        return True

    async def adopt_device(self, mac: str) -> bool:
        """Adopt a pending device onto the controller.

        Args:
            mac: Device MAC address.

        Returns:
            True if the adopt command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "adopt", "mac": mac.lower()},
        )
        return True

    async def force_provision_device(self, mac: str) -> bool:
        """Force a configuration push to a device.

        Args:
            mac: Device MAC address.

        Returns:
            True if the force-provision command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "force-provision", "mac": mac.lower()},
        )
        return True

    async def upgrade_device(self, mac: str) -> bool:
        """Trigger a firmware upgrade on a device.

        Args:
            mac: Device MAC address.

        Returns:
            True if the upgrade command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "upgrade", "mac": mac.lower()},
        )
        return True

    async def power_cycle_port(self, mac: str, port_idx: int) -> bool:
        """Power-cycle a PoE port on a switch.

        Args:
            mac: Switch MAC address.
            port_idx: Index of the port to power-cycle.

        Returns:
            True if the power-cycle command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "power-cycle", "mac": mac.lower(), "port_idx": port_idx},
        )
        return True

    async def set_device_locate(self, mac: str) -> bool:
        """Flash a device's LED to help locate it physically.

        Args:
            mac: Device MAC address.

        Returns:
            True if the set-locate command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "set-locate", "mac": mac.lower()},
        )
        return True

    async def unset_device_locate(self, mac: str) -> bool:
        """Stop flashing a device's locate LED.

        Args:
            mac: Device MAC address.

        Returns:
            True if the unset-locate command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "unset-locate", "mac": mac.lower()},
        )
        return True

    # Device Activity
    async def get_device_clients(self, device_mac: str) -> list[dict[str, Any]]:
        """Get clients connected to a specific device (AP or switch).

        Args:
            device_mac: MAC address of the device.

        Returns:
            List of client dictionaries connected to this device.
        """
        all_clients = await self.get_clients()
        device_mac_normalized = _normalize_mac(device_mac)

        connected_clients = []
        for client in all_clients:
            # Check if client is connected to this AP (wireless) or switch (wired)
            ap_mac = _normalize_mac(client.get("ap_mac", ""))
            sw_mac = _normalize_mac(client.get("sw_mac", ""))

            if device_mac_normalized in (ap_mac, sw_mac):
                connected_clients.append(client)

        return connected_clients

    async def get_device_activity(self, device_mac: str) -> dict[str, Any]:
        """Get activity summary for a specific device.

        This includes the device info, connected clients, and their traffic.

        Args:
            device_mac: MAC address of the device.

        Returns:
            Dictionary with device info and connected clients.
        """
        device, clients = await asyncio.gather(
            self.get_device(device_mac), self.get_device_clients(device_mac)
        )

        total_tx = sum(c.get("tx_bytes", 0) for c in clients)
        total_rx = sum(c.get("rx_bytes", 0) for c in clients)

        return {
            "device": device,
            "clients": clients,
            "client_count": len(clients),
            "total_tx_bytes": total_tx,
            "total_rx_bytes": total_rx,
        }
