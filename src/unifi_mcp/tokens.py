"""Shared SQLite-backed store for accounts, bearer tokens, and the usage log.

Used by both the MCP server's HTTP transport (server/_http.py: token
resolution and usage logging) and the token-admin web service (admin/:
read-write account and token management, usage reporting) — two separate
processes reading/writing the same file.
"""

import hashlib
import logging
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import argon2
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger(__name__)

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

-- One row per JSON-RPC message received over the HTTP transport. Owner and
-- token are stored as plain text (no foreign keys) so history survives
-- account deletion and token revocation.
CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    token_id INTEGER,
    token_label TEXT NOT NULL,
    owner_id INTEGER,
    owner_username TEXT NOT NULL,
    ip TEXT NOT NULL,
    remote_addr TEXT NOT NULL,
    forwarded_for TEXT,
    user_agent TEXT,
    method TEXT,
    tool TEXT,
    status INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_log_ts ON usage_log (ts);
"""

_TOKEN_COLUMNS = (
    "tokens.id, tokens.owner_id, accounts.username AS owner_username, "
    "tokens.label, tokens.created_at, tokens.expires_at, tokens.revoked_at"
)
_TOKEN_SELECT = (
    f"SELECT {_TOKEN_COLUMNS} FROM tokens "
    "JOIN accounts ON accounts.id = tokens.owner_id"
)

_USAGE_COLUMNS = (
    "id, ts, token_id, token_label, owner_id, owner_username, ip, remote_addr, "
    "forwarded_for, user_agent, method, tool, status, duration_ms"
)


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


@dataclass
class AccountRecord:
    id: int
    username: str
    created_at: str
    token_count: int
    active_token_count: int


@dataclass
class UsageEntry:
    """What the HTTP transport records for one JSON-RPC message."""

    token_id: int | None
    token_label: str
    owner_id: int | None
    owner_username: str
    ip: str
    remote_addr: str
    forwarded_for: str | None
    user_agent: str | None
    method: str | None
    tool: str | None
    status: int
    duration_ms: int


@dataclass
class UsageRecord(UsageEntry):
    id: int
    ts: str


@dataclass
class UsageFilter:
    """Optional per-column filters for the usage log; set fields AND together."""

    since: str | None = None
    until: str | None = None
    owner_username: str | None = None
    token_label: str | None = None
    ip: str | None = None
    forwarded_for: str | None = None
    method: str | None = None
    tool: str | None = None
    status: int | None = None
    min_duration_ms: int | None = None

    _EXACT_COLUMNS = ("owner_username", "token_label", "method", "tool", "status")
    _SUBSTRING_COLUMNS = ("ip", "forwarded_for")

    def where_clause(self) -> tuple[str, list[str | int]]:
        clauses: list[str] = []
        params: list[str | int] = []
        if self.since:
            clauses.append("ts >= ?")
            params.append(self.since)
        if self.until:
            clauses.append("ts <= ?")
            params.append(self.until)
        for column in self._EXACT_COLUMNS:
            value = getattr(self, column)
            if value is not None and value != "":
                clauses.append(f"{column} = ?")
                params.append(value)
        for column in self._SUBSTRING_COLUMNS:
            value = getattr(self, column)
            if value:
                clauses.append(f"instr({column}, ?) > 0")
                params.append(value)
        if self.min_duration_ms is not None:
            clauses.append("duration_ms >= ?")
            params.append(self.min_duration_ms)
        if not clauses:
            return "", params
        return " WHERE " + " AND ".join(clauses), params


@dataclass
class UsageFacets:
    """Distinct values per filterable column, for building filter dropdowns."""

    owner_usernames: list[str]
    token_labels: list[str]
    methods: list[str]
    tools: list[str]
    statuses: list[int]


@dataclass
class UsageSummary:
    calls_today: int
    calls_last_7_days: int
    callers_last_7_days: int
    ips_last_7_days: int


class AccountExistsError(Exception):
    """Raised when creating an account with a username that's already taken."""


class AccountNotFoundError(Exception):
    """Raised when deleting an account that doesn't exist."""


class TokenNotOwnedError(Exception):
    """Raised when revoking a token that doesn't exist or isn't owned by the requester."""


