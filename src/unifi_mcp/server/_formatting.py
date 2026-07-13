"""Formatting helpers shared across multiple tool domains."""

from typing import Any


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def format_uptime(seconds: int) -> str:
    """Format uptime in seconds to human-readable format."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def _format_client_lines(
    client: dict[str, Any],
    bullet_indent: str = "",
    detail_indent: str = "  ",
    include_signal_uptime: bool = False,
) -> list[str]:
    """Format a single client's detail block, shared by client and activity views."""
    hostname = client.get("hostname") or client.get("name") or "Unknown"
    mac = client.get("mac", "Unknown")
    ip = client.get("ip", "N/A")
    conn_type = "Wired" if client.get("is_wired", False) else "Wireless"
    essid = client.get("essid", "")
    tx_bytes = client.get("tx_bytes", 0)
    rx_bytes = client.get("rx_bytes", 0)

    lines = [f"{bullet_indent}- {hostname}"]
    lines.append(f"{detail_indent}MAC: {mac}")
    lines.append(f"{detail_indent}IP: {ip}")
    lines.append(f"{detail_indent}Connection: {conn_type}")
    if essid:
        lines.append(f"{detail_indent}SSID: {essid}")
    if include_signal_uptime:
        signal = client.get("signal")
        uptime = client.get("uptime", 0)
        if signal is not None:
            lines.append(f"{detail_indent}Signal: {signal} dBm")
        if uptime > 0:
            lines.append(f"{detail_indent}Uptime: {format_uptime(uptime)}")
    lines.append(
        f"{detail_indent}Traffic: TX {format_bytes(tx_bytes)} / RX {format_bytes(rx_bytes)}"
    )
    lines.append("")
    return lines
