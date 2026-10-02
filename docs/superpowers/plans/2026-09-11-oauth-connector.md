# Claude Connector OAuth Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Claude Desktop, claude.ai, and Claude mobile add this server as a custom connector by adding an OAuth 2.1 authorization server over the existing token store, and publish the endpoint through a Cloudflare Tunnel.

**Architecture:** The pinned `mcp` SDK (1.28.1) ships server-side OAuth handlers in `mcp.server.auth`; this work implements its `OAuthAuthorizationServerProvider` protocol against `TokenStore` and mounts its routes on the existing Starlette app. Access tokens issued by the OAuth flow are ordinary rows in the `tokens` table, so the bearer middleware, the admin UI, and the usage log keep working untouched. Everything is gated on a new `MCP_PUBLIC_URL`; unset, the server behaves exactly as it does today.

**Tech Stack:** Python 3.13, `mcp` 1.28.1 (`mcp.server.auth`), Starlette, Jinja2, SQLite, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-11-oauth-connector-design.md`

## Global Constraints

- Python 3.13+; `mcp>=1.28.1,<2`. No new runtime dependencies: Jinja2 and Starlette are already required.
- `ruff check .` and `ruff format .` must pass before every commit. Line length 88, `E501` ignored.
- `pytest` must pass before every commit. Baseline before this plan: 389 passed.
- Type hints on every function signature. PEP 8.
- One `server/_<domain>.py` per domain, with a matching `tests/test_server_<domain>.py`.
- With `MCP_PUBLIC_URL` unset, behaviour must be byte-for-byte today's, except that 401s from `/mcp` gain a bare `WWW-Authenticate: Bearer` header.
- Timestamps are ISO-8601 UTC strings produced by the existing `_now()`, matching every other column in `tokens.py`.
- Secrets (bearer tokens, authorization codes, refresh tokens) are stored only as SHA-256 hashes via the existing `_hash_token()`.
- Commit messages: imperative mood, no attribution trailer.
- Branch: `feature/oauth-connector` (already created; the spec is committed on it).

## Constants (Task 4 defines these once; later tasks import them)

```python
AUTHORIZATION_TTL = timedelta(minutes=10)
ACCESS_TOKEN_TTL = timedelta(hours=1)
GRANT_TTL = timedelta(days=30)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_PATH = "/oauth/login"
```

---

### Task 1: Token store — OAuth schema, client registry, token rotation

**Files:**
- Modify: `src/unifi_mcp/tokens.py`
- Test: `tests/test_tokens_store.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `TokenStore.get_token(token_id: int) -> TokenRecord | None`, `TokenStore.rotate_token(token_id: int, expires_at: str | None) -> str`, `TokenStore.save_oauth_client(client_id: str, client_json: str) -> None`, `TokenStore.get_oauth_client(client_id: str) -> str | None`. Three new tables in `_SCHEMA`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tokens_store.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tokens_store.py -k "OAuthClients or TokenRotation" -v`
Expected: FAIL with `AttributeError: 'TokenStore' object has no attribute 'get_oauth_client'`

- [ ] **Step 3: Add the schema**

In `src/unifi_mcp/tokens.py`, append to the `_SCHEMA` string, after the `usage_log` index:

```sql
-- OAuth clients registered by an MCP client through RFC 7591 dynamic
-- registration. client_json is the full OAuthClientInformationFull document.
CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id   TEXT PRIMARY KEY,
    client_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- One row per authorisation attempt, from /authorize until the code is
-- exchanged (row deleted) or it expires. owner_id and code_hash are set
-- when the user signs in successfully.
CREATE TABLE IF NOT EXISTS oauth_authorizations (
    id                    TEXT PRIMARY KEY,
    client_id             TEXT NOT NULL REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
    redirect_uri          TEXT NOT NULL,
    redirect_uri_explicit INTEGER NOT NULL,
    code_challenge        TEXT NOT NULL,
    state                 TEXT,
    scope                 TEXT NOT NULL DEFAULT '',
    resource              TEXT,
    created_at            TEXT NOT NULL,
    expires_at            TEXT NOT NULL,
    attempts              INTEGER NOT NULL DEFAULT 0,
    owner_id              INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    code_hash             TEXT UNIQUE
);

-- Refresh tokens for OAuth-issued access tokens. token_id points at the
-- tokens row the access token lives in, so revoking or deleting that row
-- takes the refresh token with it.
CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
    token_hash       TEXT PRIMARY KEY,
    token_id         INTEGER NOT NULL REFERENCES tokens(id) ON DELETE CASCADE,
    client_id        TEXT NOT NULL,
    scope            TEXT NOT NULL DEFAULT '',
    grant_expires_at TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
```

- [ ] **Step 4: Implement the methods**

Add a new exception next to the existing ones in `src/unifi_mcp/tokens.py`:

```python
class AuthorizationNotFoundError(Exception):
    """Raised when completing an authorisation that doesn't exist or has expired."""
