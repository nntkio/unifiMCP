"""Legacy traffic rules (simplified allow/block-by-app or by-network shaping)."""

from typing import Any

from unifi_mcp.unifi_client._base import UniFiError


class _TrafficRuleMixin:
    """Traffic rule management: simplified allow/block traffic shaping rules."""

    async def get_traffic_rules(self) -> list[dict[str, Any]]:
        """Get all traffic rules.

        Returns:
            List of traffic rule dictionaries.
        """
        return await self._request_v2("GET", "/trafficrules")

    async def set_traffic_rule_enabled(self, rule_id: str, enabled: bool) -> bool:
        """Enable or disable a traffic rule.

        The controller's v2 endpoint replaces the whole rule object on PUT,
        so the current rule is fetched first and only the `enabled` field is
        changed before writing it back.

        Args:
            rule_id: Traffic rule ID (`_id`).
            enabled: Whether the rule should be active.

        Returns:
            True if the update was sent successfully.

        Raises:
            UniFiError: If no rule with that ID exists.
        """
        rules = await self.get_traffic_rules()
        rule = next((r for r in rules if r.get("_id") == rule_id), None)
        if rule is None:
            raise UniFiError(f"Traffic rule not found: {rule_id}")

        rule["enabled"] = enabled
        await self._request_v2("PUT", "/trafficrules/" + rule_id, json=rule)
        return True

    async def create_traffic_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Create a new traffic rule.

        Args:
            rule: Traffic rule fields (e.g. `description`, `action`,
                `enabled`, `matching_target`).

        Returns:
            The created rule, as returned by the controller.
        """
        created = await self._request_v2("POST", "/trafficrules", json=rule)
        return created[0] if created else {}

    async def update_traffic_rule(self, rule_id: str, rule: dict[str, Any]) -> bool:
        """Update an existing traffic rule.

        Unlike `set_traffic_rule_enabled`, this writes the given object as-is
        without first fetching and merging the existing rule.

        Args:
            rule_id: Traffic rule ID (`_id`).
            rule: Full traffic rule object to write.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/trafficrules/" + rule_id, json=rule)
        return True

    async def delete_traffic_rule(self, rule_id: str) -> bool:
        """Delete a traffic rule.

        Args:
            rule_id: Traffic rule ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/trafficrules/" + rule_id)
        return True
