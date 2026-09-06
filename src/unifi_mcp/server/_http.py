"""Streamable HTTP transport for the UniFi MCP server.

Wraps the existing low-level `mcp.server.Server` in a Starlette ASGI app,
protected by a bearer-token check against the shared `TokenStore`.
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
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
from starlette.types import ASGIApp, Receive, Scope, Send

from unifi_mcp.tokens import TokenStore

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

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            try:
                yield
            finally:
                await on_shutdown()

    return Starlette(
        routes=[
            Route(HEALTH_PATH, _healthz),
            Mount(MCP_PATH, app=handle_mcp),
        ],
        middleware=[
            Middleware(NormalizeMcpPath),
            Middleware(BearerAuthMiddleware, token_store=token_store),
        ],
        lifespan=lifespan,
    )


def run_http(mcp_server: Server, on_shutdown: Callable[[], Awaitable[None]]) -> None:
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
