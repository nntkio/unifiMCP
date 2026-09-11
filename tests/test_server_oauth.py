"""Tests for the OAuth authorization server (server/_oauth.py)."""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from unifi_mcp.server._oauth import TokenStoreOAuthProvider, client_label
from unifi_mcp.tokens import TokenStore

REDIRECT_URI = "https://claude.ai/api/mcp/auth_callback"


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
def provider(store):
    return TokenStoreOAuthProvider(store)


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