class TokenStore:
    """SQLite-backed storage for accounts, their bearer tokens, and usage."""

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

    # ── accounts ──────────────────────────────────────────────────────────

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

    def list_accounts(self) -> list[AccountRecord]:
        query = (
            "SELECT accounts.id, accounts.username, accounts.created_at, "
            "COUNT(tokens.id) AS token_count, "
            "COALESCE(SUM(CASE WHEN tokens.id IS NOT NULL AND tokens.revoked_at IS NULL "
            "AND (tokens.expires_at IS NULL OR tokens.expires_at > ?) "
            "THEN 1 ELSE 0 END), 0) AS active_token_count "
            "FROM accounts LEFT JOIN tokens ON tokens.owner_id = accounts.id "
            "GROUP BY accounts.id ORDER BY accounts.username"
        )
        with closing(self._connect()) as conn:
            rows = conn.execute(query, (_now(),)).fetchall()
        return [AccountRecord(**dict(row)) for row in rows]

    def delete_account(self, account_id: int) -> None:
        """Delete an account and every token it owns, in one transaction."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
            if row is None:
                raise AccountNotFoundError(account_id)
            conn.execute("DELETE FROM tokens WHERE owner_id = ?", (account_id,))
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()

    # ── tokens ────────────────────────────────────────────────────────────

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
        query = _TOKEN_SELECT
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

    def resolve(self, raw_token: str) -> TokenRecord | None:
        """Return the record for a valid (unrevoked, unexpired) token, else None."""
        token_hash = _hash_token(raw_token)
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    _TOKEN_SELECT + " WHERE tokens.token_hash = ?", (token_hash,)
                ).fetchone()
        except sqlite3.Error:
            return None
        if row is None or row["revoked_at"] is not None:
            return None
        if row["expires_at"] is not None and row["expires_at"] <= _now():
            return None
        return TokenRecord(**dict(row))

    def validate(self, raw_token: str) -> bool:
        return self.resolve(raw_token) is not None

    # ── usage log ─────────────────────────────────────────────────────────

    def log_usage(self, entry: UsageEntry) -> None:
        """Record one call. Never raises: a logging failure must not fail the call."""
        try:
            with closing(self._connect()) as conn:
                conn.execute(
                    "INSERT INTO usage_log (ts, token_id, token_label, owner_id, "
                    "owner_username, ip, remote_addr, forwarded_for, user_agent, "
                    "method, tool, status, duration_ms) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        _now(),
                        entry.token_id,
                        entry.token_label,
                        entry.owner_id,
                        entry.owner_username,
                        entry.ip,
                        entry.remote_addr,
                        entry.forwarded_for,
                        entry.user_agent,
                        entry.method,
                        entry.tool,
                        entry.status,
                        entry.duration_ms,
                    ),
                )
                conn.commit()
        except sqlite3.Error:
            logger.warning("Failed to write usage_log row", exc_info=True)

    def list_usage(
        self, filters: UsageFilter, limit: int, offset: int
    ) -> list[UsageRecord]:
        where, params = filters.where_clause()
        query = (
            f"SELECT {_USAGE_COLUMNS} FROM usage_log{where} "
            "ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?"
        )
        with closing(self._connect()) as conn:
            rows = conn.execute(query, [*params, limit, offset]).fetchall()
        return [UsageRecord(**dict(row)) for row in rows]

    def count_usage(self, filters: UsageFilter) -> int:
        where, params = filters.where_clause()
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS n FROM usage_log{where}", params
            ).fetchone()
        return row["n"]

    def usage_facets(self) -> UsageFacets:
        def distinct(conn: sqlite3.Connection, column: str) -> list:
            rows = conn.execute(
                f"SELECT DISTINCT {column} FROM usage_log "
                f"WHERE {column} IS NOT NULL ORDER BY {column}"
            ).fetchall()
            return [row[0] for row in rows]

        with closing(self._connect()) as conn:
            return UsageFacets(
                owner_usernames=distinct(conn, "owner_username"),
                token_labels=distinct(conn, "token_label"),
                methods=distinct(conn, "method"),
                tools=distinct(conn, "tool"),
                statuses=distinct(conn, "status"),
            )

    def usage_summary(self) -> UsageSummary:
        now = datetime.now(UTC)
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        with closing(self._connect()) as conn:
            today = conn.execute(
                "SELECT COUNT(*) AS n FROM usage_log WHERE ts >= ?",
                (start_of_today.isoformat(),),
            ).fetchone()["n"]
            week = conn.execute(
                "SELECT COUNT(*) AS calls, COUNT(DISTINCT owner_username) AS callers, "
                "COUNT(DISTINCT ip) AS ips FROM usage_log WHERE ts >= ?",
                (week_ago.isoformat(),),
            ).fetchone()
        return UsageSummary(
            calls_today=today,
            calls_last_7_days=week["calls"],
            callers_last_7_days=week["callers"],
            ips_last_7_days=week["ips"],
        )
