"""Tests for the shared SQLite-backed TokenStore."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest

from unifi_mcp.tokens import (
    AccountExistsError,
    AccountNotFoundError,
    AuthorizationNotFoundError,
    TokenNotOwnedError,
    TokenStore,
    UsageEntry,
    UsageFilter,
)


@pytest.fixture
def store(tmp_path):
    return TokenStore(tmp_path / "tokens.db")


class TestAccounts:
    def test_create_account_returns_id(self, store):
        account_id = store.create_account("alice", "hunter2")

        assert isinstance(account_id, int)

    def test_create_account_duplicate_username_raises(self, store):
        store.create_account("alice", "hunter2")

        with pytest.raises(AccountExistsError):
            store.create_account("alice", "different-password")

    def test_verify_account_password_correct(self, store):
        account_id = store.create_account("alice", "hunter2")

        assert store.verify_account_password("alice", "hunter2") == account_id

    def test_verify_account_password_wrong_password(self, store):
        store.create_account("alice", "hunter2")

        assert store.verify_account_password("alice", "wrong") is None

    def test_verify_account_password_unknown_username(self, store):
        assert store.verify_account_password("nobody", "hunter2") is None


class TestTokens:
    def test_create_token_returns_raw_token_string(self, store):
        owner_id = store.create_account("alice", "hunter2")

        raw_token = store.create_token(owner_id, "laptop", None)

        assert isinstance(raw_token, str)
        assert len(raw_token) > 20

    def test_validate_accepts_freshly_created_token(self, store):
        owner_id = store.create_account("alice", "hunter2")
        raw_token = store.create_token(owner_id, "laptop", None)

        assert store.validate(raw_token) is True

    def test_validate_rejects_unknown_token(self, store):
        assert store.validate("not-a-real-token") is False

    def test_validate_rejects_revoked_token(self, store):
        owner_id = store.create_account("alice", "hunter2")
        raw_token = store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id

        store.revoke_token(token_id, requesting_owner_id=owner_id)

        assert store.validate(raw_token) is False

    def test_validate_rejects_expired_token(self, store):
        owner_id = store.create_account("alice", "hunter2")
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()

        raw_token = store.create_token(owner_id, "laptop", past)

        assert store.validate(raw_token) is False

    def test_validate_accepts_token_expiring_in_future(self, store):
        owner_id = store.create_account("alice", "hunter2")
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()

        raw_token = store.create_token(owner_id, "laptop", future)

        assert store.validate(raw_token) is True

    def test_list_tokens_filters_by_owner(self, store):
        alice_id = store.create_account("alice", "hunter2")
        bob_id = store.create_account("bob", "hunter3")
        store.create_token(alice_id, "alice-laptop", None)
        store.create_token(bob_id, "bob-laptop", None)

        alice_tokens = store.list_tokens(owner_id=alice_id)

        assert len(alice_tokens) == 1
        assert alice_tokens[0].label == "alice-laptop"

    def test_list_tokens_no_owner_returns_all(self, store):
        alice_id = store.create_account("alice", "hunter2")
        bob_id = store.create_account("bob", "hunter3")
        store.create_token(alice_id, "alice-laptop", None)
        store.create_token(bob_id, "bob-laptop", None)

        all_tokens = store.list_tokens(owner_id=None)

        assert len(all_tokens) == 2

    def test_revoke_token_by_non_owner_raises(self, store):
        alice_id = store.create_account("alice", "hunter2")
        bob_id = store.create_account("bob", "hunter3")
        store.create_token(alice_id, "alice-laptop", None)
        token_id = store.list_tokens(alice_id)[0].id

        with pytest.raises(TokenNotOwnedError):
            store.revoke_token(token_id, requesting_owner_id=bob_id)

    def test_revoke_token_unknown_id_raises(self, store):
        with pytest.raises(TokenNotOwnedError):
            store.revoke_token(999999, requesting_owner_id=None)

    def test_revoke_token_with_no_requester_bypasses_ownership_check(self, store):
        owner_id = store.create_account("alice", "hunter2")
        raw_token = store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id

        store.revoke_token(token_id, requesting_owner_id=None)

        assert store.validate(raw_token) is False

    def test_root_cannot_own_a_token(self, store):
        # Root has no accounts row; the FK constraint makes this structurally
        # impossible rather than relying on a business-logic check.
        with pytest.raises(sqlite3.IntegrityError):
            store.create_token(owner_id=999999, label="root-token", expires_at=None)


class TestResolve:
    def test_resolve_returns_record_for_valid_token(self, store):
        owner_id = store.create_account("alice", "hunter2")
        raw_token = store.create_token(owner_id, "laptop", None)

        record = store.resolve(raw_token)

        assert record is not None
        assert record.owner_id == owner_id
        assert record.owner_username == "alice"
        assert record.label == "laptop"

    def test_resolve_returns_none_for_unknown_token(self, store):
        assert store.resolve("not-a-real-token") is None

    def test_resolve_returns_none_for_revoked_token(self, store):
        owner_id = store.create_account("alice", "hunter2")
        raw_token = store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id
        store.revoke_token(token_id, requesting_owner_id=owner_id)

        assert store.resolve(raw_token) is None

    def test_resolve_returns_none_for_expired_token(self, store):
        owner_id = store.create_account("alice", "hunter2")
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        raw_token = store.create_token(owner_id, "laptop", past)

        assert store.resolve(raw_token) is None


class TestListAccounts:
    def test_lists_accounts_with_token_counts(self, store):
        alice_id = store.create_account("alice", "hunter2")
        store.create_account("bob", "hunter3")
        store.create_token(alice_id, "laptop", None)
        store.create_token(alice_id, "phone", None)
        revoked_id = store.list_tokens(alice_id)[0].id
        store.revoke_token(revoked_id, requesting_owner_id=alice_id)

        accounts = store.list_accounts()

        assert [a.username for a in accounts] == ["alice", "bob"]
        alice, bob = accounts
        assert alice.id == alice_id
        assert alice.token_count == 2
        assert alice.active_token_count == 1
        assert bob.token_count == 0
        assert bob.active_token_count == 0

    def test_expired_token_is_not_counted_as_active(self, store):
        alice_id = store.create_account("alice", "hunter2")
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        store.create_token(alice_id, "old", past)

        (alice,) = store.list_accounts()

        assert alice.token_count == 1
        assert alice.active_token_count == 0


class TestDeleteAccount:
    def test_delete_account_removes_account_and_its_tokens(self, store):
        alice_id = store.create_account("alice", "hunter2")
        bob_id = store.create_account("bob", "hunter3")
        alice_token = store.create_token(alice_id, "laptop", None)
        bob_token = store.create_token(bob_id, "laptop", None)

        store.delete_account(alice_id)

        assert store.verify_account_password("alice", "hunter2") is None
        assert store.validate(alice_token) is False
        assert store.validate(bob_token) is True
        assert [a.username for a in store.list_accounts()] == ["bob"]

    def test_delete_unknown_account_raises(self, store):
        with pytest.raises(AccountNotFoundError):
            store.delete_account(999999)

    def test_delete_account_keeps_usage_log_rows(self, store):
        alice_id = store.create_account("alice", "hunter2")
        store.create_token(alice_id, "laptop", None)
        token = store.list_tokens(alice_id)[0]
        store.log_usage(_entry(token, tool="get_devices"))

        store.delete_account(alice_id)

        rows = store.list_usage(UsageFilter(), limit=10, offset=0)
        assert len(rows) == 1
        assert rows[0].owner_username == "alice"
        assert rows[0].token_label == "laptop"


def _entry(token, **overrides):
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
    return UsageEntry(**fields)


@pytest.fixture
def usage_store(store):
    alice_id = store.create_account("alice", "hunter2")
    bob_id = store.create_account("bob", "hunter3")
    store.create_token(alice_id, "laptop", None)
    store.create_token(bob_id, "phone", None)
    alice_token = store.list_tokens(alice_id)[0]
    bob_token = store.list_tokens(bob_id)[0]
    store.log_usage(_entry(alice_token, tool="get_devices", ip="10.0.0.5"))
    store.log_usage(
        _entry(
            alice_token, tool="get_clients", ip="10.0.0.6", status=500, duration_ms=900
        )
    )
    store.log_usage(
        _entry(
            bob_token,
            method="initialize",
            tool=None,
            ip="192.168.1.9",
            forwarded_for=None,
        )
    )
    return store


class TestUsageLog:
    def test_log_usage_round_trips_every_field(self, store):
        alice_id = store.create_account("alice", "hunter2")
        store.create_token(alice_id, "laptop", None)
        token = store.list_tokens(alice_id)[0]

        store.log_usage(_entry(token))
        (row,) = store.list_usage(UsageFilter(), limit=10, offset=0)

        assert row.token_id == token.id
        assert row.token_label == "laptop"
        assert row.owner_id == alice_id
        assert row.owner_username == "alice"
        assert row.ip == "10.0.0.5"
        assert row.remote_addr == "172.16.0.2"
        assert row.forwarded_for == "10.0.0.5, 172.16.0.2"
        assert row.user_agent == "claude-code/1.0"
        assert row.method == "tools/call"
        assert row.tool == "get_devices"
        assert row.status == 200
        assert row.duration_ms == 42
        assert row.ts.endswith("+00:00")

    def test_list_usage_is_newest_first(self, usage_store):
        rows = usage_store.list_usage(UsageFilter(), limit=10, offset=0)

        assert [r.tool for r in rows] == [None, "get_clients", "get_devices"]

    def test_list_usage_pages(self, usage_store):
        first = usage_store.list_usage(UsageFilter(), limit=2, offset=0)
        second = usage_store.list_usage(UsageFilter(), limit=2, offset=2)

        assert len(first) == 2
        assert len(second) == 1
        assert usage_store.count_usage(UsageFilter()) == 3

    def test_filter_by_owner_username(self, usage_store):
        rows = usage_store.list_usage(
            UsageFilter(owner_username="bob"), limit=10, offset=0
        )

        assert [r.owner_username for r in rows] == ["bob"]

    def test_filter_by_token_label(self, usage_store):
        rows = usage_store.list_usage(
            UsageFilter(token_label="laptop"), limit=10, offset=0
        )

        assert len(rows) == 2
        assert {r.token_label for r in rows} == {"laptop"}

    def test_filter_by_ip_substring(self, usage_store):
        rows = usage_store.list_usage(UsageFilter(ip="10.0.0"), limit=10, offset=0)

        assert {r.ip for r in rows} == {"10.0.0.5", "10.0.0.6"}

    def test_filter_by_forwarded_for_substring(self, usage_store):
        rows = usage_store.list_usage(
            UsageFilter(forwarded_for="172.16"), limit=10, offset=0
        )

        assert len(rows) == 2

    def test_filter_by_method(self, usage_store):
        rows = usage_store.list_usage(
            UsageFilter(method="initialize"), limit=10, offset=0
        )

        assert [r.owner_username for r in rows] == ["bob"]

    def test_filter_by_tool(self, usage_store):
        rows = usage_store.list_usage(
            UsageFilter(tool="get_clients"), limit=10, offset=0
        )

        assert [r.tool for r in rows] == ["get_clients"]

    def test_filter_by_status(self, usage_store):
        rows = usage_store.list_usage(UsageFilter(status=500), limit=10, offset=0)

        assert [r.status for r in rows] == [500]

    def test_filter_by_min_duration(self, usage_store):
        rows = usage_store.list_usage(
            UsageFilter(min_duration_ms=100), limit=10, offset=0
        )

        assert [r.duration_ms for r in rows] == [900]

    def test_filter_by_time_window(self, usage_store):
        rows = usage_store.list_usage(UsageFilter(), limit=10, offset=0)
        middle_ts = rows[1].ts

        since_rows = usage_store.list_usage(
            UsageFilter(since=middle_ts), limit=10, offset=0
        )
        until_rows = usage_store.list_usage(
            UsageFilter(until=middle_ts), limit=10, offset=0
        )

        assert len(since_rows) == 2
        assert len(until_rows) == 2
        assert since_rows[-1].ts == middle_ts
        assert until_rows[0].ts == middle_ts

    def test_filters_combine_with_and(self, usage_store):
        rows = usage_store.list_usage(
            UsageFilter(owner_username="alice", status=200), limit=10, offset=0
        )

        assert [r.tool for r in rows] == ["get_devices"]

    def test_count_usage_honours_filters(self, usage_store):
        assert usage_store.count_usage(UsageFilter(owner_username="alice")) == 2

    def test_usage_facets_lists_distinct_values(self, usage_store):
        facets = usage_store.usage_facets()

        assert facets.owner_usernames == ["alice", "bob"]
        assert facets.token_labels == ["laptop", "phone"]
        assert facets.methods == ["initialize", "tools/call"]
        assert facets.tools == ["get_clients", "get_devices"]
        assert facets.statuses == [200, 500]

    def test_usage_summary_counts_recent_activity(self, usage_store):
        summary = usage_store.usage_summary()

        assert summary.calls_today == 3
        assert summary.calls_last_7_days == 3
        assert summary.callers_last_7_days == 2
        assert summary.ips_last_7_days == 3

    def test_log_usage_swallows_database_errors(self, store, tmp_path, caplog):
        alice_id = store.create_account("alice", "hunter2")
        store.create_token(alice_id, "laptop", None)
        token = store.list_tokens(alice_id)[0]
        with closing(sqlite3.connect(tmp_path / "tokens.db")) as conn:
            conn.execute("DROP TABLE usage_log")
            conn.commit()

        store.log_usage(_entry(token))  # must not raise

        assert "usage_log" in caplog.text


class TestGetAccount:
    def test_returns_record_with_token_counts(self, store):
        alice_id = store.create_account("alice", "hunter2")
        store.create_token(alice_id, "laptop", None)

        account = store.get_account(alice_id)

        assert account is not None
        assert account.username == "alice"
        assert account.token_count == 1
        assert account.active_token_count == 1

    def test_unknown_id_returns_none(self, store):
        assert store.get_account(999999) is None


class TestSetAccountPassword:
    def test_new_password_replaces_the_old_one(self, store):
        alice_id = store.create_account("alice", "hunter2")

        store.set_account_password(alice_id, "newpass9")

        assert store.verify_account_password("alice", "hunter2") is None
        assert store.verify_account_password("alice", "newpass9") == alice_id

    def test_unknown_account_raises(self, store):
        with pytest.raises(AccountNotFoundError):
            store.set_account_password(999999, "whatever")

    def test_tokens_survive_a_password_reset(self, store):
        alice_id = store.create_account("alice", "hunter2")
        raw_token = store.create_token(alice_id, "laptop", None)

        store.set_account_password(alice_id, "newpass9")

        assert store.validate(raw_token) is True


class TestOAuthClients:
    def test_get_oauth_client_unknown_returns_none(self, store):
        assert store.get_oauth_client("nope") is None

    def test_save_then_get_oauth_client_round_trips(self, store):
        store.save_oauth_client("abc", '{"client_id": "abc"}')

        assert store.get_oauth_client("abc") == '{"client_id": "abc"}'

    def test_save_oauth_client_twice_overwrites(self, store):
        store.save_oauth_client("abc", '{"v": 1}')
        store.save_oauth_client("abc", '{"v": 2}')

        assert store.get_oauth_client("abc") == '{"v": 2}'


class TestTokenRotation:
    def test_get_token_returns_record(self, store):
        owner_id = store.create_account("alice", "hunter2")
        store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id

        assert store.get_token(token_id).label == "laptop"

    def test_get_token_unknown_returns_none(self, store):
        assert store.get_token(999) is None

    def test_rotate_token_invalidates_old_secret(self, store):
        owner_id = store.create_account("alice", "hunter2")
        old = store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id

        new = store.rotate_token(token_id, None)

        assert store.resolve(old) is None
        assert store.resolve(new).id == token_id

    def test_rotate_token_keeps_row_identity(self, store):
        owner_id = store.create_account("alice", "hunter2")
        store.create_token(owner_id, "laptop", None)
        before = store.list_tokens(owner_id)[0]

        store.rotate_token(before.id, None)
        after = store.list_tokens(owner_id)[0]

        assert (after.id, after.label, after.created_at) == (
            before.id,
            before.label,
            before.created_at,
        )

    def test_rotate_token_sets_new_expiry(self, store):
        owner_id = store.create_account("alice", "hunter2")
        store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

        store.rotate_token(token_id, future)

        assert store.get_token(token_id).expires_at == future

    def test_rotate_revoked_token_raises(self, store):
        owner_id = store.create_account("alice", "hunter2")
        store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id
        store.revoke_token(token_id, requesting_owner_id=owner_id)

        with pytest.raises(TokenNotOwnedError):
            store.rotate_token(token_id, None)


def _make_authorization(store, client_id="client-1", minutes=10):
    store.save_oauth_client(client_id, "{}")
    return store.create_authorization(
        client_id=client_id,
        redirect_uri="https://claude.ai/api/mcp/auth_callback",
        redirect_uri_explicit=True,
        code_challenge="challenge",
        state="state-123",
        scope="",
        resource="https://example.test/mcp",
        expires_at=(datetime.now(UTC) + timedelta(minutes=minutes)).isoformat(),
    )


class TestAuthorizations:
    def test_create_returns_opaque_id(self, store):
        txn_id = _make_authorization(store)

        assert isinstance(txn_id, str)
        assert len(txn_id) >= 32

    def test_get_returns_record_with_fields(self, store):
        txn_id = _make_authorization(store)

        record = store.get_authorization(txn_id)

        assert record.client_id == "client-1"
        assert record.redirect_uri == "https://claude.ai/api/mcp/auth_callback"
        assert record.redirect_uri_explicit is True
        assert record.state == "state-123"
        assert record.owner_id is None
        assert record.attempts == 0

    def test_get_unknown_returns_none(self, store):
        assert store.get_authorization("nope") is None

    def test_get_expired_returns_none(self, store):
        txn_id = _make_authorization(store, minutes=-1)

        assert store.get_authorization(txn_id) is None

    def test_complete_then_consume_round_trips(self, store):
        owner_id = store.create_account("alice", "hunter2")
        txn_id = _make_authorization(store)

        code = store.complete_authorization(txn_id, owner_id)
        record = store.consume_authorization_code(code)

        assert record.owner_id == owner_id
        assert record.code_challenge == "challenge"

    def test_consume_is_single_use(self, store):
        owner_id = store.create_account("alice", "hunter2")
        txn_id = _make_authorization(store)
        code = store.complete_authorization(txn_id, owner_id)

        store.consume_authorization_code(code)

        assert store.consume_authorization_code(code) is None

    def test_consume_unknown_code_returns_none(self, store):
        assert store.consume_authorization_code("nope") is None

    def test_complete_unknown_txn_raises(self, store):
        owner_id = store.create_account("alice", "hunter2")

        with pytest.raises(AuthorizationNotFoundError):
            store.complete_authorization("nope", owner_id)

    def test_fail_attempt_returns_remaining(self, store):
        txn_id = _make_authorization(store)

        assert store.fail_authorization_attempt(txn_id, 5) == 4
        assert store.fail_authorization_attempt(txn_id, 5) == 3

    def test_fail_attempt_deletes_row_at_cap(self, store):
        txn_id = _make_authorization(store)
        for _ in range(4):
            store.fail_authorization_attempt(txn_id, 5)

        assert store.fail_authorization_attempt(txn_id, 5) == 0
        assert store.get_authorization(txn_id) is None

    def test_fail_attempt_on_unknown_txn_returns_zero(self, store):
        assert store.fail_authorization_attempt("nope", 5) == 0

    def test_delete_authorization_removes_row(self, store):
        txn_id = _make_authorization(store)

        store.delete_authorization(txn_id)

        assert store.get_authorization(txn_id) is None


def _make_oauth_token(store, username="alice", client_id="client-1"):
    """Return (owner_id, token_id, access_token, refresh_token)."""
    owner_id = store.create_account(username, "hunter2")
    store.save_oauth_client(client_id, "{}")
    access = store.create_token(owner_id, "OAuth · Claude", None)
    token_id = store.resolve(access).id
    refresh = store.create_refresh_token(
        token_id=token_id,
        client_id=client_id,
        scope="",
        grant_expires_at=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
    )
    return owner_id, token_id, access, refresh


class TestRefreshTokens:
    def test_get_refresh_token_returns_record(self, store):
        owner_id, token_id, _, refresh = _make_oauth_token(store)

        record = store.get_refresh_token(refresh)

        assert record.token_id == token_id
        assert record.client_id == "client-1"
        assert record.owner_id == owner_id
        assert record.revoked_at is None

    def test_get_refresh_token_unknown_returns_none(self, store):
        assert store.get_refresh_token("nope") is None

    def test_delete_refresh_token_removes_it(self, store):
        _, _, _, refresh = _make_oauth_token(store)

        store.delete_refresh_token(refresh)

        assert store.get_refresh_token(refresh) is None

    def test_refresh_record_reports_revoked_access_token(self, store):
        owner_id, token_id, _, refresh = _make_oauth_token(store)
        store.revoke_token(token_id, requesting_owner_id=owner_id)

        assert store.get_refresh_token(refresh).revoked_at is not None

    def test_get_oauth_client_id_for_token(self, store):
        _, token_id, _, _ = _make_oauth_token(store)

        assert store.get_oauth_client_id_for_token(token_id) == "client-1"

    def test_get_oauth_client_id_for_static_token_is_none(self, store):
        owner_id = store.create_account("bob", "hunter2")
        store.create_token(owner_id, "laptop", None)
        token_id = store.list_tokens(owner_id)[0].id

        assert store.get_oauth_client_id_for_token(token_id) is None

    def test_revoke_token_by_value_revokes_and_drops_refresh(self, store):
        _, _, access, refresh = _make_oauth_token(store)

        store.revoke_token_by_value(access)

        assert store.resolve(access) is None
        assert store.get_refresh_token(refresh) is None

    def test_revoke_token_by_value_unknown_is_a_no_op(self, store):
        store.revoke_token_by_value("nope")

    def test_revoke_by_refresh_token_revokes_access_token(self, store):
        _, _, access, refresh = _make_oauth_token(store)

        store.revoke_by_refresh_token(refresh)

        assert store.resolve(access) is None
        assert store.get_refresh_token(refresh) is None

    def test_deleting_account_cascades_to_refresh_tokens(self, store):
        owner_id, _, _, refresh = _make_oauth_token(store)

        store.delete_account(owner_id)

        assert store.get_refresh_token(refresh) is None
