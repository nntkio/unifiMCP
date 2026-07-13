# HTTP Transport + Token Admin Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Streamable HTTP transport to the UnifiMCP server (alongside the existing stdio transport), protected by per-user, revocable, expiring bearer tokens managed through a separate SQLite-backed admin web service, and deploy both as Docker Compose services.

**Architecture:** `src/unifi_mcp/tokens.py` holds a `TokenStore` class (SQLite, WAL mode) shared by two processes: `unifi-mcp` (existing MCP server, gains an HTTP transport in `server/_http.py` that validates bearer tokens via `TokenStore.validate`) and a new `unifi-mcp-admin` service (`src/unifi_mcp/admin/`, a small Starlette app with login + token CRUD, run from the *same* Docker image via a different `command:`). Both share a Docker named volume holding the SQLite file.

**Tech Stack:** Python 3.13, `mcp` 1.28.1 (Streamable HTTP transport), Starlette + uvicorn (ASGI), `argon2-cffi` (password hashing), Jinja2 (server-rendered templates), `itsdangerous` (signed session cookies, via Starlette's `SessionMiddleware`), SQLite (stdlib `sqlite3`), pytest/pytest-asyncio/ruff (existing project tooling).

## Global Constraints

- Python `>=3.13` (per `pyproject.toml`); no `from __future__ import annotations` — existing code (e.g. `server/__init__.py`) uses native `X | None` syntax directly and new files should match.
- `ruff` config selects `E, W, F, I, B, C4, UP` and ignores `E501`; import order groups stdlib → third-party → first-party (`known-first-party = ["unifi_mcp"]`).
- All new runtime deps (`starlette`, `uvicorn`, `argon2-cffi`, `jinja2`, `itsdangerous`) go in `pyproject.toml`'s base `dependencies` list, not `[project.optional-dependencies] dev` — both console scripts need them at runtime, not just for tests.
- Existing stdio behavior (`MCP_TRANSPORT` unset or `stdio`) must be unaffected — this is an additive change.
- Test files follow existing conventions: `pytest.mark.asyncio` where async, class-per-concern grouping (see `tests/test_server_registry.py`), Arrange/Act/Assert with a blank line between each.
- Run `pytest`, `ruff check .`, and `ruff format .` before every commit in this plan (per `CLAUDE.md`).

---

### Task 1: Add new runtime dependencies

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `starlette`, `uvicorn`, `argon2-cffi`, `jinja2`, `itsdangerous` importable as `starlette`, `uvicorn`, `argon2`, `jinja2`, `itsdangerous` respectively, for every later task in this plan.

- [ ] **Step 1: Add the dependencies**

Edit `pyproject.toml`'s `dependencies` list:

```toml
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "starlette>=0.40.0",
    "uvicorn>=0.31.0",
    "argon2-cffi>=23.1.0",
    "jinja2>=3.1.0",
    "itsdangerous>=2.2.0",
]
```

- [ ] **Step 2: Install and verify**

Run: `uv pip install -e ".[dev]"`
Expected: install succeeds, no errors.

Run: `python3 -c "import starlette, uvicorn, argon2, jinja2, itsdangerous; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "Add starlette, uvicorn, argon2-cffi, jinja2, itsdangerous dependencies"
```

---

### Task 2: `TokenStore` — shared SQLite-backed accounts/tokens store

**Files:**
- Create: `src/unifi_mcp/tokens.py`
- Test: `tests/test_tokens_store.py`

**Interfaces:**
- Produces (consumed by Tasks 3, 5, 6):
  - `class AccountExistsError(Exception)`
  - `class TokenNotOwnedError(Exception)`
  - `class TokenRecord` — dataclass with fields `id: int, owner_id: int, owner_username: str, label: str, created_at: str, expires_at: str | None, revoked_at: str | None`
  - `class TokenStore:`
    - `__init__(self, db_path: str | Path) -> None` — creates schema if missing; raises on an unwritable path.
    - `create_account(self, username: str, password: str) -> int` — raises `AccountExistsError` on duplicate username.
    - `verify_account_password(self, username: str, password: str) -> int | None`
    - `create_token(self, owner_id: int, label: str, expires_at: str | None) -> str` — returns the raw token (only time it's ever available in plaintext).
    - `list_tokens(self, owner_id: int | None = None) -> list[TokenRecord]` — all tokens if `owner_id` is `None`, else just that owner's, newest first.
    - `revoke_token(self, token_id: int, requesting_owner_id: int | None) -> None` — `requesting_owner_id=None` bypasses the ownership check (used by root); raises `TokenNotOwnedError` if the token doesn't exist or belongs to someone else.
    - `validate(self, raw_token: str) -> bool` — `True` only for a token that exists, isn't revoked, and isn't expired. Never raises — any `sqlite3.Error` is treated as invalid (fail closed).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tokens_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tokens_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'unifi_mcp.tokens'`

- [ ] **Step 3: Implement `TokenStore`**

Create `src/unifi_mcp/tokens.py`:

```python
"""Shared SQLite-backed store for accounts and their bearer tokens.

Used by both the MCP server's HTTP transport (server/_http.py, read-only
validation) and the token-admin web service (admin/, read-write account and
token management) — two separate processes reading/writing the same file.
"""

import hashlib
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import argon2
from argon2.exceptions import VerifyMismatchError

_hasher = argon2.PasswordHasher()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES accounts(id),
    label TEXT NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    revoked_at TEXT
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass
class TokenRecord:
    id: int
    owner_id: int
    owner_username: str
    label: str
    created_at: str
    expires_at: str | None
    revoked_at: str | None


class AccountExistsError(Exception):
    """Raised when creating an account with a username that's already taken."""


class TokenNotOwnedError(Exception):
    """Raised when revoking a token that doesn't exist or isn't owned by the requester."""


class TokenStore:
    """SQLite-backed storage for accounts and their bearer tokens."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def create_account(self, username: str, password: str) -> int:
        password_hash = _hasher.hash(password)
        with closing(self._connect()) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO accounts (username, password_hash, created_at) "
                    "VALUES (?, ?, ?)",
                    (username, password_hash, _now()),
                )
            except sqlite3.IntegrityError as e:
                raise AccountExistsError(username) from e
            conn.commit()
            return cursor.lastrowid

    def verify_account_password(self, username: str, password: str) -> int | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id, password_hash FROM accounts WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        try:
            _hasher.verify(row["password_hash"], password)
        except VerifyMismatchError:
            return None
        return row["id"]

    def create_token(self, owner_id: int, label: str, expires_at: str | None) -> str:
        raw_token = secrets.token_urlsafe(32)
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO tokens (owner_id, label, token_hash, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (owner_id, label, _hash_token(raw_token), _now(), expires_at),
            )
            conn.commit()
        return raw_token

    def list_tokens(self, owner_id: int | None = None) -> list[TokenRecord]:
        query = (
            "SELECT tokens.id, tokens.owner_id, "
            "accounts.username AS owner_username, tokens.label, "
            "tokens.created_at, tokens.expires_at, tokens.revoked_at "
            "FROM tokens JOIN accounts ON accounts.id = tokens.owner_id"
        )
        params: tuple[int, ...] = ()
        if owner_id is not None:
            query += " WHERE tokens.owner_id = ?"
            params = (owner_id,)
        query += " ORDER BY tokens.created_at DESC"
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [TokenRecord(**dict(row)) for row in rows]

    def revoke_token(self, token_id: int, requesting_owner_id: int | None) -> None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT owner_id FROM tokens WHERE id = ?", (token_id,)
            ).fetchone()
            if row is None:
                raise TokenNotOwnedError(token_id)
            owner_mismatch = (
                requesting_owner_id is not None
                and row["owner_id"] != requesting_owner_id
            )
            if owner_mismatch:
                raise TokenNotOwnedError(token_id)
            conn.execute(
                "UPDATE tokens SET revoked_at = ? WHERE id = ?", (_now(), token_id)
            )
            conn.commit()

    def validate(self, raw_token: str) -> bool:
        token_hash = _hash_token(raw_token)
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT expires_at, revoked_at FROM tokens WHERE token_hash = ?",
                    (token_hash,),
                ).fetchone()
        except sqlite3.Error:
            return False
        if row is None or row["revoked_at"] is not None:
            return False
        if row["expires_at"] is not None and row["expires_at"] <= _now():
            return False
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tokens_store.py -v`
Expected: PASS (16 tests).

- [ ] **Step 5: Lint**

Run: `ruff check src/unifi_mcp/tokens.py tests/test_tokens_store.py && ruff format src/unifi_mcp/tokens.py tests/test_tokens_store.py`
Expected: no errors; files unchanged or auto-formatted cleanly.

- [ ] **Step 6: Commit**

```bash
git add src/unifi_mcp/tokens.py tests/test_tokens_store.py
git commit -m "Add shared SQLite-backed TokenStore for accounts and bearer tokens"
```

---

### Task 3: Streamable HTTP transport (`server/_http.py`)

**Files:**
- Create: `src/unifi_mcp/server/_http.py`
- Test: `tests/test_server_http.py` (this task writes the transport-only test classes; Task 4 adds a dispatch test class to the same file)

**Interfaces:**
- Consumes: `unifi_mcp.tokens.TokenStore` (`__init__`, `validate`) from Task 2.
- Produces (consumed by Task 4):
  - `class BearerAuthMiddleware(starlette.middleware.base.BaseHTTPMiddleware)` — `__init__(self, app, token_store: TokenStore)`.
  - `build_app(mcp_server: mcp.server.Server, token_store: TokenStore, on_shutdown: Callable[[], Awaitable[None]]) -> starlette.applications.Starlette`
  - `run_http(mcp_server: mcp.server.Server, on_shutdown: Callable[[], Awaitable[None]]) -> None` — reads `MCP_HTTP_HOST` (default `0.0.0.0`), `MCP_HTTP_PORT` (default `8765`), `TOKEN_DB_PATH` (default `/data/tokens.db`) from the environment.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_server_http.py`:

```python
"""Tests for the Streamable HTTP transport (server/_http.py)."""

from unittest.mock import AsyncMock

import pytest
from mcp.server import Server
from starlette.testclient import TestClient

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server_http.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'unifi_mcp.server._http'`

- [ ] **Step 3: Implement `server/_http.py`**

Create `src/unifi_mcp/server/_http.py`:

```python
"""Streamable HTTP transport for the UniFi MCP server.

Wraps the existing low-level `mcp.server.Server` in a Starlette ASGI app,
protected by a bearer-token check against the shared `TokenStore`.
"""

import os
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import uvicorn
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from unifi_mcp.tokens import TokenStore

HEALTH_PATH = "/healthz"


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Requires a valid bearer token (checked via TokenStore) on every path
    except HEALTH_PATH."""

    def __init__(self, app, token_store: TokenStore) -> None:
        super().__init__(app)
        self._token_store = token_store

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path == HEALTH_PATH:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        scheme, _, raw_token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not raw_token:
            return PlainTextResponse("Unauthorized", status_code=401)
        if not self._token_store.validate(raw_token):
            return PlainTextResponse("Unauthorized", status_code=401)
        return await call_next(request)


async def _healthz(_request: Request) -> Response:
    return PlainTextResponse("ok")


def build_app(
    mcp_server: Server,
    token_store: TokenStore,
    on_shutdown: Callable[[], Awaitable[None]],
) -> Starlette:
    session_manager = StreamableHTTPSessionManager(app=mcp_server)

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    async def lifespan(_app: Starlette):
        async with session_manager.run():
            try:
                yield
            finally:
                await on_shutdown()

    return Starlette(
        routes=[
            Route(HEALTH_PATH, _healthz),
            Mount("/mcp", app=handle_mcp),
        ],
        middleware=[Middleware(BearerAuthMiddleware, token_store=token_store)],
        lifespan=lifespan,
    )


def run_http(
    mcp_server: Server, on_shutdown: Callable[[], Awaitable[None]]
) -> None:
    """Run the MCP server over Streamable HTTP.

    Reads MCP_HTTP_HOST (default 0.0.0.0), MCP_HTTP_PORT (default 8765), and
    TOKEN_DB_PATH (default /data/tokens.db) from the environment.
    """
    host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_HTTP_PORT", "8765"))
    db_path = os.environ.get("TOKEN_DB_PATH", "/data/tokens.db")

    token_store = TokenStore(db_path)
    app = build_app(mcp_server, token_store, on_shutdown)
    uvicorn.run(app, host=host, port=port)
```

Note: `lifespan` is an async generator function used directly as Starlette's
`lifespan` argument (Starlette accepts a plain async-generator callable here
without requiring `@asynccontextmanager`); no extra import is needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server_http.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint**

Run: `ruff check src/unifi_mcp/server/_http.py tests/test_server_http.py && ruff format src/unifi_mcp/server/_http.py tests/test_server_http.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/unifi_mcp/server/_http.py tests/test_server_http.py
git commit -m "Add Streamable HTTP transport with TokenStore-backed bearer auth"
```

---

### Task 4: Wire `MCP_TRANSPORT` dispatch into `main()`

**Files:**
- Modify: `src/unifi_mcp/server/__init__.py:9` (imports), `src/unifi_mcp/server/__init__.py:135-149` (`main()`)
- Modify: `tests/test_server_http.py` (add dispatch test class)
- Modify: `.env.example`

**Interfaces:**
- Consumes: `unifi_mcp.server._http.run_http` (Task 3).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server_http.py`:

```python
import os
from unittest.mock import patch

from unifi_mcp import server as server_module
```

(add these imports to the existing top-of-file import block, alongside the
`unittest.mock` import already there — the file should end up importing both
`AsyncMock` and `patch` from `unittest.mock`, plus `os` and `server_module`.)

Then add this class at the end of `tests/test_server_http.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server_http.py::TestMainTransportDispatch -v`
Expected: FAIL — `test_main_dispatches_to_http_when_configured` fails because
`main()` currently always runs the stdio path (it will hang or the mock
`run_http` is never called, so `assert_called_once_with` raises).

- [ ] **Step 3: Wire the dispatch**

In `src/unifi_mcp/server/__init__.py`, add `import os` to the top import
block (after `import asyncio` on line 9):

```python
import asyncio
import os
from typing import Any
```

Then replace `main()` (lines 135-149):

```python
def main() -> None:
    """Run the MCP server."""

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            try:
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
            finally:
                await _close_client()

    asyncio.run(run())
```

with:

```python
def main() -> None:
    """Run the MCP server using the transport selected by MCP_TRANSPORT."""
    if os.environ.get("MCP_TRANSPORT", "stdio") == "http":
        from unifi_mcp.server._http import run_http

        run_http(server, _close_client)
        return

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            try:
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
            finally:
                await _close_client()

    asyncio.run(run())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server_http.py -v`
Expected: PASS (8 tests total in the file).

Run: `pytest tests/ -v`
Expected: PASS — full existing suite still green (confirms `main()`'s stdio
path and everything else is unaffected).

- [ ] **Step 5: Update `.env.example`**

Append to `.env.example`:

```bash

# --- HTTP transport (optional; defaults to stdio if unset) ---

# Transport mode: "stdio" (default, for local/Claude Desktop use) or "http"
# (for a persistent network service, e.g. QNAP/Docker deployment)
MCP_TRANSPORT=stdio

# HTTP transport bind host/port (only used when MCP_TRANSPORT=http)
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8765

# Path to the shared SQLite token database (only used when MCP_TRANSPORT=http;
# see the token-admin service for how tokens are created)
TOKEN_DB_PATH=/data/tokens.db
```

- [ ] **Step 6: Lint**

Run: `ruff check src/unifi_mcp/server/__init__.py tests/test_server_http.py && ruff format src/unifi_mcp/server/__init__.py tests/test_server_http.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/unifi_mcp/server/__init__.py tests/test_server_http.py .env.example
git commit -m "Dispatch main() to the HTTP transport when MCP_TRANSPORT=http"
```

---

### Task 5: Admin auth helpers (root credential check + CSRF)

**Files:**
- Create: `src/unifi_mcp/admin/__init__.py` (empty in this task — populated in Task 6)
- Create: `src/unifi_mcp/admin/auth.py`
- Test: `tests/test_admin_app.py` (this task writes the auth-only test classes; Task 6 appends route test classes to the same file)

**Interfaces:**
- Produces (consumed by Task 6):
  - `check_root_credentials(username: str, password: str) -> bool` — reads `ROOT_ADMIN_USERNAME` (default `"root"`) and `ROOT_ADMIN_PASSWORD` (required — raises `KeyError` if unset) from the environment.
  - `generate_csrf_token() -> str`
  - `csrf_token_valid(session_token: str | None, submitted_token: str | None) -> bool`

- [ ] **Step 1: Create the package and write the failing tests**

Create `src/unifi_mcp/admin/__init__.py` (empty for now):

```python
"""Token-admin web service: login + bearer-token management UI."""
```

Create `tests/test_admin_app.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_admin_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'unifi_mcp.admin.auth'`

- [ ] **Step 3: Implement `admin/auth.py`**

Create `src/unifi_mcp/admin/auth.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_admin_app.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Lint**

Run: `ruff check src/unifi_mcp/admin/ tests/test_admin_app.py && ruff format src/unifi_mcp/admin/ tests/test_admin_app.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/unifi_mcp/admin/__init__.py src/unifi_mcp/admin/auth.py tests/test_admin_app.py
git commit -m "Add root-credential check and CSRF helpers for the admin service"
```

---

### Task 6: Admin routes, templates, and console-script entry point

**Files:**
- Create: `src/unifi_mcp/admin/app.py`
- Create: `src/unifi_mcp/admin/templates/login.html`
- Create: `src/unifi_mcp/admin/templates/tokens.html`
- Create: `src/unifi_mcp/admin/templates/admin.html`
- Modify: `src/unifi_mcp/admin/__init__.py` (add `main()`)
- Modify: `pyproject.toml` (add `unifi-mcp-admin` console script)
- Modify: `tests/test_admin_app.py` (append route test classes)
- Modify: `.env.example`

**Interfaces:**
- Consumes: `unifi_mcp.tokens.TokenStore`, `AccountExistsError`, `TokenNotOwnedError` (Task 2); `check_root_credentials`, `csrf_token_valid`, `generate_csrf_token` (Task 5).
- Produces:
  - `build_app(token_store: TokenStore, session_secret: str) -> starlette.applications.Starlette` (in `admin/app.py`)
  - `main() -> None` (in `admin/__init__.py`) — console-script entry point; reads `ROOT_ADMIN_PASSWORD` (required), `ADMIN_SESSION_SECRET` (required), `ADMIN_HTTP_HOST` (default `0.0.0.0`), `ADMIN_HTTP_PORT` (default `8766`), `TOKEN_DB_PATH` (default `/data/tokens.db`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_admin_app.py` (add these imports to the top-of-file
import block first):

```python
import re

from starlette.testclient import TestClient

from unifi_mcp.admin.app import build_app
from unifi_mcp.tokens import TokenStore


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf_token field not found in response HTML"
    return match.group(1)
```

Then add these fixtures and test classes at the end of the file:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_admin_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'unifi_mcp.admin.app'`

- [ ] **Step 3: Create the templates**

Create `src/unifi_mcp/admin/templates/login.html`:

```html
<!doctype html>
<html>
<head><title>UnifiMCP Token Admin — Log in</title></head>
<body>
  <h1>Log in</h1>
  {% if error %}<p style="color: red;">{{ error }}</p>{% endif %}
  <form method="post" action="/login">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <label>Username <input type="text" name="username" required></label><br>
    <label>Password <input type="password" name="password" required></label><br>
    <button type="submit">Log in</button>
  </form>
</body>
</html>
```

Create `src/unifi_mcp/admin/templates/tokens.html`:

```html
<!doctype html>
<html>
<head><title>My Tokens — UnifiMCP Token Admin</title></head>
<body>
  <h1>My Tokens</h1>
  <form method="post" action="/logout"><button type="submit">Log out</button></form>

  {% if error %}<p style="color: red;">{{ error }}</p>{% endif %}
  {% if new_token %}
    <p style="color: green;">
      New token — copy it now, it will not be shown again:<br>
      <code>{{ new_token }}</code>
    </p>
  {% endif %}

  <h2>Create a token</h2>
  <form method="post" action="/tokens">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <label>Label <input type="text" name="label" required></label><br>
    <label>Expiry
      <select name="expiry_preset">
        <option value="30d">30 days</option>
        <option value="90d">90 days</option>
        <option value="365d">365 days</option>
        <option value="never">Never</option>
        <option value="custom">Custom date</option>
      </select>
    </label>
    <label>Custom date (if "Custom date" selected above)
      <input type="date" name="custom_date">
    </label><br>
    <button type="submit">Create token</button>
  </form>

  <h2>Existing tokens</h2>
  <table border="1">
    <tr><th>Label</th><th>Created</th><th>Expires</th><th>Revoked</th><th></th></tr>
    {% for token in tokens %}
    <tr>
      <td>{{ token.label }}</td>
      <td>{{ token.created_at }}</td>
      <td>{{ token.expires_at or "Never" }}</td>
      <td>{{ token.revoked_at or "Active" }}</td>
      <td>
        {% if not token.revoked_at %}
        <form method="post" action="/tokens/{{ token.id }}/revoke">
          <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
          <button type="submit">Revoke</button>
        </form>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
```

Create `src/unifi_mcp/admin/templates/admin.html`:

```html
<!doctype html>
<html>
<head><title>Admin — UnifiMCP Token Admin</title></head>
<body>
  <h1>Admin</h1>
  <form method="post" action="/logout"><button type="submit">Log out</button></form>

  {% if error %}<p style="color: red;">{{ error }}</p>{% endif %}

  <h2>Create an account</h2>
  <form method="post" action="/admin/accounts">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <label>Username <input type="text" name="username" required></label><br>
    <label>Temporary password
      <input type="text" name="temp_password" required>
    </label><br>
    <button type="submit">Create account</button>
  </form>

  <h2>All tokens</h2>
  <table border="1">
    <tr>
      <th>Owner</th><th>Label</th><th>Created</th><th>Expires</th>
      <th>Revoked</th><th></th>
    </tr>
    {% for token in tokens %}
    <tr>
      <td>{{ token.owner_username }}</td>
      <td>{{ token.label }}</td>
      <td>{{ token.created_at }}</td>
      <td>{{ token.expires_at or "Never" }}</td>
      <td>{{ token.revoked_at or "Active" }}</td>
      <td>
        {% if not token.revoked_at %}
        <form method="post" action="/admin/tokens/{{ token.id }}/revoke">
          <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
          <button type="submit">Revoke</button>
        </form>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
```

- [ ] **Step 4: Implement `admin/app.py`**

Create `src/unifi_mcp/admin/app.py`:

```python
"""Routes for the token-admin service: login, token CRUD, account creation."""

import os
from datetime import UTC, datetime, timedelta

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from unifi_mcp.admin.auth import (
    check_root_credentials,
    csrf_token_valid,
    generate_csrf_token,
)
from unifi_mcp.tokens import AccountExistsError, TokenNotOwnedError, TokenStore

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

_EXPIRY_PRESET_DAYS = {"30d": 30, "90d": 90, "365d": 365, "never": None}


def _csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return token


async def login_form(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "login.html", {"csrf_token": _csrf_token(request), "error": None}
    )


async def login_submit(request: Request) -> Response:
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    submitted_csrf = str(form.get("csrf_token", ""))

    if not csrf_token_valid(request.session.get("csrf_token"), submitted_csrf):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"csrf_token": _csrf_token(request), "error": "Invalid form submission."},
            status_code=403,
        )

    if check_root_credentials(username, password):
        request.session["role"] = "root"
        return RedirectResponse("/admin", status_code=303)

    token_store: TokenStore = request.app.state.token_store
    account_id = token_store.verify_account_password(username, password)
    if account_id is not None:
        request.session["user_id"] = account_id
        return RedirectResponse("/tokens", status_code=303)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"csrf_token": _csrf_token(request), "error": "Invalid username or password."},
        status_code=401,
    )


