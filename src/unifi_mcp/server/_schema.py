"""Shared `ToolSpec` definition and property schema constants used across tool domains."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from unifi_mcp.unifi_client import UniFiClient


@dataclass(frozen=True)
class ToolSpec:
    """Declarative definition of an MCP tool: its schema and its handler."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[UniFiClient, dict[str, Any]], Awaitable[str]]


_MAC_PROPERTY = {
    "type": "string",
    "description": "MAC address of the target (e.g., '00:11:22:33:44:55')",
}
