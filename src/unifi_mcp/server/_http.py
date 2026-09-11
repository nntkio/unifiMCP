"""Streamable HTTP transport for the UniFi MCP server.

Wraps the existing low-level `mcp.server.Server` in a Starlette ASGI app,
protected by a bearer-token check against the shared `TokenStore`, and
records every JSON-RPC message received into the shared usage log.
"""

import json
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import uvicorn
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from unifi_mcp.tokens import TokenRecord, TokenStore, UsageEntry

HEALTH_PATH = "/healthz"
MCP_PATH = "/mcp"


class NormalizeMcpPath:
    """Serve the MCP endpoint at ``/mcp`` as well as ``/mcp/``.

    ``Mount("/mcp")`` only matches ``/mcp/...``, so a bare ``POST /mcp``
    otherwise gets a 307 redirect to ``/mcp/``. Clients that don't follow
    redirects on POST fail outright against the documented URL, so rewrite
    the bare path instead of bouncing the request.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == MCP_PATH:
            scope = dict(scope, path=MCP_PATH + "/")
        await self.app(scope, receive, send)


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
        raise ValueError(
            "must be an absolute http(s) URL, e.g. https://mcp.example.com"
        )
    if parsed.path.strip("/") or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("must be a bare origin with no path, query, or fragment")
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_messages(body: bytes) -> list[tuple[str | None, str | None]]:
    """Extract ``(method, tool)`` per JSON-RPC message in a POST body.

    Streamable HTTP delivers one message (or a batch) per POST. ``tool`` is
    ``params.name`` for ``tools/call`` and None otherwise. Anything that
    isn't valid JSON-RPC still yields one ``(None, None)`` row so the call is
    counted even though it can't be attributed to a method.
    """
    try:
        payload = json.loads(body)
    except ValueError:
        return [(None, None)]
    items = payload if isinstance(payload, list) else [payload]
    messages: list[tuple[str | None, str | None]] = []
    for item in items:
        if not isinstance(item, dict):
            messages.append((None, None))
            continue
        method = item.get("method")
        if not isinstance(method, str):
            method = None
        tool = None
        if method == "tools/call":
            params = item.get("params")
            if isinstance(params, dict) and isinstance(params.get("name"), str):
                tool = params["name"]
        messages.append((method, tool))
    return messages or [(None, None)]


def _caller_ip(request: Request) -> str:
    """Best-effort client IP: first X-Forwarded-For hop, X-Real-IP, then peer."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    first_hop = forwarded_for.split(",")[0].strip()
    if first_hop:
        return first_hop
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return _peer_host(request)


def _peer_host(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class UsageLogMiddleware(BaseHTTPMiddleware):
    """Records every POST to the MCP endpoint in ``TokenStore.usage_log``.

    Runs inside BearerAuthMiddleware, so only authenticated calls reach it.
    GET (the server-to-client SSE stream) and DELETE (session teardown) are
    not calls and are skipped. The body is read here to learn the method and
    tool; Starlette's BaseHTTPMiddleware caches it and replays it downstream.
    Duration is time-to-response-headers, which for SSE responses is all the
    transport exposes.
    """

    def __init__(self, app, token_store: TokenStore) -> None:
        super().__init__(app)
        self._token_store = token_store

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        caller: TokenRecord | None = getattr(request.state, "caller", None)
        is_mcp_post = request.method == "POST" and request.url.path.startswith(MCP_PATH)
        if not is_mcp_post or caller is None:
            return await call_next(request)

        messages = _parse_messages(await request.body())
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)

        for method, tool in messages:
            self._token_store.log_usage(
                UsageEntry(
                    token_id=caller.id,
                    token_label=caller.label,
                    owner_id=caller.owner_id,
                    owner_username=caller.owner_username,
                    ip=_caller_ip(request),
                    remote_addr=_peer_host(request),
                    forwarded_for=request.headers.get("x-forwarded-for"),
                    user_agent=request.headers.get("user-agent"),
                    method=method,
                    tool=tool,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )
            )
        return response


async def _healthz(_request: Request) -> Response:
    return PlainTextResponse("ok")


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