async def logout(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


def _require_root(request: Request) -> Response | None:
    if request.session.get("role") != "root":
        return RedirectResponse("/login", status_code=303)
    return None


def _require_user(request: Request) -> int | Response:
    user_id = request.session.get("user_id")
    if user_id is None:
        return RedirectResponse("/login", status_code=303)
    return user_id


async def admin_home(request: Request) -> Response:
    redirect = _require_root(request)
    if redirect is not None:
        return redirect

    token_store: TokenStore = request.app.state.token_store
    tokens = token_store.list_tokens(owner_id=None)
    return templates.TemplateResponse(
        request,
        "admin.html",
        {"csrf_token": _csrf_token(request), "tokens": tokens, "error": None},
    )


async def admin_create_account(request: Request) -> Response:
    redirect = _require_root(request)
    if redirect is not None:
        return redirect

    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("temp_password", ""))
    submitted_csrf = str(form.get("csrf_token", ""))
    token_store: TokenStore = request.app.state.token_store

    if not csrf_token_valid(request.session.get("csrf_token"), submitted_csrf):
        tokens = token_store.list_tokens(owner_id=None)
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "csrf_token": _csrf_token(request),
                "tokens": tokens,
                "error": "Invalid form submission.",
            },
            status_code=403,
        )

    try:
        token_store.create_account(username, password)
    except AccountExistsError:
        tokens = token_store.list_tokens(owner_id=None)
        return templates.TemplateResponse(
            request,
            "admin.html",
            {
                "csrf_token": _csrf_token(request),
                "tokens": tokens,
                "error": f"Username '{username}' already exists.",
            },
            status_code=409,
        )

    return RedirectResponse("/admin", status_code=303)


