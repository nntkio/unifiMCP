"""Tests for the token-admin service: auth helpers and the Starlette app."""

import os
import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from unifi_mcp.admin.app import build_app
from unifi_mcp.admin.auth import (
    check_root_credentials,
    csrf_token_valid,
    generate_csrf_token,
)
from unifi_mcp.tokens import TokenStore, UsageEntry


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


class TestRootRedirect:
    def test_root_path_redirects_to_login(self, app):
        with TestClient(app) as client:
            response = client.get("/", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/login"


class TestStaticAssets:
    def test_stylesheet_is_served(self, app):
        with TestClient(app) as client:
            response = client.get("/static/admin.css")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/css")

    def test_fonts_are_served(self, app):
        with TestClient(app) as client:
            response = client.get("/static/fonts/space-grotesk.woff2")

        assert response.status_code == 200


class TestShell:
    def test_sidebar_shows_signed_in_account(self, app, store):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            _login_as(client, "alice", "hunter2")
            page = client.get("/tokens")

        assert 'class="adm-me-name">alice<' in page.text
        assert "Log out" in page.text

    def test_sidebar_shows_root_identity_and_nav(self, app, root_env):
        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            page = client.get("/admin")

        assert 'class="adm-me-name">root<' in page.text
        assert 'href="/admin/usage"' in page.text

    def test_dates_render_in_short_form(self, app, store):
        store.create_account("alice", "hunter2")
        alice_id = store.verify_account_password("alice", "hunter2")
        store.create_token(alice_id, "laptop", None)

        with TestClient(app) as client:
            _login_as(client, "alice", "hunter2")
            page = client.get("/tokens")

        assert datetime.now(UTC).strftime("%d %b %Y") in page.text


class TestAccountsPage:
    def test_groups_tokens_under_their_owner(self, app, store, root_env):
        alice_id = store.create_account("alice", "hunter2")
        store.create_account("bob", "hunter3")
        store.create_token(alice_id, "alice-laptop", None)

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            page = client.get("/admin")

        alice_at = page.text.index('class="adm-group-name">alice<')
        bob_at = page.text.index('class="adm-group-name">bob<')
        token_at = page.text.index("alice-laptop")
        assert alice_at < token_at < bob_at
        assert "No tokens yet" in page.text

    def test_status_chips_reflect_token_state(self, app, store, root_env):
        alice_id = store.create_account("alice", "hunter2")
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        store.create_token(alice_id, "expired-one", past)
        store.create_token(alice_id, "revoked-one", None)
        store.create_token(alice_id, "active-one", None)
        revoked = next(
            t for t in store.list_tokens(alice_id) if t.label == "revoked-one"
        )
        store.revoke_token(revoked.id, requesting_owner_id=None)

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            page = client.get("/admin")

        assert 'class="adm-badge expired">Expired<' in page.text
        assert 'class="adm-badge revoked">Revoked<' in page.text
        assert 'class="adm-badge active">Active<' in page.text
        # Only the active token offers a revoke button.
        assert page.text.count("/revoke") == 1


class TestDeleteAccount:
    def test_root_can_delete_account_and_its_tokens(self, app, store, root_env):
        alice_id = store.create_account("alice", "hunter2")
        raw_token = store.create_token(alice_id, "laptop", None)

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            csrf = _extract_csrf(client.get("/admin").text)
            response = client.post(
                f"/admin/accounts/{alice_id}/delete",
                data={"csrf_token": csrf},
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin"
        assert store.verify_account_password("alice", "hunter2") is None
        assert store.validate(raw_token) is False

    def test_unknown_account_returns_404(self, app, root_env):
        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            csrf = _extract_csrf(client.get("/admin").text)
            response = client.post(
                "/admin/accounts/999999/delete", data={"csrf_token": csrf}
            )

        assert response.status_code == 404

    def test_bad_csrf_is_rejected(self, app, store, root_env):
        alice_id = store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            client.get("/admin")
            response = client.post(
                f"/admin/accounts/{alice_id}/delete", data={"csrf_token": "bogus"}
            )

        assert response.status_code == 403
        assert store.verify_account_password("alice", "hunter2") == alice_id

    def test_regular_user_is_redirected(self, app, store):
        alice_id = store.create_account("alice", "hunter2")
        bob_id = store.create_account("bob", "hunter3")

        with TestClient(app) as client:
            _login_as(client, "alice", "hunter2")
            csrf = _extract_csrf(client.get("/tokens").text)
            response = client.post(
                f"/admin/accounts/{bob_id}/delete",
                data={"csrf_token": csrf},
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        assert store.verify_account_password("bob", "hunter3") == bob_id
        assert alice_id is not None


def _log(store, token, **overrides):
    fields = {
        "token_id": token.id,
        "token_label": token.label,
        "owner_id": token.owner_id,
        "owner_username": token.owner_username,
        "ip": "10.0.0.5",
        "remote_addr": "172.16.0.2",
        "forwarded_for": "10.0.0.5, 172.16.0.2",
        "user_agent": "claude-code/1.0",
        "method": "tools/call",
        "tool": "get_devices",
        "status": 200,
        "duration_ms": 42,
    }
    fields.update(overrides)
    store.log_usage(UsageEntry(**fields))


@pytest.fixture
def usage_store(store):
    alice_id = store.create_account("alice", "hunter2")
    bob_id = store.create_account("bob", "hunter3")
    store.create_token(alice_id, "laptop", None)
    store.create_token(bob_id, "phone", None)
    alice_token = store.list_tokens(alice_id)[0]
    bob_token = store.list_tokens(bob_id)[0]
    _log(store, alice_token, tool="get_devices", ip="10.0.0.5")
    _log(store, alice_token, tool="get_clients", ip="10.0.0.6", status=500)
    _log(
        store,
        bob_token,
        method="initialize",
        tool=None,
        ip="192.168.1.9",
        forwarded_for=None,
    )
    return store


class TestUsagePage:
    def test_lists_calls_with_caller_and_origin(self, app, usage_store, root_env):
        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            page = client.get("/admin/usage")

        assert page.status_code == 200
        for expected in (
            "alice",
            "bob",
            "laptop",
            "phone",
            "get_devices",
            "get_clients",
            "10.0.0.5",
            "192.168.1.9",
            "initialize",
        ):
            assert expected in page.text
        assert "3 calls" in page.text

    def test_filters_narrow_the_rows(self, app, usage_store, root_env):
        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            by_owner = client.get("/admin/usage", params={"owner_username": "bob"})
            by_ip = client.get("/admin/usage", params={"ip": "10.0.0"})
            by_status = client.get("/admin/usage", params={"status": "500"})
            combined = client.get(
                "/admin/usage", params={"owner_username": "alice", "status": "200"}
            )

        assert "192.168.1.9" in by_owner.text and "10.0.0.5" not in by_owner.text
        assert "1 call" in by_owner.text
        assert "2 calls" in by_ip.text and "192.168.1.9" not in by_ip.text
        assert "1 call" in by_status.text and "10.0.0.6" in by_status.text
        assert "1 call" in combined.text and "10.0.0.5" in combined.text

    def test_filter_values_are_echoed_back_into_the_form(
        self, app, usage_store, root_env
    ):
        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            page = client.get(
                "/admin/usage", params={"owner_username": "bob", "ip": "192.168"}
            )

        assert '<option value="bob" selected>' in page.text
        assert 'name="ip" value="192.168"' in page.text

    def test_invalid_numeric_filters_are_ignored(self, app, usage_store, root_env):
        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            page = client.get(
                "/admin/usage",
                params={"status": "abc", "min_duration_ms": "x", "page": "zero"},
            )

        assert page.status_code == 200
        assert "3 calls" in page.text

    def test_pages_fifty_rows_at_a_time(self, app, store, root_env):
        alice_id = store.create_account("alice", "hunter2")
        store.create_token(alice_id, "laptop", None)
        token = store.list_tokens(alice_id)[0]
        _log(store, token, ip="10.99.99.99")
        for _ in range(50):
            _log(store, token, ip="10.0.0.5")

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            first = client.get("/admin/usage")
            second = client.get("/admin/usage", params={"page": 2})

        assert "10.99.99.99" not in first.text
        assert "10.99.99.99" in second.text
        assert "51 calls" in first.text
        assert 'href="/admin/usage?page=2"' in first.text

    def test_pager_preserves_active_filters(self, app, store, root_env):
        alice_id = store.create_account("alice", "hunter2")
        store.create_token(alice_id, "laptop", None)
        token = store.list_tokens(alice_id)[0]
        for _ in range(51):
            _log(store, token, tool="get_devices")

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            page = client.get("/admin/usage", params={"tool": "get_devices"})

        assert 'href="/admin/usage?tool=get_devices&amp;page=2"' in page.text

    def test_regular_user_is_redirected(self, app, store):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            _login_as(client, "alice", "hunter2")
            response = client.get("/admin/usage", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/login"


class TestLoginResetsSession:
    def test_signing_in_as_account_drops_a_previous_root_session(
        self, app, store, root_env
    ):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            _login_as(client, "root", "rootpass123")
            _login_as(client, "alice", "hunter2")
            admin = client.get("/admin", follow_redirects=False)
            tokens = client.get("/tokens")

        assert admin.status_code == 303
        assert 'class="adm-me-name">alice<' in tokens.text
        assert "Administrator" not in tokens.text

    def test_signing_in_as_root_drops_a_previous_account_session(
        self, app, store, root_env
    ):
        store.create_account("alice", "hunter2")

        with TestClient(app) as client:
            _login_as(client, "alice", "hunter2")
            _login_as(client, "root", "rootpass123")
            tokens = client.get("/tokens", follow_redirects=False)

        assert tokens.status_code == 303
        assert tokens.headers["location"] == "/login"
