"""Tests for the shared SQLite-backed TokenStore."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from unifi_mcp.tokens import AccountExistsError, TokenNotOwnedError, TokenStore


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
