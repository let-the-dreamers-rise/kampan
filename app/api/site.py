"""Team and invites: the lead sends a link, the technician opens it and joins."""
from __future__ import annotations

from app.api.account import me_payload
from app.api.context import caller, table
from app.auth import session as sessions
from app.domain import sites, stats
from app.web import Request, ok


def team(req: Request) -> dict:
    c = caller(req)
    data = {"members": sites.members(table(), c.site_id)}
    if c.role == "lead":
        data["invites"] = sites.invites(table(), c.site_id)
    return ok(data)


def create_invite(req: Request) -> dict:
    c = caller(req, "lead")
    return ok(sites.create_invite(table(), c.site_id, c.name))


def preview_invite(req: Request, token: str) -> dict:
    invite = sites.preview_invite(table(), token)
    return ok({k: invite[k] for k in ("site_name", "by_name", "role")})


def accept_invite(req: Request, token: str) -> dict:
    c = caller(req)
    invite = sites.accept_invite(table(), token, c.user_id, c.name)
    stats.feed_add(table(), "join", "A technician joined a site through an invite link")
    _, cookie = sessions.issue(c.user_id, invite["site_id"], "technician")
    return ok(me_payload(c.user_id, invite["site_id"], "technician"), cookies=[cookie])
