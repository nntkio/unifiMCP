"""Token-admin web service: login + bearer-token management UI."""

import os

import uvicorn

from unifi_mcp.admin.app import build_app
from unifi_mcp.tokens import TokenStore

__all__ = ["main"]


def main() -> None:
    """Run the token-admin service.

    Requires ROOT_ADMIN_PASSWORD and ADMIN_SESSION_SECRET to be set. Reads
    ROOT_ADMIN_USERNAME (default "root"), ADMIN_HTTP_HOST (default
    "0.0.0.0"), ADMIN_HTTP_PORT (default 8766), and TOKEN_DB_PATH (default
    "/data/tokens.db").
    """
    if "ROOT_ADMIN_PASSWORD" not in os.environ:
        raise RuntimeError("ROOT_ADMIN_PASSWORD must be set to run unifi-mcp-admin")
    session_secret = os.environ["ADMIN_SESSION_SECRET"]
    host = os.environ.get("ADMIN_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("ADMIN_HTTP_PORT", "8766"))
    db_path = os.environ.get("TOKEN_DB_PATH", "/data/tokens.db")

    token_store = TokenStore(db_path)
    app = build_app(token_store, session_secret)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
