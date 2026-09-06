"""Tests for the Streamable HTTP transport (server/_http.py)."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server import Server
from starlette.testclient import TestClient

from unifi_mcp import server as server_module
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


class TestMainTransportDispatch:
    def teardown_method(self) -> None:
        os.environ.pop("MCP_TRANSPORT", None)

    def test_main_dispatches_to_http_when_configured(self):
        os.environ["MCP_TRANSPORT"] = "http"

        with patch("unifi_mcp.server._http.run_http") as mock_run_http:
            server_module.main()

        mock_run_http.assert_called_once_with(
            server_module.server, server_module._close_client
        )

    def test_main_dispatches_to_stdio_by_default(self):
        os.environ.pop("MCP_TRANSPORT", None)

        with patch("unifi_mcp.server.asyncio.run") as mock_asyncio_run:
            server_module.main()

        mock_asyncio_run.assert_called_once()


class TestMcpPathWithoutTrailingSlash:
    def test_bare_mcp_path_is_served_not_redirected(self, mcp_server, token_store):
        # Starlette's Mount("/mcp") only matches "/mcp/...", so a bare
        # POST /mcp would 307 to /mcp/. TestClient follows redirects by
        # default and hides that, so this asserts with following disabled:
        # a client that doesn't follow redirects on POST must still work.
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
                follow_redirects=False,
            )

        assert response.status_code == 200
        assert '"serverInfo"' in response.text
