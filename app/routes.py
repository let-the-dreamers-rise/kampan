"""The route table: method, path pattern, handler, rate-limit group."""
from __future__ import annotations

import re
from typing import Callable

from app.api import account, fleet, measure, public, site

ID = r"([A-Za-z0-9_-]{6,64})"
Route = tuple[str, re.Pattern, Callable, str]


def _r(method: str, pattern: str, fn: Callable, group: str) -> Route:
    return method, re.compile(f"^{pattern}$"), fn, group


ROUTES: list[Route] = [
    _r("POST", "/api/auth/register/options", account.register_options, "auth"),
    _r("POST", "/api/auth/register/verify", account.register_verify, "auth"),
    _r("POST", "/api/auth/login/options", account.login_options, "auth"),
    _r("POST", "/api/auth/login/verify", account.login_verify, "auth"),
    _r("POST", "/api/auth/logout", account.logout, "write"),
    _r("GET", "/api/me", account.me, "read"),
    _r("POST", "/api/session/switch", account.switch, "write"),
    _r("GET", "/api/team", site.team, "read"),
    _r("POST", "/api/team/invites", site.create_invite, "write"),
    _r("GET", f"/api/invites/{ID}", site.preview_invite, "read"),
    _r("POST", f"/api/invites/{ID}/accept", site.accept_invite, "auth"),
    _r("GET", "/api/machines", fleet.list_machines, "read"),
    _r("POST", "/api/machines", fleet.create_machine, "write"),
    _r("GET", f"/api/machines/{ID}", fleet.machine_detail, "read"),
    _r("POST", f"/api/machines/{ID}/share", fleet.share_machine, "write"),
    _r("POST", f"/api/machines/{ID}/unshare", fleet.unshare_machine, "write"),
    _r("GET", f"/api/machines/{ID}/measurements/{ID}/trace", fleet.trace, "read"),
    _r("GET", "/api/activity", fleet.activity, "read"),
    _r("GET", "/api/tickets", fleet.list_tickets, "read"),
    _r("POST", f"/api/tickets/{ID}/decision", fleet.decide_ticket, "write"),
    _r("GET", "/api/samples", measure.samples, "read"),
    _r("POST", "/api/uploads", measure.new_upload, "write"),
    _r("POST", "/api/measure", measure.measure, "measure"),
    _r("POST", "/api/demo/analyze", measure.demo, "measure"),
    _r("GET", "/api/impact", public.impact, "read"),
    _r("GET", f"/api/share/{ID}", public.shared_machine, "read"),
]


def match(method: str, path: str) -> tuple[Callable, str, tuple[str, ...]] | None:
    """Handler, group and path arguments; None when nothing matches the path at all."""
    for m, pattern, fn, group in ROUTES:
        found = pattern.match(path)
        if found and m == method:
            return fn, group, found.groups()
    return None


def path_exists(path: str) -> bool:
    return any(p.match(path) for _, p, _, _ in ROUTES)
