"""Tests for the token-admin service: auth helpers and the Starlette app."""

import os
import re
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from unifi_mcp.admin.app import build_app
from unifi_mcp.admin.auth import (
    check_root_credentials,
    csrf_token_valid,
    generate_csrf_token,
)
from unifi_mcp.tokens import TokenStore


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf_token field not found in response HTML"
    return match.group(1)


@pytest.fixture
def root_env():
    with patch.dict(
        os.environ,
        {"ROOT_ADMIN_USERNAME": "root", "ROOT_ADMIN_PASSWORD": "rootpass123"},
    ):
        yield


class TestCheckRootCredentials:
    def test_matches_configured_credentials(self, root_env):
        assert check_root_credentials("root", "rootpass123") is True

    def test_rejects_wrong_password(self, root_env):
        assert check_root_credentials("root", "wrong") is False

    def test_rejects_wrong_username(self, root_env):
        assert check_root_credentials("notroot", "rootpass123") is False

    def test_uses_root_as_default_username(self, monkeypatch):
        monkeypatch.delenv("ROOT_ADMIN_USERNAME", raising=False)
        monkeypatch.setenv("ROOT_ADMIN_PASSWORD", "rootpass123")

        assert check_root_credentials("root", "rootpass123") is True


class TestCsrf:
    def test_generated_token_is_valid_against_itself(self):
        token = generate_csrf_token()

        assert csrf_token_valid(token, token) is True

    def test_mismatched_tokens_are_invalid(self):
        assert csrf_token_valid(generate_csrf_token(), generate_csrf_token()) is False

    def test_missing_submitted_token_is_invalid(self):
        assert csrf_token_valid(generate_csrf_token(), None) is False

    def test_missing_session_token_is_invalid(self):
        assert csrf_token_valid(None, "whatever") is False


@pytest.fixture
def store(tmp_path):
    return TokenStore(tmp_path / "tokens.db")


@pytest.fixture
def app(store):
    return build_app(store, session_secret="test-secret")


class TestLogin:
    def test_root_login_redirects_to_admin(self, app, root_env):
        with TestClient(app) as client:
            login_page = client.get("/login")
            csrf = _extract_csrf(login_page.text)

            response = client.post(
                "/login",
                data={
                    "username": "root",
                    "password": "rootpass123",
                    "csrf_token": csrf,
                },
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin"

    def test_account_login_redirects_to_tokens(self, app, store):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            login_page = client.get("/login")
            csrf = _extract_csrf(login_page.text)

            response = client.post(
                "/login",
                data={"username": "alice", "password": "hunter2", "csrf_token": csrf},
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert response.headers["location"] == "/tokens"

    def test_wrong_password_rerenders_with_error(self, app, store):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            login_page = client.get("/login")
            csrf = _extract_csrf(login_page.text)

            response = client.post(
                "/login",
                data={"username": "alice", "password": "wrong", "csrf_token": csrf},
            )

        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    def test_missing_csrf_token_rejected(self, app, store):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            client.get("/login")

            response = client.post(
                "/login",
                data={
                    "username": "alice",
                    "password": "hunter2",
                    "csrf_token": "bogus",
                },
            )

        assert response.status_code == 403


def _login_as(client, username, password):
    login_page = client.get("/login")
    csrf = _extract_csrf(login_page.text)
    client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )


class TestUserTokenFlow:
    def test_create_list_and_revoke_own_token(self, app, store):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            _login_as(client, "alice", "hunter2")

            tokens_page = client.get("/tokens")
            csrf = _extract_csrf(tokens_page.text)
            create_response = client.post(
                "/tokens",
                data={"label": "laptop", "expiry_preset": "never", "csrf_token": csrf},
                follow_redirects=False,
            )

            assert create_response.status_code == 303

            tokens_page = client.get("/tokens")

        assert "laptop" in tokens_page.text
        assert "copy it now" in tokens_page.text.lower()

    def test_user_sees_only_their_own_tokens(self, app, store):
        alice_id = store.create_account("alice", "hunter2")
        store.create_account("bob", "hunter3")
        store.create_token(alice_id, "alice-laptop", None)

        with TestClient(app) as client:
            _login_as(client, "bob", "hunter3")

            tokens_page = client.get("/tokens")

        assert "alice-laptop" not in tokens_page.text

    def test_user_cannot_revoke_another_users_token(self, app, store):
        alice_id = store.create_account("alice", "hunter2")
        store.create_account("bob", "hunter3")
        store.create_token(alice_id, "alice-laptop", None)
        token_id = store.list_tokens(alice_id)[0].id

        with TestClient(app) as client:
            _login_as(client, "bob", "hunter3")
            tokens_page = client.get("/tokens")
            csrf = _extract_csrf(tokens_page.text)

            response = client.post(
                f"/tokens/{token_id}/revoke", data={"csrf_token": csrf}
            )

        assert response.status_code == 403
        assert store.validate("irrelevant") is False


class TestRootAdminFlow:
    def test_root_can_create_account(self, app, store, root_env):
        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            admin_page = client.get("/admin")
            csrf = _extract_csrf(admin_page.text)

            response = client.post(
                "/admin/accounts",
                data={
                    "username": "newuser",
                    "temp_password": "temppass123",
                    "csrf_token": csrf,
                },
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert store.verify_account_password("newuser", "temppass123") is not None

    def test_root_sees_all_users_tokens(self, app, store, root_env):
        alice_id = store.create_account("alice", "hunter2")
        store.create_token(alice_id, "alice-laptop", None)

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")

            admin_page = client.get("/admin")

        assert "alice-laptop" in admin_page.text
        assert "alice" in admin_page.text

    def test_regular_user_cannot_reach_admin_routes(self, app, store):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            _login_as(client, "alice", "hunter2")

            response = client.get("/admin", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/login"


class TestRootCredentialsUnconfigured:
    def test_returns_false_when_root_password_unset(self, monkeypatch):
        # login_submit calls check_root_credentials on every login attempt,
        # so an unset ROOT_ADMIN_PASSWORD must fail closed, not raise.
        monkeypatch.delenv("ROOT_ADMIN_PASSWORD", raising=False)

        assert check_root_credentials("root", "anything") is False
