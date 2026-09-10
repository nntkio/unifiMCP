"""Routes for the token-admin service: login, accounts, tokens, and usage."""

import math
import os
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from starlette.applications import Starlette
from starlette.datastructures import QueryParams
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from unifi_mcp.admin.auth import (
    check_root_credentials,
    csrf_token_valid,
    generate_csrf_token,
)
from unifi_mcp.tokens import (
    AccountExistsError,
    AccountNotFoundError,
    AccountRecord,
    TokenNotOwnedError,
    TokenRecord,
    TokenStore,
    UsageFilter,
)

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

_EXPIRY_PRESET_DAYS = {"30d": 30, "90d": 90, "365d": 365, "never": None}
_EXPIRING_SOON_DAYS = 30
USAGE_PAGE_SIZE = 50


# ── template filters ──────────────────────────────────────────────────────


def short_date(value: str | None, seconds: bool = False) -> str:
    """Render an ISO-8601 timestamp as ``09 Sep 2026 14:05`` in UTC."""
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return value
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    pattern = "%d %b %Y %H:%M:%S" if seconds else "%d %b %Y %H:%M"
    return moment.strftime(pattern)


def token_status(token: TokenRecord) -> str:
    """One of ``active``, ``expired``, ``revoked`` — drives the status chip."""
    if token.revoked_at:
        return "revoked"
    if token.expires_at and token.expires_at <= datetime.now(UTC).isoformat():
        return "expired"
    return "active"


templates.env.filters["short_date"] = short_date
templates.env.filters["token_status"] = token_status


# ── session and context helpers ───────────────────────────────────────────


def _csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return token


def _current_user(request: Request) -> dict[str, str]:
    role = "root" if request.session.get("role") == "root" else "user"
    return {"username": request.session.get("username", ""), "role": role}


def _context(request: Request, active_nav: str, **extra: object) -> dict:
    return {
        "csrf_token": _csrf_token(request),
        "error": None,
        "current_user": _current_user(request),
        "active_nav": active_nav,
        **extra,
    }


def _require_root(request: Request) -> Response | None:
    if request.session.get("role") != "root":
        return RedirectResponse("/login", status_code=303)
    return None


def _require_user(request: Request) -> int | Response:
    user_id = request.session.get("user_id")
    if user_id is None:
        return RedirectResponse("/login", status_code=303)
    return user_id


# ── login / logout ────────────────────────────────────────────────────────


async def root_redirect(_request: Request) -> Response:
    return RedirectResponse("/login", status_code=303)


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
        # Start from an empty session so a previous identity (e.g. an
        # account login in the same browser) cannot linger alongside root.
        request.session.clear()
        request.session["role"] = "root"
        request.session["username"] = username
        return RedirectResponse("/admin", status_code=303)

    token_store: TokenStore = request.app.state.token_store
    account_id = token_store.verify_account_password(username, password)
    if account_id is not None:
        request.session.clear()
        request.session["user_id"] = account_id
        request.session["username"] = username
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


# ── root: accounts and tokens ─────────────────────────────────────────────


def _token_stats(accounts: list[AccountRecord], tokens: list[TokenRecord]) -> dict:
    soon = (datetime.now(UTC) + timedelta(days=_EXPIRING_SOON_DAYS)).isoformat()
    statuses = [token_status(token) for token in tokens]
    expiring = sum(
        1
        for token, status in zip(tokens, statuses, strict=True)
        if status == "active" and token.expires_at and token.expires_at <= soon
    )
    return {
        "accounts": len(accounts),
        "active": statuses.count("active"),
        "expiring": expiring,
        "revoked": statuses.count("revoked"),
    }


def _render_admin(
    request: Request, *, error: str | None = None, status_code: int = 200
) -> Response:
    token_store: TokenStore = request.app.state.token_store
    accounts = token_store.list_accounts()
    tokens = token_store.list_tokens(owner_id=None)
    tokens_by_owner: dict[int, list[TokenRecord]] = {}
    for token in tokens:
        tokens_by_owner.setdefault(token.owner_id, []).append(token)
    return templates.TemplateResponse(
        request,
        "admin.html",
        _context(
            request,
            "accounts",
            accounts=accounts,
            tokens_by_owner=tokens_by_owner,
            stats=_token_stats(accounts, tokens),
            error=error,
        ),
        status_code=status_code,
    )


async def admin_home(request: Request) -> Response:
    redirect = _require_root(request)
    if redirect is not None:
        return redirect
    return _render_admin(request)


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
        return _render_admin(request, error="Invalid form submission.", status_code=403)

    try:
        token_store.create_account(username, password)
    except AccountExistsError:
        return _render_admin(
            request,
            error=f"Username '{username}' already exists.",
            status_code=409,
        )

    return RedirectResponse("/admin", status_code=303)


