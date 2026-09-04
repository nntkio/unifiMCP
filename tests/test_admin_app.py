"""Tests for the token-admin service: auth helpers and the Starlette app."""

import os
from unittest.mock import patch

import pytest

from unifi_mcp.admin.auth import (
    check_root_credentials,
    csrf_token_valid,
    generate_csrf_token,
)


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
