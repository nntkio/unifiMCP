"""Legacy firewall rules and zone-based firewall policies."""

from typing import Any

from unifi_mcp.unifi_client._base import UniFiError


class _FirewallMixin:
    """Firewall management: legacy rules and zone-based policies."""

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
