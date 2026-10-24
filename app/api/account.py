"""Sign-up, sign-in, sign-out, the current account, and switching role."""
from __future__ import annotations

from app.api.context import caller, table
from app.auth import passkeys
from app.auth import session as sessions
from app.domain import machines, measurements, sites, stats, tickets, users
from app.domain.common import text
from app.web import ApiError, BadRequest, Forbidden, Request, ok


def _credential(body: dict) -> dict:
    cred = body.get("credential")
    if not isinstance(cred, dict):
        raise BadRequest("credential is required")
    return cred


def register_options(req: Request) -> dict:
    body = req.json()
    name = text(body.get("name"), "your name", 40)
    if body.get("invite"):
        sites.preview_invite(table(), body["invite"])
    return ok(passkeys.registration_options(table(), req, name))


def register_verify(req: Request) -> dict:
    body = req.json()
    cred = passkeys.verify_registration(table(), req, body.get("challenge_id"), _credential(body))
    user = users.create(table(), cred["user_id"], cred["name"], cred)
    site_id, role = None, "lead"
    if body.get("invite"):
        try:
            site_id, role = sites.accept_invite(table(), body["invite"], user["user_id"], user["name"])["site_id"], \
                "technician"
            stats.feed_add(table(), "join", "A technician joined a site through an invite link")
        except ApiError:
            site_id = None  # the invite was used meanwhile; fall back to an own site
    if site_id is None:
        site_name = text(body.get("site_name") or f"{user['name']}'s site", "site name", 60)
        site_id, role = sites.create(table(), user["user_id"], user["name"], site_name), "lead"
        stats.feed_add(table(), "site", "A new site started measuring with Kampan")
    _, cookie = sessions.issue(user["user_id"], site_id, role)
    return ok(me_payload(user["user_id"], site_id, role), cookies=[cookie])


def login_options(req: Request) -> dict:
    return ok(passkeys.authentication_options(table(), req))


def login_verify(req: Request) -> dict:
    body = req.json()
    user_id = passkeys.verify_authentication(table(), req, body.get("challenge_id"), _credential(body))
    user = users.get(table(), user_id)
    member = users.memberships(table(), user_id)
    if member:
        site_id = member[0]["site_id"]
        role = "lead" if "lead" in member[0]["roles"] else "technician"
    else:
        site_id, role = sites.create(table(), user_id, user["name"], f"{user['name']}'s site"), "lead"
    _, cookie = sessions.issue(user_id, site_id, role)
    return ok(me_payload(user_id, site_id, role), cookies=[cookie])


def logout(req: Request) -> dict:
    return ok({"signed_in": False}, cookies=[sessions.clear_cookie()])


def me(req: Request) -> dict:
    s = sessions.current(req)
    if s is None or s.role not in sites.roles_of(table(), s.site_id, s.user_id):
        return ok({"signed_in": False})
    return ok(me_payload(s.user_id, s.site_id, s.role))


def switch(req: Request) -> dict:
    c = caller(req)
    body = req.json()
    role = body.get("role")
    if role not in sessions.ROLES:
        raise BadRequest("role must be lead or technician")
    named = body.get("site_id")
    owned = [m["site_id"] for m in users.memberships(table(), c.user_id) if role in m["roles"]]
    if named and role in sites.roles_of(table(), named, c.user_id):
        target = named
    elif not named and role in sites.roles_of(table(), c.site_id, c.user_id):
        target = c.site_id
    elif not named and owned:
        target = owned[0]
    elif not named and role == "lead":
        target = sites.create(table(), c.user_id, c.name, f"{c.name}'s site")  # own setup for a new lead
    else:
        raise Forbidden(f"refused: you are not a {role} at that site")
    _, cookie = sessions.issue(c.user_id, target, role)
    return ok(me_payload(c.user_id, target, role), cookies=[cookie])


def progress(site_id: str, user_id: str) -> dict:
    t = table()
    machine_items = t.query(f"SITE#{site_id}", "MACHINE#", limit=500)
    meas = measurements.at_site(t, site_id, limit=1000)
    mine = [m for m in meas if m.get("by_user") == user_id]
    graded_per_machine: dict[str, int] = {}
    for m in meas:
        if m.get("verdict") == "graded":
            graded_per_machine[m["machine_id"]] = graded_per_machine.get(m["machine_id"], 0) + 1
    all_tickets = tickets.at_site(t, site_id)
    return {"machines": len(machine_items), "members": len(sites.members(t, site_id)),
            "measurements": len(meas), "graded": sum(1 for m in meas if m.get("verdict") == "graded"),
            "my_measurements": len(mine), "my_graded": sum(1 for m in mine if m.get("verdict") == "graded"),
            "repeat_machines": sum(1 for n in graded_per_machine.values() if n >= 2),
            "tickets_open": sum(1 for x in all_tickets if x["status"] == "open"),
            "tickets_decided": sum(1 for x in all_tickets if x["status"] != "open"),
            "shared": sum(1 for m in machine_items if m.get("share_token"))}


def me_payload(user_id: str, site_id: str, role: str) -> dict:
    t = table()
    user = users.get(t, user_id)
    site = sites.get(t, site_id)
    return {"signed_in": True, "user": {"user_id": user_id, "name": user["name"]},
            "site": {"site_id": site_id, "name": site["name"]}, "role": role,
            "roles_here": sites.roles_of(t, site_id, user_id), "memberships": users.memberships(t, user_id),
            "progress": progress(site_id, user_id), "machine_count": len(machines.all_at(t, site_id))}
