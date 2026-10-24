"""Sites (a workshop, a plant, a home), who belongs to them, and invite links between roles."""
from __future__ import annotations

import secrets

from app.domain import stats
from app.domain.common import new_id, now_ms
from app.repo.table import ConditionFailed, Table, now
from app.web import Conflict, Forbidden, NotFound

INVITE_DAYS = 7


def create(table: Table, user_id: str, user_name: str, site_name: str) -> str:
    site_id = new_id()
    table.put({"pk": f"SITE#{site_id}", "sk": "META", "site_id": site_id, "name": site_name,
               "created_by": user_id, "created": now_ms()}, if_absent=True)
    add_member(table, site_id, site_name, user_id, user_name, ["lead", "technician"])
    stats.bump(table, "sites")
    return site_id


def get(table: Table, site_id: str) -> dict:
    item = table.get(f"SITE#{site_id}", "META")
    if item is None:
        raise NotFound("site not found")
    return item


def add_member(table: Table, site_id: str, site_name: str, user_id: str, user_name: str, roles: list[str]) -> list[str]:
    existing = table.get(f"SITE#{site_id}", f"MEMBER#{user_id}")
    merged = sorted(set(roles) | set(existing.get("roles", []) if existing else []))
    joined = existing.get("joined", now_ms()) if existing else now_ms()
    table.put({"pk": f"SITE#{site_id}", "sk": f"MEMBER#{user_id}", "user_id": user_id, "name": user_name,
               "roles": merged, "joined": joined})
    table.put({"pk": f"USER#{user_id}", "sk": f"MEMBER#{site_id}", "site_name": site_name, "roles": merged})
    return merged


def roles_of(table: Table, site_id: str, user_id: str) -> list[str]:
    item = table.get(f"SITE#{site_id}", f"MEMBER#{user_id}")
    return list(item.get("roles", [])) if item else []


def require_member(table: Table, site_id: str, user_id: str, role: str) -> None:
    """The session says the role; the membership record must still agree (a removed member loses access)."""
    if role not in roles_of(table, site_id, user_id):
        raise Forbidden(f"refused: you are not a {role} at this site")


def members(table: Table, site_id: str) -> list[dict]:
    return [{"user_id": m["user_id"], "name": m.get("name", ""), "roles": m.get("roles", []), "joined": m.get("joined")}
            for m in table.query(f"SITE#{site_id}", "MEMBER#")]


def create_invite(table: Table, site_id: str, by_name: str) -> dict:
    site = get(table, site_id)
    token = secrets.token_urlsafe(18)
    expires = now() + INVITE_DAYS * 86400
    table.put({"pk": f"INVITE#{token}", "sk": "INVITE", "site_id": site_id, "site_name": site["name"],
               "by_name": by_name, "role": "technician", "used": False, "created": now_ms(), "ttl": expires})
    table.put({"pk": f"SITE#{site_id}", "sk": f"INVITE#{token}", "created": now_ms(), "ttl": expires,
               "used": False})
    return {"token": token, "expires": expires * 1000, "role": "technician"}


def invites(table: Table, site_id: str) -> list[dict]:
    return [{"token": i["sk"].removeprefix("INVITE#"), "created": i.get("created"), "used": i.get("used", False),
             "used_by": i.get("used_by"), "expires": int(i["ttl"]) * 1000}
            for i in table.query(f"SITE#{site_id}", "INVITE#", newest_first=True)]


def preview_invite(table: Table, token: str) -> dict:
    item = table.get(f"INVITE#{token}", "INVITE") if isinstance(token, str) and token else None
    if item is None:
        raise NotFound("this invite link is not valid or has expired; ask your lead for a new one")
    if item.get("used"):
        raise Conflict("this invite link has already been used; ask your lead for a new one")
    return {"site_name": item["site_name"], "by_name": item["by_name"], "role": item["role"],
            "site_id": item["site_id"]}


def accept_invite(table: Table, token: str, user_id: str, user_name: str) -> dict:
    invite = preview_invite(table, token)
    try:
        table.update(f"INVITE#{token}", "INVITE", {"used": True, "used_by": user_name, "used_at": now_ms()},
                     expect={"used": False})
    except ConditionFailed as exc:
        raise Conflict("this invite link has already been used; ask your lead for a new one") from exc
    try:
        table.update(f"SITE#{invite['site_id']}", f"INVITE#{token}", {"used": True, "used_by": user_name})
    except ConditionFailed:
        pass
    add_member(table, invite["site_id"], invite["site_name"], user_id, user_name, [invite["role"]])
    return invite
