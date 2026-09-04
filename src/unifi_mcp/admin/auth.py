"""Root-credential check and CSRF helpers for the token-admin service."""

import hmac
import os
import secrets


def check_root_credentials(username: str, password: str) -> bool:
    """Check credentials against ROOT_ADMIN_USERNAME/ROOT_ADMIN_PASSWORD.

    Root has no row in the accounts table — its identity lives entirely in
    these environment variables, so it structurally cannot own a token.
    """
    root_username = os.environ.get("ROOT_ADMIN_USERNAME", "root")
    root_password = os.environ["ROOT_ADMIN_PASSWORD"]
    username_matches = hmac.compare_digest(username, root_username)
    password_matches = hmac.compare_digest(password, root_password)
    return username_matches and password_matches


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_token_valid(session_token: str | None, submitted_token: str | None) -> bool:
    if not session_token or not submitted_token:
        return False
    return hmac.compare_digest(session_token, submitted_token)