```

Add to `TokenStore`, at the end of the tokens section (after `validate`):

```python
    def get_token(self, token_id: int) -> TokenRecord | None:
        """Return a token row by id, whatever its revoked/expired state."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                _TOKEN_SELECT + " WHERE tokens.id = ?", (token_id,)
            ).fetchone()
        return TokenRecord(**dict(row)) if row else None

    def rotate_token(self, token_id: int, expires_at: str | None) -> str:
        """Give an existing token row a new secret and expiry, and return it.

        Used when an OAuth refresh mints a new access token: keeping the row
        means the admin UI shows one entry per connector sign-in rather than
        one per hourly refresh, and the usage log stays attributed to it.
        """
        raw_token = secrets.token_urlsafe(32)
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "UPDATE tokens SET token_hash = ?, expires_at = ? "
                "WHERE id = ? AND revoked_at IS NULL",
                (_hash_token(raw_token), expires_at, token_id),
            )
            conn.commit()
        if cursor.rowcount == 0:
            raise TokenNotOwnedError(token_id)
        return raw_token

    # ── OAuth clients ─────────────────────────────────────────────────────

    def save_oauth_client(self, client_id: str, client_json: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO oauth_clients (client_id, client_json, created_at) "
                "VALUES (?, ?, ?) ON CONFLICT(client_id) DO UPDATE SET "
                "client_json = excluded.client_json",
                (client_id, client_json, _now()),
            )
            conn.commit()

    def get_oauth_client(self, client_id: str) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT client_json FROM oauth_clients WHERE client_id = ?",
                (client_id,),
            ).fetchone()
        return row["client_json"] if row else None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_tokens_store.py -v`
Expected: PASS, including every pre-existing test.

- [ ] **Step 6: Lint and commit**

```bash
ruff format . && ruff check .
git add src/unifi_mcp/tokens.py tests/test_tokens_store.py
git commit -m "Add OAuth tables, client registry, and token rotation to the store"
```

---

### Task 2: Token store — authorization rows

**Files:**
- Modify: `src/unifi_mcp/tokens.py`
- Test: `tests/test_tokens_store.py`

**Interfaces:**
- Consumes: `AuthorizationNotFoundError` and the `oauth_authorizations` table from Task 1.
- Produces: `AuthorizationRecord` dataclass with fields `id: str`, `client_id: str`, `redirect_uri: str`, `redirect_uri_explicit: bool`, `code_challenge: str`, `state: str | None`, `scope: str`, `resource: str | None`, `created_at: str`, `expires_at: str`, `attempts: int`, `owner_id: int | None`. Methods `create_authorization(*, client_id, redirect_uri, redirect_uri_explicit, code_challenge, state, scope, resource, expires_at) -> str`, `get_authorization(txn_id: str) -> AuthorizationRecord | None`, `fail_authorization_attempt(txn_id: str, max_attempts: int) -> int`, `complete_authorization(txn_id: str, owner_id: int) -> str`, `consume_authorization_code(raw_code: str) -> AuthorizationRecord | None`, `delete_authorization(txn_id: str) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tokens_store.py`:

```python
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
```

Add `AuthorizationNotFoundError` to the import list at the top of the test file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tokens_store.py -k Authorizations -v`
Expected: FAIL with `ImportError` on `AuthorizationNotFoundError`, or `AttributeError` on `create_authorization`.

- [ ] **Step 3: Implement the dataclass, helper, and methods**

Add the dataclass after `TokenRecord` in `src/unifi_mcp/tokens.py`:

```python
@dataclass
class AuthorizationRecord:
    """One pending OAuth authorisation, between /authorize and the code exchange."""

    id: str
    client_id: str
    redirect_uri: str
    redirect_uri_explicit: bool
    code_challenge: str
    state: str | None
    scope: str
    resource: str | None
    created_at: str
    expires_at: str
    attempts: int
    owner_id: int | None
```

Add the column list next to the other `_*_COLUMNS` constants:

```python
# code_hash is deliberately excluded: it never leaves the store.
_AUTHORIZATION_COLUMNS = (
    "id, client_id, redirect_uri, redirect_uri_explicit, code_challenge, state, "
    "scope, resource, created_at, expires_at, attempts, owner_id"
)
```

Add a row adapter next to `_hash_token`:

```python
def _authorization_from_row(row: sqlite3.Row) -> AuthorizationRecord:
    data = dict(row)
    data["redirect_uri_explicit"] = bool(data["redirect_uri_explicit"])
    return AuthorizationRecord(**data)
```

Add to `TokenStore` after the OAuth client methods:

```python
    # ── OAuth authorisations ──────────────────────────────────────────────

    def create_authorization(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        redirect_uri_explicit: bool,
        code_challenge: str,
        state: str | None,
        scope: str,
        resource: str | None,
        expires_at: str,
    ) -> str:
        """Start an authorisation and return its unguessable transaction id."""
        txn_id = secrets.token_urlsafe(32)
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO oauth_authorizations (id, client_id, redirect_uri, "
                "redirect_uri_explicit, code_challenge, state, scope, resource, "
                "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    txn_id,
                    client_id,
                    redirect_uri,
                    int(redirect_uri_explicit),
                    code_challenge,
                    state,
                    scope,
                    resource,
                    _now(),
                    expires_at,
                ),
            )
            conn.commit()
        return txn_id

    def get_authorization(self, txn_id: str) -> AuthorizationRecord | None:
        """Return a live authorisation. Expired rows are swept and read as None."""
        with closing(self._connect()) as conn:
            conn.execute(
                "DELETE FROM oauth_authorizations WHERE expires_at <= ?", (_now(),)
            )
            conn.commit()
            row = conn.execute(
                f"SELECT {_AUTHORIZATION_COLUMNS} FROM oauth_authorizations "
                "WHERE id = ?",
                (txn_id,),
            ).fetchone()
        return _authorization_from_row(row) if row else None

    def fail_authorization_attempt(self, txn_id: str, max_attempts: int) -> int:
        """Count a failed sign-in. Returns attempts left; 0 deletes the row."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT attempts FROM oauth_authorizations WHERE id = ?", (txn_id,)
            ).fetchone()
            if row is None:
                return 0
            attempts = row["attempts"] + 1
            if attempts >= max_attempts:
                conn.execute(
                    "DELETE FROM oauth_authorizations WHERE id = ?", (txn_id,)
                )
                conn.commit()
                return 0
            conn.execute(
                "UPDATE oauth_authorizations SET attempts = ? WHERE id = ?",
                (attempts, txn_id),
            )
            conn.commit()
            return max_attempts - attempts

    def complete_authorization(self, txn_id: str, owner_id: int) -> str:
        """Bind a signed-in account to the authorisation and return its code."""
        raw_code = secrets.token_urlsafe(32)
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "UPDATE oauth_authorizations SET owner_id = ?, code_hash = ? "
                "WHERE id = ?",
                (owner_id, _hash_token(raw_code), txn_id),
            )
            conn.commit()
        if cursor.rowcount == 0:
            raise AuthorizationNotFoundError(txn_id)
        return raw_code

    def consume_authorization_code(self, raw_code: str) -> AuthorizationRecord | None:
        """Return the authorisation for a code and delete it — codes are single use."""
        code_hash = _hash_token(raw_code)
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT {_AUTHORIZATION_COLUMNS} FROM oauth_authorizations "
                "WHERE code_hash = ?",
                (code_hash,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "DELETE FROM oauth_authorizations WHERE code_hash = ?", (code_hash,)
            )
            conn.commit()
        return _authorization_from_row(row)

    def delete_authorization(self, txn_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("DELETE FROM oauth_authorizations WHERE id = ?", (txn_id,))
            conn.commit()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_tokens_store.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
ruff format . && ruff check .
git add src/unifi_mcp/tokens.py tests/test_tokens_store.py
git commit -m "Store pending OAuth authorisations and single-use codes"
```

---

### Task 3: Token store — refresh tokens and OAuth-aware revocation

**Files:**
- Modify: `src/unifi_mcp/tokens.py`
- Test: `tests/test_tokens_store.py`

**Interfaces:**
- Consumes: the `oauth_refresh_tokens` table from Task 1.
- Produces: `RefreshRecord` dataclass with fields `token_id: int`, `client_id: str`, `scope: str`, `grant_expires_at: str`, `owner_id: int`, `revoked_at: str | None`. Methods `create_refresh_token(*, token_id, client_id, scope, grant_expires_at) -> str`, `get_refresh_token(raw_token: str) -> RefreshRecord | None`, `delete_refresh_token(raw_token: str) -> None`, `get_oauth_client_id_for_token(token_id: int) -> str | None`, `revoke_token_by_value(raw_token: str) -> None`, `revoke_by_refresh_token(raw_token: str) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tokens_store.py`:

```python
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
```

Add `RefreshRecord` to the test file's import list only if a test references the type directly; these tests do not, so no import change is needed.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_tokens_store.py -k RefreshTokens -v`
Expected: FAIL with `AttributeError: 'TokenStore' object has no attribute 'create_refresh_token'`

- [ ] **Step 3: Implement the dataclass and methods**

Add the dataclass after `AuthorizationRecord`:

```python
@dataclass
class RefreshRecord:
    """A refresh token joined to the access-token row it refreshes."""

    token_id: int
    client_id: str
    scope: str
    grant_expires_at: str
    owner_id: int
    revoked_at: str | None
```

Add the select constant next to the others:

```python
_REFRESH_SELECT = (
    "SELECT oauth_refresh_tokens.token_id, oauth_refresh_tokens.client_id, "
    "oauth_refresh_tokens.scope, oauth_refresh_tokens.grant_expires_at, "
    "tokens.owner_id, tokens.revoked_at "
    "FROM oauth_refresh_tokens JOIN tokens ON tokens.id = oauth_refresh_tokens.token_id"
)
```

Add to `TokenStore` after the authorisation methods:

```python
    # ── OAuth refresh tokens ──────────────────────────────────────────────

    def create_refresh_token(
        self,
        *,
        token_id: int,
        client_id: str,
        scope: str,
        grant_expires_at: str,
    ) -> str:
        """Issue a refresh token for an access-token row and return it."""
        raw_token = secrets.token_urlsafe(32)
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO oauth_refresh_tokens (token_hash, token_id, client_id, "
                "scope, grant_expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _hash_token(raw_token),
                    token_id,
                    client_id,
                    scope,
                    grant_expires_at,
                    _now(),
                ),
            )
            conn.commit()
        return raw_token

    def get_refresh_token(self, raw_token: str) -> RefreshRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                _REFRESH_SELECT + " WHERE oauth_refresh_tokens.token_hash = ?",
                (_hash_token(raw_token),),
            ).fetchone()
        return RefreshRecord(**dict(row)) if row else None

    def delete_refresh_token(self, raw_token: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "DELETE FROM oauth_refresh_tokens WHERE token_hash = ?",
                (_hash_token(raw_token),),
            )
            conn.commit()

    def get_oauth_client_id_for_token(self, token_id: int) -> str | None:
        """The OAuth client a token row was issued to, or None if hand-made."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT client_id FROM oauth_refresh_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
        return row["client_id"] if row else None

    def revoke_token_by_value(self, raw_token: str) -> None:
        """Revoke the token row holding this secret and drop its refresh tokens."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id FROM tokens WHERE token_hash = ?",
                (_hash_token(raw_token),),
            ).fetchone()
            if row is None:
                return
            conn.execute(
                "UPDATE tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (_now(), row["id"]),
            )
            conn.execute(
                "DELETE FROM oauth_refresh_tokens WHERE token_id = ?", (row["id"],)
            )
            conn.commit()

    def revoke_by_refresh_token(self, raw_token: str) -> None:
        """Revoke the access token a refresh token belongs to, and itself."""
        record = self.get_refresh_token(raw_token)
        if record is None:
            return
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (_now(), record.token_id),
            )
            conn.execute(
                "DELETE FROM oauth_refresh_tokens WHERE token_id = ?",
                (record.token_id,),
            )
            conn.commit()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_tokens_store.py -v`
Expected: PASS. `test_deleting_account_cascades_to_refresh_tokens` depends on `PRAGMA foreign_keys=ON`, already set in `_connect`, plus the existing `delete_account` deleting the account's token rows.

- [ ] **Step 5: Lint and commit**

```bash
ruff format . && ruff check .
git add src/unifi_mcp/tokens.py tests/test_tokens_store.py
git commit -m "Add OAuth refresh tokens and OAuth-aware revocation to the store"
```

---

### Task 4: OAuth provider

**Files:**
- Create: `src/unifi_mcp/server/_oauth.py`
- Test: `tests/test_server_oauth.py`

**Interfaces:**
- Consumes: every `TokenStore` method from Tasks 1-3.
- Produces: module constants `AUTHORIZATION_TTL`, `ACCESS_TOKEN_TTL`, `GRANT_TTL`, `MAX_LOGIN_ATTEMPTS`, `LOGIN_PATH`; helpers `_iso_in(delta: timedelta) -> str`, `_epoch(iso: str) -> float`, `client_label(client: OAuthClientInformationFull) -> str`; class `TokenStoreOAuthProvider(store: TokenStore)` implementing the SDK provider protocol.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_server_oauth.py`:

```python
"""Tests for the OAuth authorization server (server/_oauth.py)."""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from mcp.shared.auth import OAuthClientInformationFull

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
    async def _authorize(self, provider, client, state="state-123"):
        from mcp.server.auth.provider import AuthorizationParams
        from pydantic import AnyUrl

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

    async def test_authorize_returns_login_url(self, provider, client):
        from mcp.server.auth.provider import AuthorizationParams
        from pydantic import AnyUrl

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

    async def test_load_authorization_code_before_login_returns_none(
        self, provider, client, store
    ):
        txn_id = await self._authorize(provider, client)
        code = store.complete_authorization(txn_id, store.create_account("a", "p"))
        store.consume_authorization_code(code)

        assert await provider.load_authorization_code(client, code) is None

    async def test_exchange_issues_token_row_and_refresh(
        self, provider, client, store
    ):
        owner_id = store.create_account("alice", "hunter2")
        txn_id = await self._authorize(provider, client)
        code = store.complete_authorization(txn_id, owner_id)

        auth_code = await provider.load_authorization_code(client, code)
        tokens = await provider.exchange_authorization_code(client, auth_code)

        record = store.resolve(tokens.access_token)
        assert record.owner_id == owner_id
        assert record.label == "OAuth · Claude"
        assert tokens.refresh_token is not None
        assert tokens.expires_in == 3600

    async def test_code_from_another_client_is_rejected(
        self, provider, client, store
    ):
        owner_id = store.create_account("alice", "hunter2")
        txn_id = await self._authorize(provider, client)
        code = store.complete_authorization(txn_id, owner_id)
        other = OAuthClientInformationFull(
            client_id="client-2", redirect_uris=[REDIRECT_URI]
        )

        assert await provider.load_authorization_code(other, code) is None


class TestRefresh:
    async def _issue(self, provider, client, store, username="alice"):
        from mcp.server.auth.provider import AuthorizationParams
        from pydantic import AnyUrl

        owner_id = store.create_account(username, "hunter2")
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
        txn_id = url.split("txn=", 1)[1]
        code = store.complete_authorization(txn_id, owner_id)
        auth_code = await provider.load_authorization_code(client, code)
        return await provider.exchange_authorization_code(client, auth_code)

    async def test_refresh_rotates_access_token_in_place(
        self, provider, client, store
    ):
        tokens = await self._issue(provider, client, store)
        token_id = store.resolve(tokens.access_token).id

        loaded = await provider.load_refresh_token(client, tokens.refresh_token)
        refreshed = await provider.exchange_refresh_token(client, loaded, [])

        assert store.resolve(tokens.access_token) is None
        assert store.resolve(refreshed.access_token).id == token_id

    async def test_refresh_token_rotates(self, provider, client, store):
        tokens = await self._issue(provider, client, store)

        loaded = await provider.load_refresh_token(client, tokens.refresh_token)
        refreshed = await provider.exchange_refresh_token(client, loaded, [])

        assert refreshed.refresh_token != tokens.refresh_token
        assert await provider.load_refresh_token(client, tokens.refresh_token) is None

    async def test_load_refresh_token_none_after_revocation(
        self, provider, client, store
    ):
        tokens = await self._issue(provider, client, store)
        token_id = store.resolve(tokens.access_token).id
        store.revoke_token(token_id, requesting_owner_id=None)

        assert await provider.load_refresh_token(client, tokens.refresh_token) is None

    async def test_load_refresh_token_carries_grant_expiry(
        self, provider, client, store
    ):
        tokens = await self._issue(provider, client, store)

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

    async def test_revoke_access_token_kills_the_grant(
        self, provider, client, store
    ):
        tokens = await TestRefresh()._issue(provider, client, store)

        access = await provider.load_access_token(tokens.access_token)
        await provider.revoke_token(access)

        assert store.resolve(tokens.access_token) is None
        assert store.get_refresh_token(tokens.refresh_token) is None

    async def test_revoke_refresh_token_kills_the_access_token(
        self, provider, client, store
    ):
        tokens = await TestRefresh()._issue(provider, client, store)

        loaded = await provider.load_refresh_token(client, tokens.refresh_token)
        await provider.revoke_token(loaded)

        assert store.resolve(tokens.access_token) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_server_oauth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'unifi_mcp.server._oauth'`

- [ ] **Step 3: Implement the provider**

Create `src/unifi_mcp/server/_oauth.py`:

```python
"""OAuth 2.1 authorization server for the MCP endpoint.

Claude Desktop, claude.ai, and Claude mobile can only add a remote MCP
server as a custom connector if it speaks OAuth: the connector dialog has
no field for a static bearer token outside a limited beta. The protocol
itself is implemented by the handlers that ship in ``mcp.server.auth``;
this module supplies the provider they call, backed by the same
``TokenStore`` the admin UI and the bearer middleware already use.

An access token issued here *is* an ordinary row in the ``tokens`` table,
so a connector session shows up in the admin UI under the account that
authorised it, is revocable there, and is attributed in the usage log
exactly like a hand-made token. A refresh rotates the secret on that same
row rather than adding a new one, so the UI shows one entry per sign-in
instead of one per hour.
"""

import json
from datetime import UTC, datetime, timedelta

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from unifi_mcp.tokens import TokenStore

# How long a sign-in link stays usable after Claude sends the user to it.
AUTHORIZATION_TTL = timedelta(minutes=10)
# How long an issued access token lasts; Claude refreshes before this.
ACCESS_TOKEN_TTL = timedelta(hours=1)
# How long the whole grant lasts before the user must sign in again.
GRANT_TTL = timedelta(days=30)
# Failed sign-ins allowed per authorisation before the link is burned.
MAX_LOGIN_ATTEMPTS = 5

LOGIN_PATH = "/oauth/login"


def _iso_in(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


def _epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def client_label(client: OAuthClientInformationFull) -> str:
    """The token label shown in the admin UI for this OAuth client."""
    name = (client.client_name or "").strip() or (client.client_id or "")[:8]
    return f"OAuth · {name}"[:80]


class TokenStoreOAuthProvider:
    """Implements the MCP SDK's OAuthAuthorizationServerProvider protocol."""

    def __init__(self, store: TokenStore) -> None:
        self._store = store

    # ── clients ───────────────────────────────────────────────────────────

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        raw = self._store.get_oauth_client(client_id)
        return OAuthClientInformationFull.model_validate_json(raw) if raw else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._store.save_oauth_client(
            str(client_info.client_id), client_info.model_dump_json()
        )

    # ── authorisation ─────────────────────────────────────────────────────

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Park the request and send the user to this server's own login page."""
        txn_id = self._store.create_authorization(
            client_id=str(client.client_id),
            redirect_uri=str(params.redirect_uri),
            redirect_uri_explicit=params.redirect_uri_provided_explicitly,
            code_challenge=params.code_challenge,
            state=params.state,
            scope=" ".join(params.scopes or []),
            resource=params.resource,
            expires_at=_iso_in(AUTHORIZATION_TTL),
        )
        return f"{LOGIN_PATH}?txn={txn_id}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        """Consume the code. Deliberately single use, even on a PKCE failure."""
        record = self._store.consume_authorization_code(authorization_code)
        if (
            record is None
            or record.client_id != client.client_id
            or record.owner_id is None
        ):
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=record.scope.split() if record.scope else [],
            expires_at=_epoch(record.expires_at),
            client_id=record.client_id,
            code_challenge=record.code_challenge,
            redirect_uri=AnyUrl(record.redirect_uri),
            redirect_uri_provided_explicitly=record.redirect_uri_explicit,
            resource=record.resource,
            subject=str(record.owner_id),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        owner_id = int(authorization_code.subject or 0)
        scope = " ".join(authorization_code.scopes)
        access_token = self._store.create_token(
            owner_id, client_label(client), _iso_in(ACCESS_TOKEN_TTL)
        )
        record = self._store.resolve(access_token)
        if record is None:  # pragma: no cover - the row was just written
            raise TokenError(
                error="invalid_grant", error_description="could not issue a token"
            )
        refresh_token = self._store.create_refresh_token(
            token_id=record.id,
            client_id=str(client.client_id),
            scope=scope,
            grant_expires_at=_iso_in(GRANT_TTL),
        )
        return OAuthToken(
            access_token=access_token,
            expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
            refresh_token=refresh_token,
            scope=scope or None,
        )

    # ── refresh ───────────────────────────────────────────────────────────

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        record = self._store.get_refresh_token(refresh_token)
        if (
            record is None
            or record.client_id != client.client_id
            or record.revoked_at is not None
        ):
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=record.client_id,
            scopes=record.scope.split() if record.scope else [],
            expires_at=int(_epoch(record.grant_expires_at)),
            subject=str(record.owner_id),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Rotate both tokens, keeping the same row and the same grant expiry."""
        record = self._store.get_refresh_token(refresh_token.token)
        if record is None:  # pragma: no cover - guarded by load_refresh_token
            raise TokenError(
                error="invalid_grant", error_description="refresh token does not exist"
            )
        try:
            access_token = self._store.rotate_token(
                record.token_id, _iso_in(ACCESS_TOKEN_TTL)
            )
        except Exception as exc:
            raise TokenError(
                error="invalid_grant", error_description="token has been revoked"
            ) from exc
        self._store.delete_refresh_token(refresh_token.token)
        new_refresh = self._store.create_refresh_token(
            token_id=record.token_id,
            client_id=record.client_id,
            scope=record.scope,
            grant_expires_at=record.grant_expires_at,
        )
        return OAuthToken(
            access_token=access_token,
            expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
            refresh_token=new_refresh,
            scope=record.scope or None,
        )

    # ── access tokens and revocation ──────────────────────────────────────

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Only OAuth-issued tokens are visible here, so /revoke can't touch
        a bearer token someone made by hand in the admin UI."""
        record = self._store.resolve(token)
        if record is None:
            return None
        client_id = self._store.get_oauth_client_id_for_token(record.id)
        if client_id is None:
            return None
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=[],
            expires_at=int(_epoch(record.expires_at)) if record.expires_at else None,
            subject=str(record.owner_id),
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, RefreshToken):
            self._store.revoke_by_refresh_token(token.token)
        else:
            self._store.revoke_token_by_value(token.token)
```

Remove the unused `json` import if ruff flags it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_server_oauth.py -v`
Expected: PASS. `asyncio_mode = "auto"` in `pyproject.toml` means the `async def` tests need no decorator.

- [ ] **Step 5: Lint and commit**

```bash
ruff format . && ruff check .
git add src/unifi_mcp/server/_oauth.py tests/test_server_oauth.py
git commit -m "Add an OAuth provider backed by the token store"
```

---

### Task 5: Sign-in page

**Files:**
- Create: `src/unifi_mcp/server/templates/oauth_login.html`
- Create: `src/unifi_mcp/server/templates/oauth_error.html`
- Modify: `src/unifi_mcp/server/_oauth.py`
- Test: `tests/test_server_oauth.py`

**Interfaces:**
- Consumes: `TokenStoreOAuthProvider`, the constants, and every store method from Tasks 1-3.
- Produces: `build_login_routes(store: TokenStore) -> list[Route]` serving `GET /oauth/login` and `POST /oauth/login`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server_oauth.py`:

```python
from starlette.applications import Starlette
from starlette.testclient import TestClient
from urllib.parse import parse_qs, urlparse

from unifi_mcp.server._oauth import build_login_routes


@pytest.fixture
def login_client(store):
    app = Starlette(routes=build_login_routes(store))
    return TestClient(app, base_url="http://localhost")


def _pending(store, state="state-123"):
    store.save_oauth_client("client-1", '{"client_id": "client-1", "client_name": "Claude"}')
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


class TestLoginPage:
    def test_get_renders_form_with_client_and_redirect_host(
        self, login_client, store
    ):
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_server_oauth.py -k LoginPage -v`
Expected: FAIL with `ImportError: cannot import name 'build_login_routes'`

- [ ] **Step 3: Write the templates**

Create `src/unifi_mcp/server/templates/oauth_login.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in · UniFi MCP</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center;
         background: #0E0E10; color: #0E0E10;
         font: 15px/1.5 "Helvetica Neue", Arial, sans-serif; padding: 24px; }
  .card { width: 100%; max-width: 380px; background: #fff; border-radius: 20px;
          padding: 32px; box-sizing: border-box; }
  .eyebrow { font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
             color: #717179; margin-bottom: 8px; }
  .eyebrow span { color: #E8590C; }
  h1 { font-size: 22px; margin: 0 0 8px; letter-spacing: -.02em; }
  p { color: #52525A; margin: 0 0 20px; }
  .grant { background: #FCFCFD; border: 1px solid #E8E8EB; border-radius: 10px;
           padding: 12px; font-size: 13px; color: #52525A; margin-bottom: 20px; }
  .grant b { color: #0E0E10; }
  label { display: block; font-size: 12px; letter-spacing: .08em;
          text-transform: uppercase; color: #717179; margin-bottom: 6px; }
  input { width: 100%; box-sizing: border-box; padding: 10px 12px; font-size: 15px;
          border: 1px solid #DFDFE3; border-radius: 10px; margin-bottom: 16px; }
  button { font: inherit; border-radius: 10px; padding: 11px 16px; cursor: pointer;
           border: 1px solid transparent; }
  .primary { width: 100%; background: #E8590C; color: #fff; font-weight: 600; }
  .primary:hover { background: #C7480A; }
  .ghost { width: 100%; background: transparent; color: #52525A;
           border-color: #DFDFE3; margin-top: 10px; }
  .alert { background: #FDECEA; color: #C0392B; border-radius: 10px;
           padding: 10px 12px; margin-bottom: 16px; font-size: 14px; }
  .foot { margin-top: 22px; font-size: 12px; color: #717179; text-align: center; }
</style>
</head>
<body>
  <div class="card">
    <div class="eyebrow"><span>/</span> UniFi MCP</div>
    <h1>Sign in</h1>
    <p>Authorise this application to use your UniFi MCP server.</p>
    <div class="grant">
      <b>{{ client_name }}</b> is asking for access, and will be returned to
      <b>{{ redirect_host }}</b>. It will be able to read and change everything on
      this UniFi network until you revoke its token in the token admin.
    </div>
    {% if error %}<div class="alert" role="alert">{{ error }}</div>{% endif %}
    <form method="post" action="/oauth/login">
      <input type="hidden" name="txn" value="{{ txn }}">
      <label for="username">Username</label>
      <input id="username" name="username" type="text" autocomplete="username"
             autofocus required>
      <label for="password">Password</label>
      <input id="password" name="password" type="password"
             autocomplete="current-password" required>
      <button class="primary" type="submit">Sign in</button>
      <button class="ghost" type="submit" name="cancel" value="1"
              formnovalidate>Cancel</button>
    </form>
    <div class="foot">seeg development · UniFi MCP</div>
  </div>
</body>
</html>
```

Create `src/unifi_mcp/server/templates/oauth_error.html` with the same `<style>` block, and this body:

```html
  <div class="card">
    <div class="eyebrow"><span>/</span> UniFi MCP</div>
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
    <div class="foot">seeg development · UniFi MCP</div>
  </div>
```

- [ ] **Step 4: Implement the routes**

Append to `src/unifi_mcp/server/_oauth.py`:

```python
import os
from urllib.parse import urlparse

from mcp.server.auth.provider import construct_redirect_uri
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

_BAD_LINK_TITLE = "This sign-in link has expired"
_BAD_LINK_MESSAGE = (
    "Sign-in links are valid for a few minutes and can only be used once. "
    "Start again from the application you were connecting."
)


def _error_page(request: Request, title: str, message: str) -> Response:
    return templates.TemplateResponse(
        request,
        "oauth_error.html",
        {"title": title, "message": message},
        status_code=400,
    )


def build_login_routes(store: TokenStore) -> list[Route]:
    """The sign-in page an authorisation redirects the user's browser to."""

    async def _render_form(
        request: Request, txn_id: str, client_name: str, redirect_uri: str, error: str | None
    ) -> Response:
        return templates.TemplateResponse(
            request,
            "oauth_login.html",
            {
                "txn": txn_id,
                "client_name": client_name,
                "redirect_host": urlparse(redirect_uri).netloc,
                "error": error,
            },
            status_code=200,
        )

    def _client_name(client_id: str) -> str:
        raw = store.get_oauth_client(client_id)
        if raw is None:
            return "An application"
        client = OAuthClientInformationFull.model_validate_json(raw)
        return (client.client_name or "").strip() or "An application"

    async def login_page(request: Request) -> Response:
        txn_id = request.query_params.get("txn", "")
        record = store.get_authorization(txn_id) if txn_id else None
        if record is None:
            return _error_page(request, _BAD_LINK_TITLE, _BAD_LINK_MESSAGE)
        return await _render_form(
            request,
            txn_id,
            _client_name(record.client_id),
            record.redirect_uri,
            None,
        )

    async def login_submit(request: Request) -> Response:
        form = await request.form()
        txn_id = str(form.get("txn", ""))
        record = store.get_authorization(txn_id) if txn_id else None
        if record is None:
            return _error_page(request, _BAD_LINK_TITLE, _BAD_LINK_MESSAGE)

        if form.get("cancel"):
            store.delete_authorization(txn_id)
            return RedirectResponse(
                construct_redirect_uri(
                    record.redirect_uri, error="access_denied", state=record.state
                ),
                status_code=303,
            )

        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        owner_id = store.verify_account_password(username, password)
        if owner_id is None:
            # Root lives in environment variables with no accounts row, so it
            # can never authorise a connector — the same rule that stops it
            # owning a bearer token.
            remaining = store.fail_authorization_attempt(txn_id, MAX_LOGIN_ATTEMPTS)
            if remaining == 0:
                return _error_page(
                    request,
                    "Too many attempts",
                    "This sign-in link has been cancelled. Start again from the "
                    "application you were connecting.",
                )
            return await _render_form(
                request,
                txn_id,
                _client_name(record.client_id),
                record.redirect_uri,
                "Invalid username or password",
            )

        code = store.complete_authorization(txn_id, owner_id)
        return RedirectResponse(
            construct_redirect_uri(record.redirect_uri, code=code, state=record.state),
            status_code=303,
        )

    return [
        Route(LOGIN_PATH, login_page, methods=["GET"]),
        Route(LOGIN_PATH, login_submit, methods=["POST"]),
    ]
```

Move the new imports to the top of the file with the existing ones so ruff's isort rule passes.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_server_oauth.py -v`
Expected: PASS.

- [ ] **Step 6: Confirm the templates ship in the wheel**

Run: `python -c "import unifi_mcp.server._oauth as m; import os; print(os.listdir(m._TEMPLATES_DIR))"`
Expected: `['oauth_login.html', 'oauth_error.html']`. Hatchling includes package data under `src/unifi_mcp` by default, matching how `admin/templates` already ships.

- [ ] **Step 7: Lint and commit**

```bash
ruff format . && ruff check .
git add src/unifi_mcp/server/_oauth.py src/unifi_mcp/server/templates tests/test_server_oauth.py
git commit -m "Serve a sign-in and consent page for OAuth authorisations"
```

---

### Task 6: Mount the OAuth routes and update the bearer challenge

**Files:**
- Modify: `src/unifi_mcp/server/_oauth.py`
- Modify: `src/unifi_mcp/server/_http.py`
- Test: `tests/test_server_http.py`, `tests/test_server_oauth.py`

**Interfaces:**
- Consumes: `TokenStoreOAuthProvider` and `build_login_routes` from Tasks 4-5.
- Produces: `build_oauth_routes(store: TokenStore, public_url: str) -> tuple[list[Route], str]` returning the routes and the protected-resource metadata URL; `normalize_public_url(raw: str) -> str` in `_http.py`; `build_app(mcp_server, token_store, on_shutdown, public_url: str | None = None)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server_oauth.py`:

```python
from unittest.mock import AsyncMock

from mcp.server import Server

from unifi_mcp.server._http import build_app, normalize_public_url

PUBLIC_URL = "http://localhost"


@pytest.fixture
def oauth_app(store):
    return build_app(Server("test-server"), store, AsyncMock(), public_url=PUBLIC_URL)


@pytest.fixture
def http(oauth_app):
    with TestClient(oauth_app, base_url=PUBLIC_URL) as client:
        yield client


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
        response = http.post(
            "/mcp", json={}, headers={"Authorization": "Bearer nope"}
        )

        assert 'error="invalid_token"' in response.headers["www-authenticate"]

    def test_oauth_routes_do_not_require_a_bearer_token(self, http):
        assert http.get("/.well-known/oauth-authorization-server").status_code == 200
        assert http.get("/oauth/login", params={"txn": "x"}).status_code == 400
```

Append to `tests/test_server_http.py`:

```python
class TestChallengeWithoutPublicUrl:
    def test_401_carries_a_bare_bearer_challenge(self, mcp_server, token_store):
        store, _ = token_store
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.post("/mcp", json={})

        assert response.headers["www-authenticate"] == "Bearer"

    def test_oauth_routes_are_absent(self, mcp_server, token_store):
        store, _ = token_store
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.get("/.well-known/oauth-authorization-server")

        assert response.status_code == 404

    def test_unknown_path_still_needs_no_token(self, mcp_server, token_store):
        store, _ = token_store
        app = build_app(mcp_server, store, AsyncMock())

        with TestClient(app) as client:
            response = client.get("/nope")

        assert response.status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_server_oauth.py -k "Metadata or NormalizePublicUrl or UnauthenticatedChallenge" tests/test_server_http.py -v`
Expected: FAIL with `ImportError: cannot import name 'normalize_public_url'`

- [ ] **Step 3: Implement `build_oauth_routes`**

Append to `src/unifi_mcp/server/_oauth.py`:

```python
from mcp.server.auth.handlers.metadata import MetadataHandler
from mcp.server.auth.routes import (
    build_metadata,
    build_resource_metadata_url,
    cors_middleware,
    create_auth_routes,
    create_protected_resource_routes,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from pydantic import AnyHttpUrl

_METADATA_PATH = "/.well-known/oauth-authorization-server"
_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"


def build_oauth_routes(store: TokenStore, public_url: str) -> tuple[list[Route], str]:
    """Routes for the authorization server, and the resource metadata URL.

    The URL comes back so the bearer middleware can point its 401 challenge
    at it: Claude reads the pointer, fetches the document, and learns where
    to send the user to sign in.
    """
    issuer = AnyHttpUrl(public_url)
    resource_url = AnyHttpUrl(f"{public_url}/mcp")
    registration = ClientRegistrationOptions(enabled=True)
    revocation = RevocationOptions(enabled=True)
    provider = TokenStoreOAuthProvider(store)

    routes = create_auth_routes(
        provider=provider,
        issuer_url=issuer,
        client_registration_options=registration,
        revocation_options=revocation,
    )

    # Claude registers as a public client, and picking a Client ID Metadata
    # Document over dynamic registration requires "none" to be advertised.
    # The SDK's own metadata lists only the two client_secret methods.
    metadata = build_metadata(issuer, None, registration, revocation)
    metadata.token_endpoint_auth_methods_supported = [
        "client_secret_post",
        "client_secret_basic",
        "none",
    ]
    routes = [route for route in routes if route.path != _METADATA_PATH]
    routes.insert(
        0,
        Route(
            _METADATA_PATH,
            endpoint=cors_middleware(MetadataHandler(metadata).handle, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"],
        ),
    )

    resource_routes = create_protected_resource_routes(
        resource_url=resource_url,
        authorization_servers=[issuer],
        resource_name="UniFi MCP",
    )
    # Claude probes the path-suffixed URL first and the bare one second; serve
    # both so a client that skips the WWW-Authenticate pointer still works.
    alias = Route(
        _RESOURCE_METADATA_PATH,
        endpoint=resource_routes[0].endpoint,
        methods=["GET", "OPTIONS"],
    )

    routes = routes + resource_routes + [alias] + build_login_routes(store)
    return routes, str(build_resource_metadata_url(resource_url))
```

- [ ] **Step 4: Wire it into the app**

In `src/unifi_mcp/server/_http.py`, add `from urllib.parse import urlparse` and `from starlette.routing import Route` (already imported), then replace `BearerAuthMiddleware.__init__`/`dispatch` and `build_app`/`run_http`:

```python
class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Requires a valid bearer token (checked via TokenStore) on the MCP
    endpoint. Everything else — the health check, and the OAuth endpoints when
    they are enabled — is public by design. The resolved token is left on
    ``request.state.caller`` for the usage log."""

    def __init__(
        self, app, token_store: TokenStore, resource_metadata_url: str | None = None
    ) -> None:
        super().__init__(app)
        self._token_store = token_store
        self._resource_metadata_url = resource_metadata_url

    def _challenge(self, error: str | None = None) -> str:
        """RFC 9728 challenge. The resource_metadata pointer is what tells an
        OAuth client where to discover this server's authorization server."""
        params = []
        if error:
            params.append(f'error="{error}"')
        if self._resource_metadata_url:
            params.append(f'resource_metadata="{self._resource_metadata_url}"')
        return "Bearer " + ", ".join(params) if params else "Bearer"

    def _unauthorized(self, error: str | None = None) -> Response:
        return PlainTextResponse(
            "Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": self._challenge(error)},
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith(MCP_PATH):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        scheme, _, raw_token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not raw_token:
            return self._unauthorized()
        caller = self._token_store.resolve(raw_token)
        if caller is None:
            return self._unauthorized("invalid_token")
        request.state.caller = caller
        return await call_next(request)


def normalize_public_url(raw: str) -> str:
    """Validate MCP_PUBLIC_URL and return it without a trailing slash.

    It has to be a bare origin: the OAuth metadata documents are served at
    fixed paths beneath it, and the value must match the URL a user types
    into their MCP client minus the /mcp path.
    """
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("must be an absolute http(s) URL, e.g. https://mcp.example.com")
    if parsed.path.strip("/") or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("must be a bare origin with no path, query, or fragment")
    return f"{parsed.scheme}://{parsed.netloc}"


def build_app(
    mcp_server: Server,
    token_store: TokenStore,
    on_shutdown: Callable[[], Awaitable[None]],
    public_url: str | None = None,
) -> Starlette:
    session_manager = StreamableHTTPSessionManager(app=mcp_server)

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            try:
                yield
            finally:
                await on_shutdown()

    routes: list = [Route(HEALTH_PATH, _healthz)]
    resource_metadata_url: str | None = None
    if public_url:
        from unifi_mcp.server._oauth import build_oauth_routes

        oauth_routes, resource_metadata_url = build_oauth_routes(
            token_store, public_url
        )
        routes.extend(oauth_routes)
    routes.append(Mount(MCP_PATH, app=handle_mcp))

    return Starlette(
        routes=routes,
        middleware=[
            Middleware(NormalizeMcpPath),
            Middleware(
                BearerAuthMiddleware,
                token_store=token_store,
                resource_metadata_url=resource_metadata_url,
            ),
            Middleware(UsageLogMiddleware, token_store=token_store),
        ],
        lifespan=lifespan,
    )


def run_http(mcp_server: Server, on_shutdown: Callable[[], Awaitable[None]]) -> None:
    """Run the MCP server over Streamable HTTP.

    Reads MCP_HTTP_HOST (default 0.0.0.0), MCP_HTTP_PORT (default 8765),
    TOKEN_DB_PATH (default /data/tokens.db), and the optional MCP_PUBLIC_URL
    (enables the OAuth endpoints) from the environment.
    """
    host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_HTTP_PORT", "8765"))
    db_path = os.environ.get("TOKEN_DB_PATH", "/data/tokens.db")
    raw_public_url = os.environ.get("MCP_PUBLIC_URL", "").strip()
    public_url = None
    if raw_public_url:
        try:
            public_url = normalize_public_url(raw_public_url)
        except ValueError as exc:
            raise SystemExit(f"MCP_PUBLIC_URL is invalid: {exc}") from exc

    token_store = TokenStore(db_path)
    app = build_app(mcp_server, token_store, on_shutdown, public_url=public_url)
    uvicorn.run(app, host=host, port=port)
```

The `HEALTH_PATH` early return in `dispatch` is gone because `/healthz` no longer starts with `/mcp`; keep `HEALTH_PATH` defined for the route.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_server_http.py tests/test_server_oauth.py -v`
Expected: PASS. If `authorization_servers` comes back as `["http://localhost/"]` rather than `["http://localhost"]`, that trailing slash is Pydantic's `AnyHttpUrl` normalisation; the test above already expects it.

- [ ] **Step 6: Lint and commit**

```bash
ruff format . && ruff check .
git add src/unifi_mcp/server/_oauth.py src/unifi_mcp/server/_http.py tests/
git commit -m "Mount the OAuth endpoints and point 401s at resource metadata"
```

---

### Task 7: End-to-end connector flow

**Files:**
- Test: `tests/test_server_oauth.py`

**Interfaces:**
- Consumes: the whole stack from Tasks 1-6. Produces no new production code; this task is the acceptance test for the feature.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server_oauth.py`:

```python
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


def _sign_in(http, store, client_id, challenge, username="alice", state="state-123"):
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

        code = _sign_in(http, store, client_id, challenge)
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

        code = _sign_in(http, store, client_id, challenge)
        _exchange(http, client_id, code, verifier)

        tokens = store.list_tokens(owner_id)
        assert [token.label for token in tokens] == ["OAuth · Claude"]

    def test_code_cannot_be_exchanged_twice(self, http, store):
        store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, store, client_id, challenge)
        _exchange(http, client_id, code, verifier)

        second = _exchange(http, client_id, code, verifier)

        assert second.status_code == 400
        assert second.json()["error"] == "invalid_grant"

    def test_wrong_code_verifier_is_rejected_and_burns_the_code(self, http, store):
        store.create_account("alice", "hunter2")
        _, challenge = pkce_pair()
        other_verifier, _ = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, store, client_id, challenge)

        first = _exchange(http, client_id, code, other_verifier)

        assert first.json()["error"] == "invalid_grant"
        assert store.consume_authorization_code(code) is None

    def test_refresh_returns_a_working_token_and_retires_the_old_one(
        self, http, store
    ):
        store.create_account("alice", "hunter2")
        verifier, challenge = pkce_pair()
        client_id = _register(http)
        code = _sign_in(http, store, client_id, challenge)
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
        code = _sign_in(http, store, client_id, challenge)
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
        code = _sign_in(http, store, client_id, challenge)
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
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_server_oauth.py -k ConnectorFlow -v`
Expected: PASS on the first run if Tasks 1-6 are correct. If `test_full_flow_issues_a_working_token` fails on the `/mcp` call with a status other than 401, that is fine — the assertion only rules out an auth failure; the MCP session layer legitimately returns 400 for an empty JSON body, as the existing `test_server_http.py` tests already show.

- [ ] **Step 3: Run the whole suite**

Run: `pytest`
Expected: PASS, 389 pre-existing plus the new tests.

- [ ] **Step 4: Lint and commit**

```bash
ruff format . && ruff check .
git add tests/test_server_oauth.py
git commit -m "Cover the end-to-end connector sign-in, refresh, and revocation flow"
```

---

### Task 8: Configuration and deployment files

**Files:**
- Modify: `.env.example`
- Modify: `deploy/qnap.env.example`
- Modify: `deploy/docker-compose.qnap.yml`
- Modify: `deploy/docker-compose.container-station.yml`

**Interfaces:**
- Consumes: the `MCP_PUBLIC_URL` contract from Task 6. Produces no code.

- [ ] **Step 1: Add `MCP_PUBLIC_URL` to `.env.example`**

After the `TOKEN_DB_PATH` block:

```bash
# Public origin of the MCP service as a remote client reaches it, scheme and
# host only (no path). Setting it turns on the OAuth endpoints that Claude
# Desktop, claude.ai, and Claude mobile need to add this server as a custom
# connector, and makes the 401 on /mcp point at the OAuth metadata.
#
# It must match the URL you type into the client, minus the /mcp path, and
# the service must be reachable at it over public HTTPS — connector traffic
# comes from Anthropic's servers, not from your own machine.
#
# Leave it unset for a LAN-only deployment using hand-made bearer tokens.
# MCP_PUBLIC_URL=https://unifi-mcp.example.com
```

- [ ] **Step 2: Add the same block plus the tunnel token to `deploy/qnap.env.example`**

```bash
# --- Public endpoint (only needed for Claude custom connectors) ---
# Public origin of the MCP service; turns on the OAuth endpoints.
# MCP_PUBLIC_URL=https://unifi-mcp.seeg.io

# Connector token from Zero Trust > Networks > Tunnels. Publishes the MCP
# service without opening any inbound port on the NAS.
# CLOUDFLARE_TUNNEL_TOKEN=
```

- [ ] **Step 3: Add the `cloudflared` service to `deploy/docker-compose.qnap.yml`**

After the `unifi-mcp-admin` service, before `volumes:`:

```yaml
  # Publishes the MCP service on a public hostname without opening a port on
  # the NAS. Only needed for Claude custom connectors; delete this service
  # for a LAN-only deployment. Reaches unifi-mcp over the compose network, so
  # the tunnel's public hostname points at http://unifi-mcp:8765.
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: unifi-mcp-tunnel
    command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - unifi-mcp
    restart: unless-stopped
```

- [ ] **Step 4: Mirror both changes in `deploy/docker-compose.container-station.yml`**

Add to the `unifi-mcp` service's `environment:` block:

```yaml
      # Only for Claude custom connectors; delete if the service stays on the LAN.
      MCP_PUBLIC_URL: "<https://unifi-mcp.example.com>"
```

and add the same `cloudflared` service with the token inlined:

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: unifi-mcp-tunnel
    command: tunnel --no-autoupdate run --token <tunnel-token>
    depends_on:
      - unifi-mcp
    restart: unless-stopped
```

- [ ] **Step 5: Verify both compose files parse**

Run: `docker compose -f deploy/docker-compose.qnap.yml --env-file deploy/qnap.env.example config >/dev/null && echo ok`
Expected: `ok`. If Docker is unavailable, run `python -c "import yaml,sys; [yaml.safe_load(open(p)) for p in sys.argv[1:]]" deploy/docker-compose.qnap.yml deploy/docker-compose.container-station.yml` instead.

- [ ] **Step 6: Commit**

```bash
git add .env.example deploy/
git commit -m "Add MCP_PUBLIC_URL and a Cloudflare Tunnel service to the deploy files"
```

---

### Task 9: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/usage-guide.md`
- Modify: `docs/qnap-deployment.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: everything above. Produces no code.

- [ ] **Step 1: Update `CLAUDE.md`**

In the project-structure block, under `server/`, add after `_http.py`:

```
      _oauth.py            # OAuth authorization server: provider, sign-in page, routes
      templates/           # oauth_login.html, oauth_error.html
```

and add `tests/test_server_oauth.py  # OAuth flow: metadata, sign-in, token exchange, refresh` to the tests block.

- [ ] **Step 2: Add `MCP_PUBLIC_URL` to the README's transport table**

In the `MCP server transport` section's variable table:

| `MCP_PUBLIC_URL` | Public origin of the MCP service (e.g. `https://unifi-mcp.example.com`). Setting it enables the OAuth endpoints needed for Claude custom connectors. | unset |

- [ ] **Step 3: Add a connector subsection to the README**

Under "Running as a network service (HTTP)", after the client-config example, replacing the sentence that says Claude Desktop needs a bridge:

```markdown
### Claude Desktop and claude.ai (custom connector)

Claude's **Settings → Connectors → Add custom connector** does not accept a
static bearer token outside a limited beta, and it reaches the server from
Anthropic's infrastructure rather than from your machine. Two things are
therefore needed: the endpoint must be published on public HTTPS, and the
server must speak OAuth.

Set `MCP_PUBLIC_URL` to the public origin and the server exposes an OAuth
authorization server alongside `/mcp`: dynamic client registration, an
authorize endpoint, a sign-in page, and token and revocation endpoints. The
access token Claude receives is an ordinary row in the token database, so it
shows up in the admin UI under the account that signed in, is revocable
there, and is recorded in the usage log like any other token.

To publish the endpoint without opening a port, see
[docs/qnap-deployment.md](docs/qnap-deployment.md#publishing-the-mcp-endpoint-with-a-cloudflare-tunnel).
For the steps inside Claude, see
[docs/usage-guide.md](docs/usage-guide.md#adding-the-server-as-a-claude-connector).

Claude Code does not use this flow. It authenticates with a static bearer
token, which works unchanged over the LAN or the public URL.
```

- [ ] **Step 4: Rewrite the bridge paragraph in `docs/usage-guide.md`**

In "Connecting to the network service", replace the `mcp-remote` block with a new subsection `### Adding the server as a Claude connector` containing the six Part C steps from the spec, and keep a short note that `mcp-remote` remains an option for clients with no connector support.

- [ ] **Step 5: Add the Cloudflare section to `docs/qnap-deployment.md`**

Add a section `## Publishing the MCP endpoint with a Cloudflare Tunnel` after "Fronting with a reverse proxy (TLS)", covering: creating the tunnel and copying the connector token; the `cloudflared` compose service; the public hostname route (`unifi-mcp` / `seeg.io`, service HTTP, URL `unifi-mcp:8765`) and the note to delete any pre-existing DNS record for that name first; setting `MCP_PUBLIC_URL`; keeping the admin UI off the tunnel; and the off-LAN verification commands from the spec.

Then add a subsection `### Restricting who can reach it` with both options:

```markdown
Two mechanisms are worth knowing apart, because "bypass" means something
specific in Cloudflare.

**Cloudflare Access with a Bypass policy** puts an identity check in front of
the hostname. Anthropic's servers cannot complete an interactive login, so
they need a **Bypass** policy, which is Access's term for "let this traffic
through without enforcement". In Zero Trust → Access controls → Applications
→ Create new application → Self-hosted and private → Add public hostname,
select the `unifi-mcp` hostname, then attach two policies:

| Order | Action | Selector | Value |
|-------|--------|----------|-------|
| 1 | Bypass | IP ranges | Anthropic's egress range, `160.79.104.0/21` |
| 2 | Allow | Emails | your own address, for reaching the sign-in page from a browser |

Access evaluates Service Auth first, then Bypass, then Block and Allow, so
the Bypass is what keeps `/mcp`, `/token`, `/register`, and the metadata
documents reachable. The Allow policy matters because the sign-in page is
opened by *your browser*, which is not in Anthropic's range; without it you
could never complete a connector sign-in. Note Cloudflare's own caveat that
a Bypass policy "does not enforce any Access security controls and requests
are not logged" — the OAuth layer is still doing the real authentication
underneath.

**A WAF custom rule** is the lighter alternative if you do not want Access in
the path at all. In Security → WAF → Custom rules, create a rule with action
**Block**:

    (http.host eq "unifi-mcp.example.com"
      and not ip.src in {160.79.104.0/21}
      and not http.request.uri.path in {"/authorize" "/oauth/login"})

The two path exceptions exist for the same reason as the Allow policy above.

Either way, check Anthropic's published egress range before relying on it,
and remember that everything still requires a valid token or a valid login if
you skip this step entirely.

**One Cloudflare setting can break the connector: Bot Fight Mode.** It
challenges automated clients, and server-to-server requests from Anthropic
look exactly like that. Cloudflare's documentation is explicit that "you
cannot bypass or skip Bot Fight Mode using WAF custom rules or Page Rules"
and that it runs "in a separate evaluation pipeline where Skip, Bypass, and
Allow actions have no effect". If it is on for the zone, turn it off or move
to Super Bot Fight Mode, which does support exceptions. A connector that
fails to complete its first request with no useful error is the symptom.
```

- [ ] **Step 6: Check the docs for staleness**

Run: `grep -rn "mcp-remote" README.md docs/`
Expected: only the single surviving mention in the usage guide's fallback note.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/ CLAUDE.md
git commit -m "Document the Claude connector flow and publishing via Cloudflare Tunnel"
```

---

## Self-Review

**Spec coverage.** Part A section A.2 maps to Task 8 and Task 9 step 5; A.3 to Task 9 step 5; A.5 to Task 9 step 5. Part B: B.2 to Task 6 (`normalize_public_url`) and Task 8; B.3 to Task 6; B.4 to Tasks 1-3; B.5 to Task 4; B.6 to Task 5; B.7 to Task 6; B.8 constants to Task 4; B.9 file list spans Tasks 1-9; B.10's eleven test cases map to Tasks 1-7 (cases 1-2 Task 6 and Task 7; 3-7 Task 7; 8-9 Task 5; 10 Task 6; 11 Task 3). Part C is Task 9 step 4.

**Placeholder scan.** No TBD, TODO, or "handle errors appropriately" steps; every code step carries the code.

**Type consistency.** `AuthorizationRecord.redirect_uri_explicit` is a `bool` everywhere, converted from the SQLite integer in `_authorization_from_row`. `RefreshRecord.token_id` is the `tokens.id` integer used by `rotate_token`, `get_oauth_client_id_for_token`, and `create_refresh_token`. `client_label` is public (no underscore) because Task 4's tests import it. `build_oauth_routes` returns `tuple[list[Route], str]`, matching its unpacking in `build_app`. `store.create_token(owner_id, label, expires_at)` keeps its existing positional signature.

**Known risk to watch during execution.** The SDK's `create_auth_routes` validates that the issuer is HTTPS unless the host is `localhost` or `127.0.0.1`, which is why every test uses `http://localhost` as `MCP_PUBLIC_URL` and sets `TestClient(base_url=...)` to match.
