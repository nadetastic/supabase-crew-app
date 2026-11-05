"""Backend routes for the Supabase page.

Mounted by Kiro Crew under ``/api/apps/supabase`` behind the dashboard's own
sign-in. No new port is opened.

  GET    /api/apps/supabase/status          -> connection state + saved overview
  POST   /api/apps/supabase/oauth/start     -> Supabase authorize URL to redirect to
  GET    /api/apps/supabase/oauth/callback  -> finishes sign-in, redirects back
  POST   /api/apps/supabase/oauth/finish    -> finishes sign-in from a pasted address
  POST   /api/apps/supabase/refresh         -> reads orgs/projects/tables now
  POST   /api/apps/supabase/oauth/disconnect-> forgets the Supabase tokens

Sign-in is Supabase's own OAuth (authorization code + PKCE). The client is
registered on first use through Supabase's dynamic client registration, so
there is nothing to configure. Tokens are kept in this app's data directory
(file mode 0600), are never sent to the browser, and are only used to read the
Supabase Management API (organizations, projects, public table names).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import ipaddress
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from aiohttp import web

try:  # real registry type inside the gateway
    from kiro_crew.apps.route_registry import AppRoute
except Exception:  # pragma: no cover - standalone import
    from dataclasses import dataclass

    @dataclass
    class AppRoute:  # type: ignore[no-redef]
        method: str
        path: str
        handler: Any


logger = logging.getLogger("kirocrew.app.supabase")

API_BASE = "https://api.supabase.com"
AUTHORIZE_URL = API_BASE + "/v1/oauth/authorize"
TOKEN_URL = API_BASE + "/v1/oauth/token"
REGISTER_URL = API_BASE + "/platform/oauth/apps/register"
SCOPES = "organizations:read projects:read database:read"
CALLBACK_PATH = "/api/apps/supabase/oauth/callback"
CLIENT_NAME = "Kiro Crew Supabase App"

OAUTH_FILE = "oauth.json"  # client registration + tokens (secret)
PENDING_FILE = "oauth-pending.json"  # in-flight sign-ins (secret)
OVERVIEW_FILE = "overview.json"
PENDING_TTL_S = 600
TABLES_SQL = (
    "select table_name from information_schema.tables "
    "where table_schema = 'public' order by table_name"
)

_lock = asyncio.Lock()


class SupabaseError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _require_auth(request: web.Request) -> web.Response | None:
    # The gateway already authenticates /api/apps/*; re-check for defence in depth.
    if request.get("user") is not None:
        return None
    return web.json_response({"error": "unauthorized"}, status=401)


def _data_dir(ctx) -> Path:
    d = Path(getattr(ctx, "data_dir", ".") or ".")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(ctx, name: str) -> dict[str, Any]:
    try:
        data = json.loads((_data_dir(ctx) / name).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write_private(ctx, name: str, data: dict[str, Any]) -> None:
    path = _data_dir(ctx) / name
    tmp = path.with_name(f".{name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _delete(ctx, name: str) -> None:
    try:
        (_data_dir(ctx) / name).unlink()
    except FileNotFoundError:
        pass


def _is_loopback(host: str) -> bool:
    if host in {"localhost", "kirocrew.localhost"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _normalize_origin(value: str) -> str:
    """Accept https origins, or http only on loopback. No path, query or userinfo."""
    try:
        p = urlsplit(str(value or "").strip())
        port = p.port
    except ValueError as exc:
        raise ValueError("The Kiro Crew browser origin is invalid.") from exc
    scheme, host = p.scheme.lower(), (p.hostname or "").lower()
    if (
        scheme not in {"http", "https"}
        or not host
        or p.username
        or p.password
        or p.path not in {"", "/"}
        or p.query
        or p.fragment
        or (scheme == "http" and not _is_loopback(host))
    ):
        raise ValueError("The Kiro Crew browser origin is invalid.")
    netloc = f"[{host}]" if ":" in host else host
    if port:
        netloc += f":{port}"
    return f"{scheme}://{netloc}"


def _safe_return_to(value: str) -> str:
    """Only same-site absolute paths, so the callback cannot redirect off-site."""
    v = str(value or "").strip()
    if not v.startswith("/") or v.startswith("//") or "\\" in v or len(v) > 300:
        return "/"
    return v


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.decode().rstrip("=")


async def _http(method: str, url: str, **kw) -> tuple[int, Any]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.request(method, url, **kw) as r:
            text = await r.text()
            try:
                body = json.loads(text) if text else None
            except json.JSONDecodeError:
                body = None
            return r.status, body


def _store_tokens(ctx, conn: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise SupabaseError("Supabase did not return an access token.")
    expires_in = payload.get("expires_in")
    try:
        ttl = float(expires_in) if expires_in is not None else 3600.0
    except (TypeError, ValueError):
        ttl = 3600.0
    conn = dict(conn)
    conn["access_token"] = access
    if payload.get("refresh_token"):
        conn["refresh_token"] = payload["refresh_token"]
    conn["expires_at"] = time.time() + max(60.0, ttl) - 30
    conn["connected_at"] = conn.get("connected_at") or time.time()
    _write_private(ctx, OAUTH_FILE, conn)
    return conn


# --------------------------------------------------------------------------- #
# OAuth
# --------------------------------------------------------------------------- #
async def _client_for(ctx, redirect_uri: str) -> dict[str, Any]:
    """Reuse the registered client for this redirect URI, or register one."""
    conn = _read(ctx, OAUTH_FILE)
    client = conn.get("client") or {}
    if client.get("client_id") and client.get("redirect_uri") == redirect_uri:
        return client
    status, body = await _http(
        "POST",
        REGISTER_URL,
        json={
            "client_name": CLIENT_NAME,
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
            "scope": SCOPES,
        },
    )
    if status >= 300 or not isinstance(body, dict) or not body.get("client_id"):
        logger.warning("supabase client registration failed: status=%s", status)
        raise SupabaseError(f"Supabase refused to register the app (HTTP {status}).")
    client = {
        "client_id": body["client_id"],
        "client_secret": body.get("client_secret") or "",
        "redirect_uri": redirect_uri,
    }
    # A new client invalidates tokens issued to an old one.
    _write_private(ctx, OAUTH_FILE, {"client": client})
    return client


async def _access_token(ctx) -> str:
    conn = _read(ctx, OAUTH_FILE)
    if not conn.get("access_token"):
        raise SupabaseError("Not signed in to Supabase.", status=401)
    if time.time() < float(conn.get("expires_at") or 0):
        return conn["access_token"]
    client = conn.get("client") or {}
    if not conn.get("refresh_token") or not client.get("client_id"):
        raise SupabaseError("Supabase sign-in expired. Sign in again.", status=401)
    status, body = await _http(
        "POST",
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": conn["refresh_token"],
            "client_id": client["client_id"],
            "client_secret": client.get("client_secret", ""),
        },
    )
    if status >= 300 or not isinstance(body, dict):
        logger.warning("supabase token refresh failed: status=%s", status)
        _write_private(ctx, OAUTH_FILE, {"client": client})
        raise SupabaseError("Supabase sign-in expired. Sign in again.", status=401)
    return _store_tokens(ctx, conn, body)["access_token"]


# --------------------------------------------------------------------------- #
# Supabase Management API reads
# --------------------------------------------------------------------------- #
async def _api_get(token: str, path: str) -> Any:
    status, body = await _http(
        "GET", API_BASE + path, headers={"Authorization": f"Bearer {token}"}
    )
    if status == 401:
        raise SupabaseError("Supabase rejected the sign-in. Sign in again.", status=401)
    if status >= 300:
        raise SupabaseError(f"Supabase returned HTTP {status} for {path}.")
    return body


async def _tables(token: str, ref: str) -> list[str] | None:
    try:
        status, body = await _http(
            "POST",
            f"{API_BASE}/v1/projects/{ref}/database/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": TABLES_SQL},
        )
    except Exception:  # network trouble on one project should not fail the page
        return None
    if status >= 300 or not isinstance(body, list):
        return None
    return [str(r.get("table_name")) for r in body if isinstance(r, dict)][:500]


def _s(v: Any, limit: int = 200) -> str:
    return str(v if v is not None else "")[:limit]


async def _build_overview(ctx) -> dict[str, Any]:
    token = await _access_token(ctx)
    orgs_raw, projects_raw = await asyncio.gather(
        _api_get(token, "/v1/organizations"), _api_get(token, "/v1/projects")
    )
    orgs = [
        {"id": _s(o.get("id") or o.get("slug")), "name": _s(o.get("name"))}
        for o in (orgs_raw or [])
        if isinstance(o, dict)
    ]
    projects = []
    for p in projects_raw or []:
        if not isinstance(p, dict):
            continue
        projects.append(
            {
                "id": _s(p.get("ref") or p.get("id")),
                "name": _s(p.get("name")),
                "organization_id": _s(p.get("organization_id") or p.get("organization_slug")),
                "region": _s(p.get("region")),
                "status": _s(p.get("status")),
                "created_at": _s(p.get("created_at")),
                "tables": None,
            }
        )
    sem = asyncio.Semaphore(4)

    async def fill(p: dict[str, Any]) -> None:
        if p["status"] != "ACTIVE_HEALTHY" or not p["id"]:
            return
        async with sem:
            p["tables"] = await _tables(token, p["id"])

    await asyncio.gather(*(fill(p) for p in projects))
    overview = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "organizations": orgs,
        "projects": projects,
        "error": None,
    }
    _write_private(ctx, OVERVIEW_FILE, overview)
    return overview


# --------------------------------------------------------------------------- #
# handlers
# --------------------------------------------------------------------------- #
def _status_body(ctx) -> dict[str, Any]:
    conn = _read(ctx, OAUTH_FILE)
    connected = bool(conn.get("access_token"))
    return {
        "connected": connected,
        "overview": _read(ctx, OVERVIEW_FILE) or None if connected else None,
    }


async def h_status(request: web.Request, ctx) -> web.Response:
    if denied := _require_auth(request):
        return denied
    return web.json_response(_status_body(ctx))


async def h_oauth_start(request: web.Request, ctx) -> web.Response:
    if denied := _require_auth(request):
        return denied
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        origin = _normalize_origin(body.get("origin") or f"{request.scheme}://{request.host}")
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    redirect_uri = origin + CALLBACK_PATH
    async with _lock:
        try:
            client = await _client_for(ctx, redirect_uri)
        except SupabaseError as exc:
            return web.json_response({"error": exc.message}, status=exc.status)
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(32)
        now = time.time()
        pending = {
            k: v
            for k, v in _read(ctx, PENDING_FILE).items()
            if isinstance(v, dict) and now - float(v.get("created_at") or 0) < PENDING_TTL_S
        }
        pending[state] = {
            "verifier": verifier,
            "redirect_uri": redirect_uri,
            "return_to": _safe_return_to(body.get("return_to") or "/"),
            "created_at": now,
        }
        _write_private(ctx, PENDING_FILE, pending)
    url = AUTHORIZE_URL + "?" + urlencode(
        {
            "client_id": client["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return web.json_response({"authorizationUrl": url})


_PAGE_TEXT = {
    "connected": ("Supabase connected", "You can close this window and go back to Kiro Crew."),
    "denied": ("Sign-in canceled", "Supabase sign-in was canceled. You can close this window."),
    "failed": ("Sign-in did not finish", "Supabase sign-in did not finish. Close this window and try again."),
    "expired": ("Link expired", "This sign-in link expired or was already used. Close this window and try again."),
}


def _done_page(result: str) -> web.Response:
    """Small popup page: tells the opener the result, then closes. No token or code is shown."""
    title, message = _PAGE_TEXT.get(result, _PAGE_TEXT["failed"])
    payload = json.dumps({"type": "supabase-oauth-complete", "result": result}).replace("<", "\\u003c")
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title></head>
<body style="margin:0;background:#111827;color:#f9fafb;font:14px system-ui,sans-serif">
<main style="max-width:440px;margin:72px auto;padding:24px">
<h1 style="font-size:20px;margin:0 0 10px">{html.escape(title)}</h1>
<p style="line-height:1.6;color:#d1d5db">{html.escape(message)}</p>
<button type="button" onclick="window.close()" style="margin-top:12px;padding:8px 14px;border:1px solid #4b5563;border-radius:6px;background:#1f2937;color:#f9fafb;cursor:pointer">Close</button>
</main>
<script>
const result = {payload};
if (window.opener) window.opener.postMessage(result, window.location.origin);
if (result.result === "connected") window.setTimeout(() => window.close(), 800);
</script></body></html>"""
    return web.Response(
        text=doc,
        content_type="text/html",
        status=200 if result == "connected" else 400,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        },
    )


