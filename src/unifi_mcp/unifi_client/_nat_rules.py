"""NAT rules CRUD (`v2/api/site/{site}/nat`)."""

from typing import Any


class _NatRuleMixin:
    """NAT rule management."""

    async def get_nat_rules(self) -> list[dict[str, Any]]:
        """Get all NAT rules.

        Returns:
            List of NAT rule dictionaries.
        """
        return await self._request_v2("GET", "/nat")

    async def create_nat_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Create a new NAT rule.

        Args:
            rule: NAT rule fields (e.g. `name`, `enabled`, `type`,
                `source`, `destination`).

        Returns:
            The created rule, as returned by the controller.
        """
        created = await self._request_v2("POST", "/nat", json=rule)
        return created[0] if created else {}

    async def update_nat_rule(self, rule_id: str, rule: dict[str, Any]) -> bool:
        """Update an existing NAT rule.

        Args:
            rule_id: NAT rule ID (`_id`).
            rule: Full rule object with updated fields.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/nat/" + rule_id, json=rule)
        return True

    async def delete_nat_rule(self, rule_id: str) -> bool:
        """Delete a NAT rule.

        Args:
            rule_id: NAT rule ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/nat/" + rule_id)
        return True
