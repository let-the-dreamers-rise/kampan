"""AWS Lambda entry point behind a function URL: serves the page and the JSON API.

Every API response is { ok, data } or { ok: false, error }. Every route is rate-limited per client address,
state-changing calls must come from this site, and each handler checks the caller's role on the server.
Agent trace events are logged as JSON lines; per-request metrics use CloudWatch Embedded Metric Format.
"""
from __future__ import annotations

import json
import mimetypes
import time
import traceback
from pathlib import Path
from typing import Any

from app import routes
from app.api.context import storage, table  # noqa: F401  (storage re-exported for tests)
from app.auth.session import check_origin
from app.domain import ratelimit
from app.web import SECURITY_HEADERS, ApiError, Request, fail, ok, request_from_event
from kampan import __version__

STATIC = Path(__file__).parent / "static"
PAGES = {"/", "/index.html"}


def _static(path: str) -> dict:
    name = "index.html" if path in PAGES else path.removeprefix("/static/")
    target = (STATIC / name).resolve()
    if STATIC.resolve() not in target.parents or not target.is_file():
        return fail(404, "not found")
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if target.suffix == ".js":
        ctype = "text/javascript"
    cache = "no-cache" if name == "index.html" else "public, max-age=60"
    return {"statusCode": 200, "headers": {"Content-Type": ctype, "Cache-Control": cache, **SECURITY_HEADERS},
            "body": target.read_text(encoding="utf-8")}


def _log(kind: str, request_id: str, **fields: Any) -> None:
    print(json.dumps({"kind": kind, "request_id": request_id, **fields}, default=str))


def _metrics(request_id: str, path: str, data: dict, seconds: float) -> None:
    report = data.get("report") or {}
    print(json.dumps({
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": "Kampan", "Dimensions": [["Status"]],
            "Metrics": [{"Name": "AnalyzeSeconds", "Unit": "Seconds"}, {"Name": "AgentEvents", "Unit": "Count"}]}]},
        "Status": data.get("status", "error"), "AnalyzeSeconds": round(seconds, 2),
        "AgentEvents": len(data.get("events", [])), "Verdict": report.get("verdict"), "path": path,
        "request_id": request_id}))


def route(req: Request) -> dict:
    if req.method == "GET" and (req.path in PAGES or req.path.startswith("/static/")):
        return _static(req.path)
    if req.method == "GET" and req.path == "/api/health":
        return ok({"version": __version__, "storage": type(storage()).__name__, "table": type(table()).__name__})
    found = routes.match(req.method, req.path)
    if found is None:
        return fail(405 if routes.path_exists(req.path) else 404, "not found")
    fn, group, args = found
    ratelimit.check(table(), req.ip, group)
    check_origin(req)
    t0 = time.perf_counter()
    response = fn(req, *args)
    if group == "measure" and response["statusCode"] == 200:
        data = json.loads(response["body"])["data"]
        for e in data.get("events", []):
            if e.get("kind") != "tool":
                _log("agent_event", req.request_id, event=e)
        _metrics(req.request_id, req.path, data, time.perf_counter() - t0)
    return response


def handler(event: dict, context: Any = None) -> dict:
    req = request_from_event(event)
    try:
        return route(req)
    except ApiError as exc:
        _log("refused", req.request_id, status=exc.status, error=exc.message, path=req.path)
        return fail(exc.status, exc.message)
    except Exception:  # noqa: BLE001 - last resort: log the detail, return a safe message
        _log("error", req.request_id, trace=traceback.format_exc(), path=req.path)
        return fail(500, "something failed on our side; the request id is in the server log",
                    request_id=req.request_id)
