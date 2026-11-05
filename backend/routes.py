"""Backend routes for the Supabase page.

Mounted by Kiro Crew under ``/api/apps/supabase`` behind the dashboard's own
sign-in. No new port is opened.

  GET  /api/apps/supabase/overview   -> saved overview + refresh state
  POST /api/apps/supabase/refresh    -> start the supabase-overview agent

The page never talks to Supabase. A refresh starts the app's read-only
``supabase-overview`` agent, which uses the hosted Supabase MCP server (and its
OAuth sign-in) and saves the result through the app's ``save_overview`` tool.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

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

AGENT = "supabase-overview"
OVERVIEW_FILE = "overview.json"
REFRESH_TIMEOUT_S = 300

TASK = (
    "Refresh the Supabase page: list my Supabase organizations, projects and "
    "public tables, then save them with save_overview. Read only."
)

# One refresh at a time per gateway process.
_state: dict[str, Any] = {"spawn_id": "", "started_at": 0.0, "error": ""}


def _unauthorized() -> web.Response:
    return web.json_response({"error": "unauthorized"}, status=401)


def _require_auth(request: web.Request) -> web.Response | None:
    # The gateway already authenticates /api/apps/*; re-check for defence in depth.
    return None if request.get("user") is not None else _unauthorized()


def _data_dir(ctx) -> Path:
    return Path(getattr(ctx, "data_dir", ".") or ".")


def _read_overview(ctx) -> dict[str, Any] | None:
    path = _data_dir(ctx) / OVERVIEW_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("cannot read %s: %s", path, exc)
        return None


def _running(ctx) -> bool:
    spawn_id = _state["spawn_id"]
    if not spawn_id:
        return False
    if time.time() - _state["started_at"] > REFRESH_TIMEOUT_S:
        _state["spawn_id"] = ""
        _state["error"] = "The last refresh timed out."
        return False
    spawn = getattr(ctx, "spawn", None)
    if spawn is not None and spawn.is_done(spawn_id):
        _state["spawn_id"] = ""
        return False
    return True


async def h_overview(request: web.Request, ctx) -> web.Response:
    if denied := _require_auth(request):
        return denied
    return web.json_response(
        {
            "overview": _read_overview(ctx),
            "refreshing": _running(ctx),
            "refresh_error": _state["error"] or None,
        }
    )


async def h_refresh(request: web.Request, ctx) -> web.Response:
    if denied := _require_auth(request):
        return denied
    if _running(ctx):
        return web.json_response({"refreshing": True}, status=202)
    spawn = getattr(ctx, "spawn", None)
    if spawn is None:
        return web.json_response(
            {"error": "This app was not granted the spawn permission."}, status=503
        )
    _state["error"] = ""
    try:
        spawn_id = await spawn.run(TASK, AGENT, silent=True)
    except Exception as exc:  # SpawnError and anything else the host raises
        _state["error"] = f"Could not start a refresh: {exc}"
        logger.warning("supabase refresh spawn failed: %s", exc)
        return web.json_response({"error": _state["error"]}, status=503)
    _state["spawn_id"] = spawn_id
    _state["started_at"] = time.time()
    return web.json_response({"refreshing": True, "spawn_id": spawn_id}, status=202)


def register_routes(ctx) -> list[AppRoute]:
    return [
        AppRoute("GET", "/overview", h_overview),
        AppRoute("POST", "/refresh", h_refresh),
    ]
