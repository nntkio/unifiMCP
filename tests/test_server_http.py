"""Tests for the Streamable HTTP transport (server/_http.py)."""

from unittest.mock import AsyncMock

import pytest
from mcp.server import Server
from starlette.testclient import TestClient

from unifi_mcp.server._http import build_app
from unifi_mcp.tokens import TokenStore


@pytest.fixture
def mcp_server():
    return Server("test-server")


@pytest.fixture
def token_store(tmp_path):
    store = TokenStore(tmp_path / "tokens.db")
    owner_id = store.create_account("alice", "hunter2")
    return store, owner_id


class TestHealthz:
    def test_healthz_ok_without_authorization_header(self, mcp_server, token_store):
        store, _ = token_store
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.get("/healthz")

        assert response.status_code == 200

    def test_healthz_ok_even_with_tokens_present(self, mcp_server, token_store):
        store, owner_id = token_store
        store.create_token(owner_id, "test-token", None)
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.get("/healthz")

        assert response.status_code == 200


class TestBearerAuthMiddleware:
    def test_rejects_request_with_no_authorization_header(
        self, mcp_server, token_store
    ):
        store, _ = token_store
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.post("/mcp", json={})

        assert response.status_code == 401

    def test_rejects_unknown_token(self, mcp_server, token_store):
        store, _ = token_store
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.post(
                "/mcp", json={}, headers={"Authorization": "Bearer not-a-real-token"}
            )

        assert response.status_code == 401

    def test_rejects_revoked_token(self, mcp_server, token_store):
        store, owner_id = token_store
        raw_token = store.create_token(owner_id, "test-token", None)
        token_id = store.list_tokens(owner_id)[0].id
        store.revoke_token(token_id, requesting_owner_id=owner_id)
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.post(
                "/mcp", json={}, headers={"Authorization": f"Bearer {raw_token}"}
            )

        assert response.status_code == 401

    def test_allows_valid_token_past_auth_middleware(self, mcp_server, token_store):
        store, owner_id = token_store
        raw_token = store.create_token(owner_id, "test-token", None)
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.post(
                "/mcp",
                json={},
                headers={
                    "Authorization": f"Bearer {raw_token}",
                    "Accept": "application/json, text/event-stream",
                },
            )

        # Not 401 means the request passed auth and reached the MCP session
        # manager, which may itself reject this malformed test body with a
        # different 4xx — this test only asserts on the auth layer.
        assert response.status_code != 401

    def test_valid_token_completes_a_real_mcp_initialize(self, mcp_server, token_store):
        # The assertion above only rules out 401, which a missing route would
        # also satisfy. This asserts the request actually reaches the MCP
        # session manager and gets a protocol-level response back.
        store, owner_id = token_store
        raw_token = store.create_token(owner_id, "test-token", None)
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                },
                headers={
                    "Authorization": f"Bearer {raw_token}",
                    "Accept": "application/json, text/event-stream",
                },
            )

        assert response.status_code == 200
        assert '"serverInfo"' in response.text