async def _complete(ctx, state: str, code: str, error: str) -> str:
    """Finish a sign-in. Returns connected | denied | failed | expired."""
    async with _lock:
        pending = _read(ctx, PENDING_FILE)
        entry = pending.pop(state, None) if state else None
        _write_private(ctx, PENDING_FILE, pending)
    if not isinstance(entry, dict) or time.time() - float(entry.get("created_at") or 0) > PENDING_TTL_S:
        return "expired"
    if error or not code:
        return "denied"
    conn = _read(ctx, OAUTH_FILE)
    client = conn.get("client") or {}
    status, body = await _http(
        "POST",
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": entry["redirect_uri"],
            "code_verifier": entry["verifier"],
            "client_id": client.get("client_id", ""),
            "client_secret": client.get("client_secret", ""),
        },
    )
    if status >= 300 or not isinstance(body, dict):
        logger.warning("supabase code exchange failed: status=%s", status)
        return "failed"
    try:
        _store_tokens(ctx, {"client": client}, body)
    except SupabaseError:
        return "failed"
    _delete(ctx, OVERVIEW_FILE)  # a new account should not show the old one's data
    return "connected"


async def h_oauth_callback(request: web.Request, ctx) -> web.Response:
    """Supabase redirects here. Works when this browser is signed in to Kiro Crew."""
    if denied := _require_auth(request):
        return denied
    q = request.query
    result = await _complete(
        ctx, str(q.get("state") or ""), str(q.get("code") or ""), str(q.get("error") or "")
    )
    return _done_page(result)