async def admin_revoke_token(request: Request) -> Response:
    redirect = _require_root(request)
    if redirect is not None:
        return redirect

    form = await request.form()
    submitted_csrf = str(form.get("csrf_token", ""))
    if not csrf_token_valid(request.session.get("csrf_token"), submitted_csrf):
        return Response("Invalid form submission.", status_code=403)

    token_store: TokenStore = request.app.state.token_store
    token_id = int(request.path_params["token_id"])
    try:
        token_store.revoke_token(token_id, requesting_owner_id=None)
    except TokenNotOwnedError:
        return Response("Not found.", status_code=404)
    return RedirectResponse("/admin", status_code=303)


async def tokens_home(request: Request) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id

    token_store: TokenStore = request.app.state.token_store
    tokens = token_store.list_tokens(owner_id=user_id)
    return templates.TemplateResponse(
        request,
        "tokens.html",
        {
            "csrf_token": _csrf_token(request),
            "tokens": tokens,
            "error": None,
            "new_token": request.session.pop("new_token", None),
        },
    )


def _compute_expiry(form) -> str | None:
    preset = form.get("expiry_preset", "never")
    if preset == "custom":
        custom_date = str(form.get("custom_date", ""))
        expiry = datetime.fromisoformat(custom_date).replace(tzinfo=UTC)
        return expiry.isoformat()
    days = _EXPIRY_PRESET_DAYS.get(preset)
    if days is None:
        return None
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def tokens_create(request: Request) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id

    form = await request.form()
    submitted_csrf = str(form.get("csrf_token", ""))
    token_store: TokenStore = request.app.state.token_store

    if not csrf_token_valid(request.session.get("csrf_token"), submitted_csrf):
        tokens = token_store.list_tokens(owner_id=user_id)
        return templates.TemplateResponse(
            request,
            "tokens.html",
            {
                "csrf_token": _csrf_token(request),
                "tokens": tokens,
                "error": "Invalid form submission.",
                "new_token": None,
            },
            status_code=403,
        )

    label = str(form.get("label", "")).strip() or "unnamed token"
    expires_at = _compute_expiry(form)
    raw_token = token_store.create_token(user_id, label, expires_at)
    request.session["new_token"] = raw_token
    return RedirectResponse("/tokens", status_code=303)


