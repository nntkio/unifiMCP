"""Tests for UniFi client."""

from unifi_mcp.unifi_client import UniFiClient


def test_client_initialization() -> None:
    """Test that the client initializes with default values."""
    client = UniFiClient(
        host="https://unifi.local",
        username="admin",
        password="password",
    )
    assert client.host == "https://unifi.local"
    assert client.username == "admin"
    assert client.site == "default"
    assert client.verify_ssl is True
