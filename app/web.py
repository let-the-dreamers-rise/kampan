"""HTTP plumbing shared by every route: the request view, the { ok, data } envelope, typed errors, cookies."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

MAX_BODY = 64 * 1024
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                               "connect-src 'self' https://*.amazonaws.com; base-uri 'none'; form-action 'none'",
}


class ApiError(Exception):
    status = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadRequest(ApiError, ValueError):
    status = 400


class Unauthorized(ApiError):
    status = 401


class Forbidden(ApiError):
    status = 403


class NotFound(ApiError):
    status = 404


class Conflict(ApiError):
    status = 409


class TooManyRequests(ApiError):
    status = 429


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    headers: dict[str, str]
    cookies: dict[str, str]
    raw_body: str
    ip: str
    request_id: str
    query: dict[str, str] = field(default_factory=dict)

    def json(self) -> dict:
        if len(self.raw_body) > MAX_BODY:
            raise BadRequest("request body too large")
        try:
            data = json.loads(self.raw_body or "{}")
        except json.JSONDecodeError as exc:
            raise BadRequest("body must be JSON") from exc
        if not isinstance(data, dict):
            raise BadRequest("body must be a JSON object")
        return data

    @property
    def host(self) -> str:
        return self.headers.get("host", "").lower()

    @property
    def origin(self) -> str:
        proto = self.headers.get("x-forwarded-proto", "https")
        return f"{proto}://{self.host}"


def parse_cookies(items: list[str] | None, header: str | None) -> dict[str, str]:
    pairs = list(items or []) + [p for p in (header or "").split(";") if p.strip()]
    out: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.strip().partition("=")
        if sep and name:
            out[name] = value
    return out


def request_from_event(event: dict) -> Request:
    ctx = event.get("requestContext", {})
    http = ctx.get("http", {})
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    raw = event.get("body") or ""
    if event.get("isBase64Encoded") and raw:
        raw = base64.b64decode(raw).decode("utf-8", "replace")
    return Request(method=http.get("method", "GET").upper(), path=event.get("rawPath", "/"), headers=headers,
                   cookies=parse_cookies(event.get("cookies"), headers.get("cookie")), raw_body=raw,
                   ip=http.get("sourceIp", "local"), request_id=ctx.get("requestId", "local"),
                   query=dict(event.get("queryStringParameters") or {}))


def ok(data: Any = None, status: int = 200, cookies: list[str] | None = None) -> dict:
    return _respond(status, {"ok": True, "data": data}, cookies)


def fail(status: int, message: str, cookies: list[str] | None = None, **extra: Any) -> dict:
    return _respond(status, {"ok": False, "error": message, **extra}, cookies)


def _respond(status: int, payload: dict, cookies: list[str] | None) -> dict:
    response = {"statusCode": status, "headers": {"Content-Type": "application/json", "Cache-Control": "no-store",
                                                  **SECURITY_HEADERS}, "body": json.dumps(payload, default=str)}
    if cookies:
        response["cookies"] = cookies
    return response
