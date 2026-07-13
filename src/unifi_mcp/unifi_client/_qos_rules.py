"""QoS (Quality of Service) rules."""

from typing import Any


class _QosRuleMixin:
    """QoS rule management."""

    async def get_qos_rules(self) -> list[dict[str, Any]]:
        """Get all QoS rules.

        Returns:
            List of QoS rule dictionaries.
        """
        return await self._request_v2("GET", "/qos-rules")

    async def create_qos_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Create a new QoS rule.

        Args:
            rule: QoS rule fields (e.g. `name`, `enabled`, `bandwidth_limit`).

        Returns:
            The created rule, as returned by the controller.
        """
        created = await self._request_v2("POST", "/qos-rules", json=rule)
        return created[0] if created else {}

    async def update_qos_rule(self, rule_id: str, rule: dict[str, Any]) -> bool:
        """Update an existing QoS rule.

        Args:
            rule_id: QoS rule ID (`_id`).
            rule: Full QoS rule object to write back.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/qos-rules/" + rule_id, json=rule)
        return True

    async def delete_qos_rule(self, rule_id: str) -> bool:
        """Delete a QoS rule.

        Args:
            rule_id: QoS rule ID (`_id`).

        Returns:
            True if the delete command was sent successfully.
        """
        await self._request_v2("DELETE", "/qos-rules/" + rule_id)
        return True

    async def batch_update_qos_rules(self, rules: list[dict[str, Any]]) -> bool:
        """Bulk-update QoS rules.

        The exact semantics of this batch endpoint (whether it accepts
        partial updates, how ordering is handled, etc.) are inferred from
        the analogous `/firewall-policies/batch` endpoint and have not been
        independently verified against a live controller.

        Args:
            rules: Full QoS rule objects to update, each including `_id`.

        Returns:
            True if the update was sent successfully.
        """
        await self._request_v2("PUT", "/qos-rules/batch", json=rules)
        return True
