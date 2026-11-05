"""Stdio MCP server for the Supabase Kiro Crew app.

It exposes one tool, ``save_overview``. The background ``supabase-overview``
agent reads your organizations and projects from the hosted Supabase MCP server
(using that server's OAuth sign-in) and hands the result to this tool. The tool
writes it to the app's data directory, where the Supabase page reads it.

Standard library only. stdout is the JSON-RPC channel, so nothing else may
print to it.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SERVER_NAME = "supabase-overview"
SERVER_VERSION = "0.2.0"
PROTOCOL_VERSION = "2025-06-18"
OVERVIEW_FILE = "overview.json"
MAX_BYTES = 2_000_000


def data_dir() -> Path:
    home = os.environ.get("KIROCREW_HOME")
    if home:
        d = Path(home) / "apps" / "supabase" / "data"
    else:
        d = Path(__file__).resolve().parent.parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


SAVE_TOOL = {
    "name": "save_overview",
    "description": (
        "Save the Supabase account overview shown on the Supabase page. "
        "Call it once, after listing organizations and projects. "
        "If a Supabase call failed, call it with only `error` set."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "organizations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["id", "name"],
                },
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Project ref"},
                        "name": {"type": "string"},
                        "organization_id": {"type": "string"},
                        "region": {"type": "string"},
                        "status": {"type": "string"},
                        "created_at": {"type": "string"},
                        "tables": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Table names in the public schema",
                        },
                    },
                    "required": ["id", "name"],
                },
            },
            "error": {"type": "string"},
        },
    },
}


def _clean(value: Any, limit: int = 200) -> str:
    return str(value if value is not None else "")[:limit]


def save_overview(args: dict[str, Any]) -> str:
    orgs = [
        {"id": _clean(o.get("id")), "name": _clean(o.get("name"))}
        for o in (args.get("organizations") or [])
        if isinstance(o, dict)
    ]
    projects = []
    for p in args.get("projects") or []:
        if not isinstance(p, dict):
            continue
        tables = p.get("tables")
        projects.append(
            {
                "id": _clean(p.get("id")),
                "name": _clean(p.get("name")),
                "organization_id": _clean(p.get("organization_id")),
                "region": _clean(p.get("region")),
                "status": _clean(p.get("status")),
                "created_at": _clean(p.get("created_at")),
                "tables": (
                    [_clean(t) for t in tables[:500]] if isinstance(tables, list) else None
                ),
            }
        )
    record = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "organizations": orgs,
        "projects": projects,
        "error": _clean(args.get("error"), 2000) or None,
    }
    body = json.dumps(record, indent=1)
    if len(body) > MAX_BYTES:
        raise ValueError("overview is too large")
    d = data_dir()
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".overview-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, d / OVERVIEW_FILE)
    return f"Saved {len(orgs)} organizations and {len(projects)} projects."


def _reply(msg_id: Any, result: Any = None, error: dict | None = None) -> None:
    out: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def handle(msg: dict[str, Any]) -> None:
    method = msg.get("method")
    msg_id = msg.get("id")
    if msg_id is None:  # notification, e.g. notifications/initialized
        return
    if method == "initialize":
        client_version = (msg.get("params") or {}).get("protocolVersion")
        _reply(
            msg_id,
            {
                "protocolVersion": client_version or PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    elif method == "ping":
        _reply(msg_id, {})
    elif method == "tools/list":
        _reply(msg_id, {"tools": [SAVE_TOOL]})
    elif method == "tools/call":
        params = msg.get("params") or {}
        if params.get("name") != "save_overview":
            _reply(msg_id, error={"code": -32602, "message": "unknown tool"})
            return
        try:
            text = save_overview(params.get("arguments") or {})
            _reply(msg_id, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:  # report as a tool error, keep serving
            _reply(
                msg_id,
                {"content": [{"type": "text", "text": f"save failed: {exc}"}], "isError": True},
            )
    else:
        _reply(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _reply(None, error={"code": -32700, "message": "parse error"})
            continue
        if isinstance(msg, dict):
            handle(msg)


if __name__ == "__main__":
    main()