async def admin_delete_account(request: Request) -> Response:
    redirect = _require_root(request)
    if redirect is not None:
        return redirect

    form = await request.form()
    submitted_csrf = str(form.get("csrf_token", ""))
    if not csrf_token_valid(request.session.get("csrf_token"), submitted_csrf):
        return Response("Invalid form submission.", status_code=403)

    token_store: TokenStore = request.app.state.token_store
    account_id = int(request.path_params["account_id"])
    try:
        token_store.delete_account(account_id)
    except AccountNotFoundError:
        return Response("Not found.", status_code=404)
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


# ── root: usage log ───────────────────────────────────────────────────────

_USAGE_TEXT_FIELDS = (
    "since",
    "until",
    "owner_username",
    "token_label",
    "ip",
    "forwarded_for",
    "method",
    "tool",
)
_USAGE_INT_FIELDS = ("status", "min_duration_ms")


def _text_param(params: QueryParams, name: str) -> str | None:
    return params.get(name, "").strip() or None


def _int_param(params: QueryParams, name: str) -> int | None:
    raw = params.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _usage_filter(params: QueryParams) -> UsageFilter:
    values: dict[str, str | int | None] = {
        name: _text_param(params, name) for name in _USAGE_TEXT_FIELDS
    }
    values.update({name: _int_param(params, name) for name in _USAGE_INT_FIELDS})
    return UsageFilter(**values)


def _active_filter_params(filters: UsageFilter) -> list[tuple[str, str]]:
    """The set filters as query pairs, in declaration order, for pager links."""
    return [
        (field.name, str(getattr(filters, field.name)))
        for field in fields(filters)
        if getattr(filters, field.name) not in (None, "")
    ]


def _usage_page_url(active: list[tuple[str, str]], page: int) -> str:
    return "/admin/usage?" + urlencode([*active, ("page", page)])


async def admin_usage(request: Request) -> Response:
    redirect = _require_root(request)
    if redirect is not None:
        return redirect

    token_store: TokenStore = request.app.state.token_store
    params = request.query_params
    filters = _usage_filter(params)
    total = token_store.count_usage(filters)
    page_count = max(1, math.ceil(total / USAGE_PAGE_SIZE))
    page = min(max(_int_param(params, "page") or 1, 1), page_count)
    rows = token_store.list_usage(
        filters, limit=USAGE_PAGE_SIZE, offset=(page - 1) * USAGE_PAGE_SIZE
    )
    active = _active_filter_params(filters)
    return templates.TemplateResponse(
        request,
        "usage.html",
        _context(
            request,
            "usage",
            rows=rows,
            total=total,
            page=page,
            page_count=page_count,
            filters=filters,
            filters_active=bool(active),
            facets=token_store.usage_facets(),
            summary=token_store.usage_summary(),
            prev_url=_usage_page_url(active, page - 1) if page > 1 else None,
            next_url=_usage_page_url(active, page + 1) if page < page_count else None,
        ),
    )


# ── account users: own tokens ─────────────────────────────────────────────


def _render_tokens(
    request: Request,
    user_id: int,
    *,
    error: str | None = None,
    new_token: str | None = None,
    status_code: int = 200,
) -> Response:
    token_store: TokenStore = request.app.state.token_store
    tokens = token_store.list_tokens(owner_id=user_id)
    return templates.TemplateResponse(
        request,
        "tokens.html",
        _context(request, "tokens", tokens=tokens, error=error, new_token=new_token),
        status_code=status_code,
    )


async def tokens_home(request: Request) -> Response:
    user_id = _require_user(request)
    if isinstance(user_id, Response):
        return user_id
    return _render_tokens(
        request, user_id, new_token=request.session.pop("new_token", None)
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
        return _render_tokens(
            request, user_id, error="Invalid form submission.", status_code=403
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
            Route("/", root_redirect, methods=["GET"]),
            Route("/login", login_form, methods=["GET"]),
            Route("/login", login_submit, methods=["POST"]),
            Route("/logout", logout, methods=["POST"]),
            Route("/admin", admin_home, methods=["GET"]),
            Route("/admin/accounts", admin_create_account, methods=["POST"]),
            Route(
                "/admin/accounts/{account_id:int}/delete",
                admin_delete_account,
                methods=["POST"],
            ),
            Route(
                "/admin/tokens/{token_id:int}/revoke",
                admin_revoke_token,
                methods=["POST"],
            ),
            Route("/admin/usage", admin_usage, methods=["GET"]),
            Route("/tokens", tokens_home, methods=["GET"]),
            Route("/tokens", tokens_create, methods=["POST"]),
            Route("/tokens/{token_id:int}/revoke", tokens_revoke, methods=["POST"]),
            Mount("/static", app=StaticFiles(directory=_STATIC_DIR), name="static"),
        ],
        middleware=[Middleware(SessionMiddleware, secret_key=session_secret)],
    )
    app.state.token_store = token_store
    return app
