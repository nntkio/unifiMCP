"""UniFi API client for communicating with UniFi Controller."""

import asyncio
import os
from typing import Any

import httpx


class UniFiError(Exception):
    """Base exception for UniFi API errors."""

    pass


class UniFiAuthenticationError(UniFiError):
    """Raised when authentication fails."""

    pass


class UniFiConnectionError(UniFiError):
    """Raised when connection to controller fails."""

    pass


def _normalize_mac(mac: str) -> str:
    """Normalize a MAC address for case/format-insensitive comparison."""
    return mac.lower().replace(":", "").replace("-", "")


def _env_bool(name: str, default: str, override: bool | None) -> bool:
    """Resolve a boolean setting from an explicit override or an environment variable."""
    if override is not None:
        return override
    return os.environ.get(name, default).lower() == "true"


class UniFiClient:
    """Client for interacting with UniFi Controller API."""

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
        password: str | None = None,
        site: str | None = None,
        verify_ssl: bool | None = None,
        is_unifi_os: bool | None = None,
    ) -> None:
        """Initialize the UniFi client.

        Args:
            host: UniFi Controller host URL
            username: UniFi Controller username
            password: UniFi Controller password
            site: UniFi site name
            verify_ssl: Whether to verify SSL certificates
            is_unifi_os: Whether the controller is a UniFi OS device (UDM/UDM Pro)
        """
        self.host = host or os.environ.get("UNIFI_HOST", "")
        self.username = username or os.environ.get("UNIFI_USERNAME", "")
        self.password = password or os.environ.get("UNIFI_PASSWORD", "")
        self.site = site or os.environ.get("UNIFI_SITE", "default")
        self.verify_ssl = _env_bool("UNIFI_VERIFY_SSL", "true", verify_ssl)
        self.is_unifi_os = _env_bool("UNIFI_IS_UNIFI_OS", "false", is_unifi_os)
        self._client: httpx.AsyncClient | None = None
        self._logged_in: bool = False

    @property
    def _api_prefix(self) -> str:
        """Get the API prefix based on controller type."""
        return "/proxy/network" if self.is_unifi_os else ""

    def _api_url(self, endpoint: str) -> str:
        """Build the full API URL for an endpoint.

        Args:
            endpoint: The API endpoint (e.g., "/api/s/{site}/stat/device")

        Returns:
            The full URL with proper prefixing for UniFi OS if needed.
        """
        # Replace {site} placeholder with actual site
        endpoint = endpoint.replace("{site}", self.site)
        return f"{self._api_prefix}{endpoint}"

    def _v2_api_url(self, endpoint: str) -> str:
        """Build the full v2 API URL for an endpoint.

        The v2 API backs newer features (e.g. zone-based firewall policies)
        and lives under a different path prefix than the classic API.

        Args:
            endpoint: The v2 API endpoint, relative to the site
                (e.g. "/firewall-policies").

        Returns:
            The full URL with proper prefixing for UniFi OS if needed.
        """
        prefix = "/proxy/network" if self.is_unifi_os else ""
        return f"{prefix}/v2/api/site/{self.site}{endpoint}"

    async def connect(self) -> "UniFiClient":
        """Open the underlying HTTP client and log in."""
        self._client = httpx.AsyncClient(
            base_url=self.host,
            verify=self.verify_ssl,
            timeout=30.0,
        )
        await self.login()
        return self

    async def close(self) -> None:
        """Log out and close the underlying HTTP client."""
        if self._client:
            await self.logout()
            await self._client.aclose()

    async def __aenter__(self) -> "UniFiClient":
        """Enter async context."""
        return await self.connect()

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""
        await self.close()

    async def login(self) -> None:
        """Authenticate with the UniFi Controller."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        try:
            # A stale session cookie on the client causes UniFi OS consoles to
            # reject a fresh login with 403, so clear it before every attempt
            # (this matters for the re-login-on-expired-session retry path).
            self._client.cookies.clear()

            # UniFi OS uses a different login endpoint
            login_url = "/api/auth/login" if self.is_unifi_os else "/api/login"
            response = await self._client.post(
                login_url,
                json={"username": self.username, "password": self.password},
            )
            response.raise_for_status()
            self._logged_in = True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise UniFiAuthenticationError("Invalid credentials") from e
            raise UniFiError(f"Login failed: {e}") from e
        except httpx.ConnectError as e:
            raise UniFiConnectionError(f"Failed to connect to {self.host}") from e

    async def logout(self) -> None:
        """Logout from the UniFi Controller."""
        if not self._client or not self._logged_in:
            return
        try:
            await self._client.post("/api/logout")
            self._logged_in = False
        except httpx.HTTPError:
            pass  # Ignore logout errors

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | None = None,
        _retry_on_expired_session: bool = True,
    ) -> list[dict[str, Any]]:
        """Make an API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json: JSON body for POST/PUT requests
            _retry_on_expired_session: Re-login and retry once on a 401,
                since a long-lived client's session cookie can expire
                between requests.

        Returns:
            The data array from the response.

        Raises:
            UniFiError: If the request fails.
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        url = self._api_url(endpoint)
        try:
            response = await self._client.request(method, url, json=json)
            if response.status_code == 401 and _retry_on_expired_session:
                await self.login()
                return await self._request(
                    method, endpoint, json=json, _retry_on_expired_session=False
                )
            response.raise_for_status()
            data = response.json()

            # Check for API-level errors
            meta = data.get("meta", {})
            if meta.get("rc") == "error":
                raise UniFiError(meta.get("msg", "Unknown API error"))

            return data.get("data", [])
        except httpx.HTTPStatusError as e:
            raise UniFiError(f"Request failed: {e}") from e

    async def _request_v2(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | list[Any] | None = None,
        _retry_on_expired_session: bool = True,
    ) -> list[dict[str, Any]]:
        """Make a v2 API request.

        The v2 API (used by zone-based firewall policies, traffic rules,
        etc.) returns a bare JSON array/object instead of the classic API's
        `{"meta": ..., "data": [...]}` envelope, and reports errors via an
        `errorCode` field rather than `meta.rc == "error"`, so it needs its
        own response handling.

        Args:
            method: HTTP method
            endpoint: v2 API endpoint, relative to the site
            json: JSON body for POST/PUT requests
            _retry_on_expired_session: Re-login and retry once on a 401

        Returns:
            The response data, always as a list.

        Raises:
            UniFiError: If the request fails.
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        url = self._v2_api_url(endpoint)
        try:
            response = await self._client.request(method, url, json=json)
            if response.status_code == 401 and _retry_on_expired_session:
                await self.login()
                return await self._request_v2(
                    method, endpoint, json=json, _retry_on_expired_session=False
                )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and "errorCode" in data:
                raise UniFiError(data.get("message", "Unknown API error"))

            return data if isinstance(data, list) else [data]
        except httpx.HTTPStatusError as e:
            raise UniFiError(f"Request failed: {e}") from e

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

    # Client Management
    async def get_clients(self) -> list[dict[str, Any]]:
        """Get all currently connected clients.

        Returns:
            List of client dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/sta")

    async def get_all_clients(self) -> list[dict[str, Any]]:
        """Get all known clients (including offline).

        Returns:
            List of client dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/stat/alluser")

    async def block_client(self, mac: str) -> bool:
        """Block a client from the network.

        Args:
            mac: Client MAC address.

        Returns:
            True if block command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "block-sta", "mac": mac.lower()},
        )
        return True

    async def unblock_client(self, mac: str) -> bool:
        """Unblock a client from the network.

        Args:
            mac: Client MAC address.

        Returns:
            True if unblock command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "unblock-sta", "mac": mac.lower()},
        )
        return True

    async def disconnect_client(self, mac: str) -> bool:
        """Force disconnect a client.

        Args:
            mac: Client MAC address.

        Returns:
            True if disconnect command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "kick-sta", "mac": mac.lower()},
        )
        return True

    async def forget_client(self, mac: str) -> bool:
        """Remove a client from the controller's known-clients list.

        Args:
            mac: Client MAC address.

        Returns:
            True if the forget command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "forget-sta", "macs": [mac.lower()]},
        )
        return True

    async def authorize_guest(self, mac: str, minutes: int | None = None) -> bool:
        """Authorize a client through the guest portal.

        Args:
            mac: Client MAC address.
            minutes: Session length in minutes, if the authorization should
                expire automatically.

        Returns:
            True if the authorize command was sent successfully.
        """
        payload: dict[str, Any] = {"cmd": "authorize-guest", "mac": mac.lower()}
        if minutes is not None:
            payload["minutes"] = minutes
        await self._request("POST", "/api/s/{site}/cmd/stamgr", json=payload)
        return True

    async def unauthorize_guest(self, mac: str) -> bool:
        """Revoke a client's guest portal authorization.

        Args:
            mac: Client MAC address.

        Returns:
            True if the unauthorize command was sent successfully.
        """
        await self._request(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "unauthorize-guest", "mac": mac.lower()},
        )
        return True

    # Site Management
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

    # Network Configuration
    async def get_networks(self) -> list[dict[str, Any]]:
        """Get all network configurations.

        Returns:
            List of network configuration dictionaries.
        """
        return await self._request("GET", "/api/s/{site}/rest/networkconf")

    async def create_network(self, network: dict[str, Any]) -> dict[str, Any]:
        """Create a new network configuration (e.g. a VLAN).

        Args:
            network: Network fields (e.g. `name`, `purpose`, `vlan`,
                `ip_subnet`).

        Returns:
            The created network, as returned by the controller.
        """
        created = await self._request(
            "POST", "/api/s/{site}/rest/networkconf", json=network
        )
        return created[0] if created else {}

    async def update_network(self, network_id: str, network: dict[str, Any]) -> bool:
        """Update an existing network configuration.

        The controller's REST endpoint replaces the whole network object on
        PUT, so callers should pass the full object with their changes applied.

        Args:
            network_id: Network ID (`_id`).
            network: Full network object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request(
            "PUT", "/api/s/{site}/rest/networkconf/" + network_id, json=network
        )
        return True

    async def delete_network(self, network_id: str) -> bool:
        """Delete a network configuration.

        Args:
            network_id: Network ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/networkconf/" + network_id)
        return True

    # Firewall Rules (legacy)
    async def get_firewall_rules(self) -> list[dict[str, Any]]:
        """Get all legacy custom firewall rules.

        Consoles that have migrated to the newer zone-based firewall (see
        `get_firewall_policies`) reject this endpoint with
        `api.err.InvalidObject` instead of returning an empty list; that
        specific error is treated as "no legacy rules" rather than raised.

        Returns:
            List of firewall rule dictionaries.
        """
        try:
            return await self._request("GET", "/api/s/{site}/rest/firewallrule")
        except UniFiError as e:
            if "InvalidObject" in str(e):
                return []
            raise

    async def set_firewall_rule_enabled(self, rule_id: str, enabled: bool) -> bool:
        """Enable or disable a legacy firewall rule.

        The controller's REST endpoint replaces the whole rule object on PUT,
        so the current rule is fetched first and only the `enabled` field is
        changed before writing it back.

        Args:
            rule_id: Firewall rule ID (`_id`).
            enabled: Whether the rule should be active.

        Returns:
            True if the update was sent successfully.

        Raises:
            UniFiError: If no rule with that ID exists.
        """
        rules = await self.get_firewall_rules()
        rule = next((r for r in rules if r.get("_id") == rule_id), None)
        if rule is None:
            raise UniFiError(f"Firewall rule not found: {rule_id}")

        rule["enabled"] = enabled
        await self._request(
            "PUT", "/api/s/{site}/rest/firewallrule/" + rule_id, json=rule
        )
        return True

    async def create_firewall_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Create a new legacy firewall rule.

        Args:
            rule: Firewall rule fields (e.g. `name`, `ruleset`, `action`,
                `protocol`, `src_address`, `dst_address`, `enabled`).

        Returns:
            The created rule, as returned by the controller.
        """
        created = await self._request(
            "POST", "/api/s/{site}/rest/firewallrule", json=rule
        )
        return created[0] if created else {}

    async def delete_firewall_rule(self, rule_id: str) -> bool:
        """Delete a legacy firewall rule.

        Args:
            rule_id: Firewall rule ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request("DELETE", "/api/s/{site}/rest/firewallrule/" + rule_id)
        return True

    # Firewall Policies (zone-based firewall, UniFi Network 8.0+)
    async def get_firewall_policies(self) -> list[dict[str, Any]]:
        """Get all zone-based firewall policies.

        Includes both predefined (built-in) and custom policies.

        Returns:
            List of firewall policy dictionaries.
        """
        return await self._request_v2("GET", "/firewall-policies")

    async def set_firewall_policy_enabled(self, policy_id: str, enabled: bool) -> bool:
        """Enable or disable a zone-based firewall policy.

        Predefined (built-in) policies can't be modified by the controller,
        only ones you've created.

        Args:
            policy_id: Firewall policy ID (`_id`).
            enabled: Whether the policy should be active.

        Returns:
            True if the update was sent successfully.

        Raises:
            UniFiError: If no policy with that ID exists.
        """
        policies = await self.get_firewall_policies()
        policy = next((p for p in policies if p.get("_id") == policy_id), None)
        if policy is None:
            raise UniFiError(f"Firewall policy not found: {policy_id}")

        policy["enabled"] = enabled
        await self._request_v2("PUT", "/firewall-policies/" + policy_id, json=policy)
        return True

    async def create_firewall_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        """Create a new zone-based firewall policy.

        Args:
            policy: Firewall policy fields (e.g. `name`, `action`,
                `enabled`, `source`, `destination`).

        Returns:
            The created policy, as returned by the controller.
        """
        created = await self._request_v2("POST", "/firewall-policies", json=policy)
        return created[0] if created else {}

    async def _reject_predefined_policies(self, policy_ids: list[str]) -> None:
        """Raise if any of the given policy IDs is a predefined (built-in) policy.

        Predefined policies can't be modified or deleted by the controller,
        so this is checked client-side to surface a clear error instead of
        letting the request fail (or silently do nothing) downstream.
        """
        policies = await self.get_firewall_policies()
        predefined_ids = {p.get("_id") for p in policies if p.get("predefined", False)}
        blocked = predefined_ids & set(policy_ids)
        if blocked:
            raise UniFiError(
                "Predefined firewall policies can't be modified or deleted: "
                + ", ".join(sorted(blocked))
            )

    async def batch_update_firewall_policies(
        self, policies: list[dict[str, Any]]
    ) -> bool:
        """Bulk-update zone-based firewall policies.

        Args:
            policies: Full policy objects to update, each including `_id`.

        Returns:
            True if the update was sent successfully.

        Raises:
            UniFiError: If any policy is predefined.
        """
        await self._reject_predefined_policies([p.get("_id", "") for p in policies])
        await self._request_v2("PUT", "/firewall-policies/batch", json=policies)
        return True

    async def batch_delete_firewall_policies(self, policy_ids: list[str]) -> bool:
        """Bulk-delete zone-based firewall policies.

        Args:
            policy_ids: Policy IDs (`_id`) to delete.

        Returns:
            True if the delete was sent successfully.

        Raises:
            UniFiError: If any policy is predefined.
        """
        await self._reject_predefined_policies(policy_ids)
        await self._request_v2(
            "POST", "/firewall-policies/batch-delete", json=policy_ids
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