async def tokens_revoke(request: Request) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id

    form = await request.form()
    submitted_csrf = str(form.get("csrf_token", ""))
    if not csrf_token_valid(request.session.get("csrf_token"), submitted_csrf):
        return Response("Invalid form submission.", status_code=403)

    token_store: TokenStore = request.app.state.token_store
    token_id = int(request.path_params["token_id"])
    try:
        token_store.revoke_token(token_id, requesting_owner_id=user_id)
    except TokenNotOwnedError:
        return Response("Forbidden.", status_code=403)
    return RedirectResponse("/tokens", status_code=303)


def build_app(token_store: TokenStore, session_secret: str) -> Starlette:
    app = Starlette(
        routes=[
            Route("/login", login_form, methods=["GET"]),
            Route("/login", login_submit, methods=["POST"]),
            Route("/logout", logout, methods=["POST"]),
            Route("/admin", admin_home, methods=["GET"]),
            Route("/admin/accounts", admin_create_account, methods=["POST"]),
            Route(
                "/admin/tokens/{token_id:int}/revoke",
                admin_revoke_token,
                methods=["POST"],
            ),
            Route("/tokens", tokens_home, methods=["GET"]),
            Route("/tokens", tokens_create, methods=["POST"]),
            Route("/tokens/{token_id:int}/revoke", tokens_revoke, methods=["POST"]),
        ],
        middleware=[Middleware(SessionMiddleware, secret_key=session_secret)],
    )
    app.state.token_store = token_store
    return app
