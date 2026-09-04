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
