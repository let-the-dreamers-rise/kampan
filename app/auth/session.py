"""Signed session cookies. The server reads the user, the active site and the active role from here only."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from app.auth.secret import session_key
from app.web import Forbidden, Request, Unauthorized

COOKIE = "kampan_session"
MAX_AGE = 14 * 24 * 3600
ROLES = ("lead", "technician")


@dataclass(frozen=True)
class Session:
    user_id: str
    site_id: str
    role: str
    expires: int


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(session_key(), payload.encode(), hashlib.sha256).digest())


def encode(session: Session) -> str:
    payload = _b64(json.dumps({"u": session.user_id, "s": session.site_id, "r": session.role,
                               "e": session.expires}, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def decode(token: str) -> Session | None:
    payload, sep, sig = (token or "").partition(".")
    if not sep or not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        data = json.loads(_unb64(payload))
        session = Session(str(data["u"]), str(data["s"]), str(data["r"]), int(data["e"]))
    except (ValueError, KeyError, TypeError):
        return None
    if session.expires < time.time() or session.role not in ROLES:
        return None
    return session


def _attrs(max_age: int) -> str:
    secure = "" if os.environ.get("KAMPAN_INSECURE_COOKIES") else "; Secure"
    return f"; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"


def issue(user_id: str, site_id: str, role: str) -> tuple[Session, str]:
    if role not in ROLES:
        raise ValueError(f"unknown role {role}")
    session = Session(user_id, site_id, role, int(time.time()) + MAX_AGE)
    return session, f"{COOKIE}={encode(session)}{_attrs(MAX_AGE)}"


def clear_cookie() -> str:
    return f"{COOKIE}={_attrs(0)}"


def current(request: Request) -> Session | None:
    return decode(request.cookies.get(COOKIE, ""))


def require(request: Request, role: str | None = None) -> Session:
    """The signed-in session, optionally in a given role. The UI hides actions; this refuses them."""
    session = current(request)
    if session is None:
        raise Unauthorized("sign in first")
    if role is not None and session.role != role:
        raise Forbidden(f"refused: this needs the {role} role; you are signed in as {session.role}")
    return session


def check_origin(request: Request) -> None:
    """Cross-site request guard for state-changing calls (SameSite=Lax covers most; this covers the rest)."""
    origin = request.headers.get("origin")
    if request.method != "GET" and origin is not None and origin.rstrip("/") != request.origin:
        raise Forbidden("refused: request came from another site")