```

- [ ] **Step 5: Implement `admin/__init__.py`'s `main()`**

Replace the contents of `src/unifi_mcp/admin/__init__.py`:

```python
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
```

- [ ] **Step 6: Add the console-script entry point**

In `pyproject.toml`, update `[project.scripts]`:

```toml
[project.scripts]
unifi-mcp = "unifi_mcp.server:main"
unifi-mcp-admin = "unifi_mcp.admin:main"
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv pip install -e ".[dev]"` (re-run so the new console script is registered)
Expected: succeeds.

Run: `pytest tests/test_admin_app.py -v`
Expected: PASS (17 tests total in the file).

Run: `pytest tests/ -v`
Expected: PASS — full suite green.

- [ ] **Step 8: Update `.env.example`**

Append to `.env.example`:

```bash

# --- Token-admin service (unifi-mcp-admin) ---

# Root admin identity: env-var only, no database row, so root can never own
# a bearer token. Used to log in to the admin UI and create accounts for
# other people, who then create/manage their own tokens.
ROOT_ADMIN_USERNAME=root
ROOT_ADMIN_PASSWORD=change-me-to-a-strong-password

# Signs the admin service's session cookies (generate with, e.g.,
# `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`)
ADMIN_SESSION_SECRET=

ADMIN_HTTP_HOST=0.0.0.0
ADMIN_HTTP_PORT=8766
```

- [ ] **Step 9: Lint**

Run: `ruff check src/unifi_mcp/admin/ tests/test_admin_app.py && ruff format src/unifi_mcp/admin/ tests/test_admin_app.py`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add src/unifi_mcp/admin/ tests/test_admin_app.py pyproject.toml .env.example
git commit -m "Add token-admin routes, templates, and console-script entry point"
```