async def h_oauth_finish(request: web.Request, ctx) -> web.Response:
    """Finish from a pasted callback address, for a browser not signed in to Kiro Crew.

    The code is single-use, expires in minutes, and is useless without the PKCE
    verifier and client secret that never leave this backend.
    """
    if denied := _require_auth(request):
        return denied
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = str(body.get("url") or "").strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        parts = None
    if not parts or parts.path != CALLBACK_PATH:
        return web.json_response(
            {"error": "That is not the Supabase sign-in address. Copy the full address from the browser tab after you approve."},
            status=400,
        )
    q = parse_qs(parts.query)
    first = lambda k: (q.get(k) or [""])[0]  # noqa: E731
    result = await _complete(ctx, first("state"), first("code"), first("error"))
    status = 200 if result == "connected" else 400
    return web.json_response({"result": result, **_status_body(ctx)}, status=status)


async def h_refresh(request: web.Request, ctx) -> web.Response:
    if denied := _require_auth(request):
        return denied
    try:
        overview = await _build_overview(ctx)
    except SupabaseError as exc:
        return web.json_response({"error": exc.message, **_status_body(ctx)}, status=exc.status)
    return web.json_response({"connected": True, "overview": overview})


async def h_disconnect(request: web.Request, ctx) -> web.Response:
    if denied := _require_auth(request):
        return denied
    async with _lock:
        client = _read(ctx, OAUTH_FILE).get("client")
        if client:
            _write_private(ctx, OAUTH_FILE, {"client": client})
        else:
            _delete(ctx, OAUTH_FILE)
        _delete(ctx, OVERVIEW_FILE)
    return web.json_response({"connected": False, "overview": None})


def register_routes(ctx) -> list[AppRoute]:
    return [
        AppRoute("GET", "/status", h_status),
        AppRoute("POST", "/oauth/start", h_oauth_start),
        AppRoute("GET", "/oauth/callback", h_oauth_callback),
        AppRoute("POST", "/oauth/finish", h_oauth_finish),
        AppRoute("POST", "/oauth/disconnect", h_disconnect),
        AppRoute("POST", "/refresh", h_refresh),
    ]
