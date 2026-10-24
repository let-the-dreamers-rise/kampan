"""AWS Lambda entry point behind a function URL: serves the page and the JSON API.

Routes: GET / and /static/*, GET /api/health, GET /api/samples, POST /api/upload, POST /api/analyze.
Every agent trace event is logged as one JSON line; per-request metrics use CloudWatch Embedded Metric Format.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import traceback
from pathlib import Path
from typing import Any

from app import service
from app.samples import list_samples
from app.storage import storage_from_env
from kampan import __version__

STATIC = Path(__file__).parent / "static"
MAX_BODY = 64 * 1024
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                               "connect-src 'self' https://*.amazonaws.com; base-uri 'none'; form-action 'none'",
}
_STORAGE = None


def storage():
    global _STORAGE
    if _STORAGE is None:
        _STORAGE = storage_from_env()
    return _STORAGE


def _json(status: int, payload: Any) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json", "Cache-Control": "no-store",
                                              **SECURITY_HEADERS}, "body": json.dumps(payload)}


def _static(path: str) -> dict:
    name = "index.html" if path in ("/", "") else path.removeprefix("/static/")
    target = (STATIC / name).resolve()
    if STATIC.resolve() not in target.parents or not target.is_file():
        return _json(404, {"error": "not found"})
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return {"statusCode": 200, "headers": {"Content-Type": ctype, "Cache-Control": "public, max-age=300",
                                           **SECURITY_HEADERS}, "body": target.read_text(encoding="utf-8")}


def _body(event: dict) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    if len(raw) > MAX_BODY:
        raise service.BadRequest("request body too large")
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise service.BadRequest("body must be JSON") from exc
    if not isinstance(data, dict):
        raise service.BadRequest("body must be a JSON object")
    return data


def _log(kind: str, request_id: str, **fields: Any) -> None:
    print(json.dumps({"kind": kind, "request_id": request_id, **fields}, default=str))


def _metrics(request_id: str, result: dict, seconds: float) -> None:
    report = result.get("report") or {}
    print(json.dumps({
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": "Kampan", "Dimensions": [["Status"]],
            "Metrics": [{"Name": "AnalyzeSeconds", "Unit": "Seconds"}, {"Name": "AgentEvents", "Unit": "Count"}]}]},
        "Status": result.get("status", "error"), "AnalyzeSeconds": round(seconds, 2),
        "AgentEvents": len(result.get("events", [])), "Verdict": report.get("verdict"), "request_id": request_id}))


def route(event: dict) -> dict:
    http = event.get("requestContext", {}).get("http", {})
    method, path = http.get("method", "GET"), event.get("rawPath", "/")
    request_id = event.get("requestContext", {}).get("requestId", "local")
    if method == "GET" and (path == "/" or path.startswith("/static/")):
        return _static(path)
    if method == "GET" and path == "/api/health":
        return _json(200, {"ok": True, "version": __version__, "storage": type(storage()).__name__})
    if method == "GET" and path == "/api/samples":
        return _json(200, {"samples": list_samples()})
    if method == "POST" and path == "/api/upload":
        body = _body(event)
        return _json(200, service.new_upload(storage(), body.get("filename", "clip.mp4"),
                                             body.get("content_type", "video/mp4")))
    if method == "POST" and path == "/api/analyze":
        body = _body(event)
        t0 = time.perf_counter()
        result = service.analyze(body, storage())
        for e in result["events"]:
            if e["kind"] != "tool":
                _log("agent_event", request_id, event=e)
        _metrics(request_id, result, time.perf_counter() - t0)
        return _json(200, result)
    return _json(404, {"error": "not found"})


def handler(event: dict, context: Any = None) -> dict:
    request_id = event.get("requestContext", {}).get("requestId", "local")
    try:
        return route(event)
    except service.BadRequest as exc:
        _log("bad_request", request_id, error=str(exc))
        return _json(400, {"error": str(exc)})
    except Exception:  # noqa: BLE001 - last resort: log the detail, return a safe message
        _log("error", request_id, trace=traceback.format_exc())
        return _json(500, {"error": "analysis failed; the request id is in the server log", "request_id": request_id})


if os.environ.get("KAMPAN_DEBUG_IMPORT"):
    print("handler imported")