---

### Task 7: Docker Compose changes

**Files:**
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `unifi-mcp` image (existing `Dockerfile`, unchanged — both console
  scripts are registered by the `pyproject.toml` changes in Tasks 1-6, so no
  Dockerfile edit is needed), `unifi-mcp-admin` console script (Task 6).

- [ ] **Step 1: Rewrite `docker-compose.yml`**

Replace the full contents of `docker-compose.yml`:

```yaml
services:
  unifi-mcp:
    build: .
    image: unifi-mcp:latest
    container_name: unifi-mcp
    env_file:
      - .env
    ports:
      - "8765:8765"
    volumes:
      - unifi-mcp-data:/data
    healthcheck:
      test:
        [
          "CMD",
          "python3",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:8765/healthz')",
        ]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  unifi-mcp-admin:
    image: unifi-mcp:latest
    container_name: unifi-mcp-admin
    command: ["unifi-mcp-admin"]
    env_file:
      - .env
    ports:
      - "8766:8766"
    volumes:
      - unifi-mcp-data:/data
    restart: unless-stopped

volumes:
  unifi-mcp-data:
```

Note: `unifi-mcp-admin` has no `build:` directive — it reuses the image built
by the `unifi-mcp` service's `build: .` (both reference the same
`unifi-mcp:latest` tag), so `docker compose build` only needs to build once.

