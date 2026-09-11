"""Tests for the OAuth authorization server (server/_oauth.py)."""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from mcp.server import Server
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.testclient import TestClient

from unifi_mcp.server._http import build_app, normalize_public_url
from unifi_mcp.server._oauth import (
    TokenStoreOAuthProvider,
    build_login_routes,
    client_label,
)
from unifi_mcp.tokens import TokenStore

REDIRECT_URI = "https://claude.ai/api/mcp/auth_callback"
PUBLIC_URL = "http://localhost"


def pkce_pair() -> tuple[str, str]:
    """Return a (code_verifier, code_challenge) S256 pair."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


@pytest.fixture
def store(tmp_path):
    return TokenStore(tmp_path / "tokens.db")


@pytest.fixture
def oauth_app(store):
    return build_app(Server("test-server"), store, AsyncMock(), public_url=PUBLIC_URL)


@pytest.fixture
def http(oauth_app):
    with TestClient(oauth_app, base_url=PUBLIC_URL) as client:
        yield client


@pytest.fixture
def provider(store):
    return TokenStoreOAuthProvider(store)


@pytest.fixture
def login_client(store):
    app = Starlette(routes=build_login_routes(store))
    return TestClient(app, base_url="http://localhost")


def _pending(store, state="state-123"):
    store.save_oauth_client(
        "client-1",
        OAuthClientInformationFull(
            client_id="client-1",
            client_name="Claude",
            redirect_uris=[REDIRECT_URI],
        ).model_dump_json(),
    )
    return store.create_authorization(
        client_id="client-1",
        redirect_uri=REDIRECT_URI,
        redirect_uri_explicit=True,
        code_challenge="challenge",
        state=state,
        scope="",
        resource=None,
        expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    )


@pytest.fixture
def client():
    return OAuthClientInformationFull(
        client_id="client-1",
        client_name="Claude",
        redirect_uris=[REDIRECT_URI],
        token_endpoint_auth_method="none",
    )


async def _authorize(provider, client, state="state-123"):
    """Register the client, start an authorisation, return its txn id."""
    _, challenge = pkce_pair()
    await provider.register_client(client)
    url = await provider.authorize(
        client,
        AuthorizationParams(
            state=state,
            scopes=None,
            code_challenge=challenge,
            redirect_uri=AnyUrl(REDIRECT_URI),
            redirect_uri_provided_explicitly=True,
            resource="https://example.test/mcp",
        ),
    )
    return url.split("txn=", 1)[1]


async def _issue(provider, client, store, username="alice"):
    """Run a whole sign-in at the provider level and return the OAuthToken."""
    owner_id = store.create_account(username, "hunter2")
    txn_id = await _authorize(provider, client)
    code = store.complete_authorization(txn_id, owner_id)
    auth_code = await provider.load_authorization_code(client, code)
    return await provider.exchange_authorization_code(client, auth_code)


class TestClientLabel:
    def test_uses_client_name(self, client):
        assert client_label(client) == "OAuth · Claude"

    def test_falls_back_to_client_id_prefix(self):
        anonymous = OAuthClientInformationFull(
            client_id="abcdefghijkl", redirect_uris=[REDIRECT_URI]
        )

        assert client_label(anonymous) == "OAuth · abcdefgh"


class TestClientRegistry:
    async def test_get_unknown_client_returns_none(self, provider):
        assert await provider.get_client("nope") is None

    async def test_register_then_get_round_trips(self, provider, client):
        await provider.register_client(client)

        loaded = await provider.get_client("client-1")

        assert loaded.client_name == "Claude"
        assert str(loaded.redirect_uris[0]) == REDIRECT_URI


class TestAuthorizeAndExchange:
    async def test_authorize_returns_login_url(self, provider, client):
        await provider.register_client(client)
        _, challenge = pkce_pair()

        url = await provider.authorize(
            client,
            AuthorizationParams(
                state=None,
                scopes=None,
                code_challenge=challenge,
                redirect_uri=AnyUrl(REDIRECT_URI),
                redirect_uri_provided_explicitly=True,
            ),
        )

        assert url.startswith("/oauth/login?txn=")

    async def test_load_authorization_code_after_consumption_returns_none(
        self, provider, client, store
    ):
        owner_id = store.create_account("alice", "hunter2")
        txn_id = await _authorize(provider, client)
        code = store.complete_authorization(txn_id, owner_id)
        store.consume_authorization_code(code)

        assert await provider.load_authorization_code(client, code) is None

    async def test_exchange_issues_token_row_and_refresh(self, provider, client, store):
        owner_id = store.create_account("alice", "hunter2")
        txn_id = await _authorize(provider, client)
        code = store.complete_authorization(txn_id, owner_id)

        auth_code = await provider.load_authorization_code(client, code)
        tokens = await provider.exchange_authorization_code(client, auth_code)

        record = store.resolve(tokens.access_token)
        assert record.owner_id == owner_id
        assert record.label == "OAuth · Claude"
        assert tokens.refresh_token is not None
        assert tokens.expires_in == 3600

    async def test_code_from_another_client_is_rejected(self, provider, client, store):
        owner_id = store.create_account("alice", "hunter2")
        txn_id = await _authorize(provider, client)
        code = store.complete_authorization(txn_id, owner_id)
        other = OAuthClientInformationFull(
            client_id="client-2", redirect_uris=[REDIRECT_URI]
        )

        assert await provider.load_authorization_code(other, code) is None


class TestRefresh:
    async def test_refresh_rotates_access_token_in_place(self, provider, client, store):
        tokens = await _issue(provider, client, store)
        token_id = store.resolve(tokens.access_token).id

        loaded = await provider.load_refresh_token(client, tokens.refresh_token)
        refreshed = await provider.exchange_refresh_token(client, loaded, [])

        assert store.resolve(tokens.access_token) is None
        assert store.resolve(refreshed.access_token).id == token_id

    async def test_refresh_token_rotates(self, provider, client, store):
        tokens = await _issue(provider, client, store)

        loaded = await provider.load_refresh_token(client, tokens.refresh_token)
        refreshed = await provider.exchange_refresh_token(client, loaded, [])

        assert refreshed.refresh_token != tokens.refresh_token
        assert await provider.load_refresh_token(client, tokens.refresh_token) is None

    async def test_load_refresh_token_none_after_revocation(
        self, provider, client, store
    ):
        tokens = await _issue(provider, client, store)
        token_id = store.resolve(tokens.access_token).id
        store.revoke_token(token_id, requesting_owner_id=None)

        assert await provider.load_refresh_token(client, tokens.refresh_token) is None

    async def test_load_refresh_token_carries_grant_expiry(
        self, provider, client, store
    ):
        tokens = await _issue(provider, client, store)

        loaded = await provider.load_refresh_token(client, tokens.refresh_token)

        expected = (datetime.now(UTC) + timedelta(days=30)).timestamp()
        assert abs(loaded.expires_at - expected) < 60


class TestAccessTokensAndRevocation:
    async def test_load_access_token_for_static_token_returns_none(
        self, provider, store
    ):
        owner_id = store.create_account("bob", "hunter2")
        raw = store.create_token(owner_id, "laptop", None)

        assert await provider.load_access_token(raw) is None

    async def test_revoke_access_token_kills_the_grant(self, provider, client, store):
        tokens = await _issue(provider, client, store)

        access = await provider.load_access_token(tokens.access_token)
        await provider.revoke_token(access)

        assert store.resolve(tokens.access_token) is None
        assert store.get_refresh_token(tokens.refresh_token) is None

    async def test_revoke_refresh_token_kills_the_access_token(
        self, provider, client, store
    ):
        tokens = await _issue(provider, client, store)

        loaded = await provider.load_refresh_token(client, tokens.refresh_token)
        await provider.revoke_token(loaded)

        assert store.resolve(tokens.access_token) is None


class TestLoginPage:
    def test_get_renders_form_with_client_and_redirect_host(self, login_client, store):
        txn_id = _pending(store)

        response = login_client.get("/oauth/login", params={"txn": txn_id})

        assert response.status_code == 200
        assert "Claude" in response.text
        assert "claude.ai" in response.text
        assert txn_id in response.text

    def test_get_unknown_txn_is_400(self, login_client):
        response = login_client.get("/oauth/login", params={"txn": "nope"})

        assert response.status_code == 400

    def test_get_without_txn_is_400(self, login_client):
        assert login_client.get("/oauth/login").status_code == 400

    def test_post_valid_credentials_redirects_with_code_and_state(
        self, login_client, store
    ):
        store.create_account("alice", "hunter2")
        txn_id = _pending(store)

        response = login_client.post(
            "/oauth/login",
            data={"txn": txn_id, "username": "alice", "password": "hunter2"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        query = parse_qs(urlparse(response.headers["location"]).query)
        assert query["state"] == ["state-123"]
        assert store.consume_authorization_code(query["code"][0]) is not None

    def test_post_wrong_password_rerenders_with_error(self, login_client, store):
        store.create_account("alice", "hunter2")
        txn_id = _pending(store)

        response = login_client.post(
            "/oauth/login",
            data={"txn": txn_id, "username": "alice", "password": "wrong"},
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert "Invalid username or password" in response.text

    def test_post_unknown_user_rerenders_with_same_error(self, login_client, store):
        txn_id = _pending(store)

        response = login_client.post(
            "/oauth/login",
            data={"txn": txn_id, "username": "nobody", "password": "hunter2"},
            follow_redirects=False,
        )

        assert "Invalid username or password" in response.text

    def test_fifth_failure_burns_the_link(self, login_client, store):
        store.create_account("alice", "hunter2")
        txn_id = _pending(store)

        for _ in range(4):
            login_client.post(
                "/oauth/login",
                data={"txn": txn_id, "username": "alice", "password": "wrong"},
            )
        response = login_client.post(
            "/oauth/login",
            data={"txn": txn_id, "username": "alice", "password": "wrong"},
        )

        assert response.status_code == 400
        assert store.get_authorization(txn_id) is None

    def test_cancel_redirects_with_access_denied(self, login_client, store):
        txn_id = _pending(store)

        response = login_client.post(
            "/oauth/login",
            data={"txn": txn_id, "cancel": "1"},
            follow_redirects=False,
        )

        query = parse_qs(urlparse(response.headers["location"]).query)
        assert query["error"] == ["access_denied"]
        assert query["state"] == ["state-123"]
        assert store.get_authorization(txn_id) is None

    def test_post_unknown_txn_is_400(self, login_client):
        response = login_client.post(
            "/oauth/login",
            data={"txn": "nope", "username": "alice", "password": "hunter2"},
        )

        assert response.status_code == 400


class TestNormalizePublicUrl:
    def test_strips_trailing_slash(self):
        assert normalize_public_url("https://a.test/") == "https://a.test"

    def test_accepts_https_origin(self):
        assert normalize_public_url("https://a.test") == "https://a.test"

    @pytest.mark.parametrize(
        "value",
        ["", "a.test", "ftp://a.test", "https://a.test/mcp", "https://a.test?x=1"],
    )
    def test_rejects_invalid(self, value):
        with pytest.raises(ValueError):
            normalize_public_url(value)


class TestMetadata:
    def test_protected_resource_metadata(self, http):
        body = http.get("/.well-known/oauth-protected-resource/mcp").json()

        assert body["resource"] == f"{PUBLIC_URL}/mcp"
        assert body["authorization_servers"] == [f"{PUBLIC_URL}/"]

    def test_protected_resource_alias_matches(self, http):
        alias = http.get("/.well-known/oauth-protected-resource").json()
        canonical = http.get("/.well-known/oauth-protected-resource/mcp").json()

        assert alias == canonical

    def test_authorization_server_metadata(self, http):
        body = http.get("/.well-known/oauth-authorization-server").json()

        assert body["code_challenge_methods_supported"] == ["S256"]
        assert body["registration_endpoint"] == f"{PUBLIC_URL}/register"
        assert "none" in body["token_endpoint_auth_methods_supported"]


class TestUnauthenticatedChallenge:
    def test_mcp_401_points_at_resource_metadata(self, http):
        response = http.post("/mcp", json={})

        challenge = response.headers["www-authenticate"]
        assert response.status_code == 401
        assert 'resource_metadata="' in challenge
        assert "/.well-known/oauth-protected-resource/mcp" in challenge

    def test_invalid_token_challenge_names_the_error(self, http):
        response = http.post("/mcp", json={}, headers={"Authorization": "Bearer nope"})

        assert 'error="invalid_token"' in response.headers["www-authenticate"]

    def test_oauth_routes_do_not_require_a_bearer_token(self, http):
        assert http.get("/.well-known/oauth-authorization-server").status_code == 200
        assert http.get("/oauth/login", params={"txn": "x"}).status_code == 400


def _register(http) -> str:
    response = http.post(
        "/register",
        json={
            "redirect_uris": [REDIRECT_URI],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "client_name": "Claude",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body.get("client_secret") is None
    return body["client_id"]


def _sign_in(http, client_id, challenge, username="alice", state="state-123"):
    """Drive /authorize and the login form, and return the authorization code."""
    authorize = http.get(
        "/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        },
        follow_redirects=False,
    )
    assert authorize.status_code == 302, authorize.text
    txn_id = parse_qs(urlparse(authorize.headers["location"]).query)["txn"][0]

    submit = http.post(
        "/oauth/login",
        data={"txn": txn_id, "username": username, "password": "hunter2"},
        follow_redirects=False,
    )
    assert submit.status_code == 303
    query = parse_qs(urlparse(submit.headers["location"]).query)
    assert query["state"] == [state]
    return query["code"][0]


def _exchange(http, client_id, code, verifier):
    return http.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )


class TestConnectorFlow:
    def test_full_flow_issues_a_working_token(self, http, store):
        store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)

        code = _sign_in(http, client_id, challenge)
        tokens = _exchange(http, client_id, code, verifier).json()

        assert tokens["token_type"] == "Bearer"
        assert tokens["expires_in"] == 3600
        mcp = http.post(
            "/mcp",
            json={},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert mcp.status_code != 401

    def test_issued_token_is_visible_to_the_admin_ui(self, http, store):
        owner_id = store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)

        code = _sign_in(http, client_id, challenge)
        _exchange(http, client_id, code, verifier)

        tokens = store.list_tokens(owner_id)
        assert [token.label for token in tokens] == ["OAuth · Claude"]

    def test_code_cannot_be_exchanged_twice(self, http, store):
        store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, client_id, challenge)
        _exchange(http, client_id, code, verifier)

        second = _exchange(http, client_id, code, verifier)

        assert second.status_code == 400
        assert second.json()["error"] == "invalid_grant"

    def test_wrong_code_verifier_is_rejected_and_burns_the_code(self, http, store):
        store.create_account("alice", "hunter2")
        _, challenge = pkce_pair()
        other_verifier, _ = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, client_id, challenge)

        first = _exchange(http, client_id, code, other_verifier)

        assert first.json()["error"] == "invalid_grant"
        assert store.consume_authorization_code(code) is None

    def test_refresh_returns_a_working_token_and_retires_the_old_one(self, http, store):
        store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, client_id, challenge)
        tokens = _exchange(http, client_id, code, verifier).json()

        refreshed = http.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": client_id,
            },
        ).json()

        assert store.resolve(tokens["access_token"]) is None
        assert store.resolve(refreshed["access_token"]) is not None
        assert (
            http.post(
                "/mcp",
                json={},
                headers={"Authorization": f"Bearer {refreshed['access_token']}"},
            ).status_code
            != 401
        )

    def test_revoking_in_the_admin_ui_ends_the_session(self, http, store):
        owner_id = store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, client_id, challenge)
        tokens = _exchange(http, client_id, code, verifier).json()

        token_id = store.list_tokens(owner_id)[0].id
        store.revoke_token(token_id, requesting_owner_id=owner_id)

        refreshed = http.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": client_id,
            },
        )
        assert refreshed.json()["error"] == "invalid_grant"

    def test_revocation_endpoint_kills_the_token(self, http, store):
        store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, client_id, challenge)
        tokens = _exchange(http, client_id, code, verifier).json()

        response = http.post(
            "/revoke",
            data={"token": tokens["access_token"], "client_id": client_id},
        )

        assert response.status_code == 200
        assert store.resolve(tokens["access_token"]) is None

    def test_authorize_rejects_an_unregistered_redirect_uri(self, http, store):
        store.create_account("alice", "hunter2")
        _, challenge = pkce_pair()
        client_id = _register(http)

        response = http.get(
            "/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": "https://evil.test/callback",
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400

    def test_root_cannot_sign_in(self, http, store, monkeypatch):
        monkeypatch.setenv("ROOT_ADMIN_USERNAME", "root")
        monkeypatch.setenv("ROOT_ADMIN_PASSWORD", "root-password")
        _, challenge = pkce_pair()
        client_id = _register(http)
        authorize = http.get(
            "/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )
        txn_id = parse_qs(urlparse(authorize.headers["location"]).query)["txn"][0]

        response = http.post(
            "/oauth/login",
            data={"txn": txn_id, "username": "root", "password": "root-password"},
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert "Invalid username or password" in response.text
