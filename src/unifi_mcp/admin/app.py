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