The `stdin_open`/`tty` keys from the original file are intentionally removed:
they were needed for the stdio transport (a client attaching to the
container's stdin), which is no longer how this Compose deployment runs the
server — `unifi-mcp` now runs with `MCP_TRANSPORT=http` set in `.env`,
serving over the network instead.

- [ ] **Step 2: Validate the compose file**

Run: `docker compose config --quiet`
Expected: no output, exit code 0 (confirms valid YAML/schema; does not
require `.env` to have real UniFi credentials, just needs the file to
exist — copy `.env.example` to `.env` first if you don't have one locally).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "Add unifi-mcp-admin service and shared token volume to docker-compose.yml"
```

---

### Task 8: Documentation and final full-repo verification

**Files:**
- Modify: `README.md`
- Modify: `docs/usage-guide.md`

- [ ] **Step 1: Update `README.md`**

Replace the "Development" section heading context by inserting a new section
before it. Find this text in `README.md`:

`````markdown
## Development

```bash
# Run tests
pytest
```
`````

Insert a new section immediately before `## Development` (i.e. right after
the `## Available Tools` table ends and before the `## Development` line):

`````markdown
## Running as a Network Service (HTTP Transport)

By default the server speaks MCP over stdio (a local subprocess). It can
also run as a persistent Streamable HTTP service — e.g. for a Docker/QNAP
deployment reachable over the LAN — by setting `MCP_TRANSPORT=http`.

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | `stdio` or `http` | `stdio` |
| `MCP_HTTP_HOST` | Bind host (HTTP mode only) | `0.0.0.0` |
| `MCP_HTTP_PORT` | Bind port (HTTP mode only) | `8765` |
| `TOKEN_DB_PATH` | Path to the shared SQLite token database (HTTP mode only) | `/data/tokens.db` |

In HTTP mode, the server exposes:
- `POST/GET /mcp` — the MCP Streamable HTTP endpoint, requires
  `Authorization: Bearer <token>`
- `GET /healthz` — unauthenticated health check, used by Docker's healthcheck

Tokens aren't configured directly — they're created through the separate
**token-admin service** (`unifi-mcp-admin`, included in `docker-compose.yml`).
See its section below for how to log in and mint a token.

An MCP client pointed at a remote Streamable HTTP server (instead of
spawning a local subprocess) typically needs a URL and a bearer token,
e.g.:

```json
{
  "mcpServers": {
    "unifi": {
      "url": "http://172.16.25.50:8765/mcp",
      "headers": {
        "Authorization": "Bearer <token from the token-admin service>"
      }
    }
  }
}
```

(Check your specific MCP client's documentation for its exact remote-server
config format — the shape above is illustrative.)

## Token Admin Service

`unifi-mcp-admin` is a small web UI for creating and revoking the bearer
tokens the HTTP transport above requires. It shares a SQLite database
(`TOKEN_DB_PATH`) with the `unifi-mcp` service via a Docker volume.

| Variable | Description | Default |
|----------|-------------|---------|
| `ROOT_ADMIN_USERNAME` | Root admin login username | `root` |
| `ROOT_ADMIN_PASSWORD` | Root admin login password (required) | - |
| `ADMIN_SESSION_SECRET` | Signs session cookies (required) | - |
| `ADMIN_HTTP_HOST` | Bind host | `0.0.0.0` |
| `ADMIN_HTTP_PORT` | Bind port | `8766` |

Root has no account of its own to hold a token — it exists only to create
accounts for trusted people at `http://<host>:8766/admin`. Each person then
logs in at `http://<host>:8766/login` to create, view, and revoke their own
tokens at `/tokens`. A newly created token is shown exactly once — copy it
immediately, since only its hash is stored.

```bash
docker compose up -d
# then, in a browser:
#   http://<host>:8766/login   (log in as root, create an account)
#   http://<host>:8766/login   (log in as that account, create a token)
```
`````

- [ ] **Step 2: Update `docs/usage-guide.md`**

Edit the Overview section (line 13) — find:

```markdown
its local HTTP API and speaks MCP over stdio to the assistant.
```

Replace with:

```markdown
its local HTTP API and speaks MCP to the assistant, by default over stdio
(a local subprocess) — it can also run as a persistent Streamable HTTP
service; see [section 9](#9-running-as-a-network-service) below.
```

Edit the "Running the server" section (around line 127-129) — find:

```markdown
The server speaks newline-delimited JSON-RPC 2.0 over stdin/stdout (the MCP
stdio transport) — it will look like it's hanging, since it's waiting for a
client to send it requests. That's expected; Ctrl-C to stop it.
```

Replace with:

```markdown
By default the server speaks newline-delimited JSON-RPC 2.0 over
stdin/stdout (the MCP stdio transport) — it will look like it's hanging,
since it's waiting for a client to send it requests. That's expected;
Ctrl-C to stop it. For running it instead as a persistent network service,
see [section 9](#9-running-as-a-network-service).
```

Append a new section at the end of the file (after the existing
`## 8. Development` section):

```markdown
## 9. Running as a network service

Instead of stdio, the server can run as a persistent Streamable HTTP
service — the setup used for the Docker Compose deployment in this repo.
Set `MCP_TRANSPORT=http` (see `.env.example` for the full list of
`MCP_HTTP_*`/`TOKEN_DB_PATH` variables this enables).

Bearer tokens for the HTTP endpoint are managed through a separate
`unifi-mcp-admin` service (also started by `docker compose up -d`) — a root
account (`ROOT_ADMIN_USERNAME`/`ROOT_ADMIN_PASSWORD`) logs in to create
accounts for trusted people, who each log in themselves to create, view,
and revoke their own tokens. See the "Token Admin Service" section in
[`README.md`](../README.md) for the full walkthrough.
```

- [ ] **Step 3: Full-repo verification**

Run: `pytest`
Expected: PASS — entire suite green.

Run: `ruff check .`
Expected: no errors.

Run: `ruff format --check .`
Expected: no files need reformatting.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/usage-guide.md
git commit -m "Document the HTTP transport and token-admin service"
```
