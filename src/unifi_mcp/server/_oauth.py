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

import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from mcp.server.auth.handlers.metadata import MetadataHandler
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.routes import (
    build_metadata,
    build_resource_metadata_url,
    cors_middleware,
    create_auth_routes,
    create_protected_resource_routes,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl, AnyUrl, ValidationError
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

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
_METADATA_PATH = "/.well-known/oauth-authorization-server"
_RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

_BAD_LINK_TITLE = "This sign-in link has expired"
_BAD_LINK_MESSAGE = (
    "Sign-in links are valid for a few minutes and can only be used once. "
    "Start again from the application you were connecting."
)


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

    # ── clients ─────────────────────────────────────────────────

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        raw = self._store.get_oauth_client(client_id)
        return OAuthClientInformationFull.model_validate_json(raw) if raw else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._store.save_oauth_client(
            str(client_info.client_id), client_info.model_dump_json()
        )

    # ── authorisation ───────────────────────────────────────────

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

    # ── refresh ─────────────────────────────────────────────────

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

    # ── access tokens and revocation ────────────────────────────

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
        request: Request,
        txn_id: str,
        client_name: str,
        redirect_uri: str,
        error: str | None,
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
        """Display name for the consent line. A stored document that no longer
        parses must not break sign-in, so fall back to a neutral label."""
        raw = store.get_oauth_client(client_id)
        if raw is None:
            return "An application"
        try:
            client = OAuthClientInformationFull.model_validate_json(raw)
        except ValidationError:
            return "An application"
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
            endpoint=cors_middleware(
                MetadataHandler(metadata).handle, ["GET", "OPTIONS"]
            ),
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
