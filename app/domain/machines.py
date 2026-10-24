"""Machines registered at a site, their latest reading, and read-only share links."""
from __future__ import annotations

import secrets

from app.domain import stats
from app.domain.common import new_id, now_ms, number, text
from app.repo.table import Table
from app.web import BadRequest, NotFound

CLASSES = ("I", "II", "III", "IV")
PUBLIC_FIELDS = ("machine_id", "name", "location", "machine_class", "rpm", "marker_mm", "created",
                 "measurements", "last_zone", "last_velocity", "last_verdict", "last_at", "last_change")


def parse(data: dict) -> dict:
    machine_class = data.get("machine_class", "I")
    if machine_class not in CLASSES:
        raise BadRequest("machine_class must be I, II, III or IV")
    rpm = data.get("rpm")
    return {"name": text(data.get("name"), "name", 60), "location": text(data.get("location"), "location", 80, False),
            "machine_class": machine_class,
            "rpm": None if rpm in (None, "") else round(number(rpm, "rpm", 30, 60000), 1),
            "marker_mm": round(number(data.get("marker_mm", 40), "marker_mm", 5, 500), 1)}


def create(table: Table, site_id: str, user_id: str, data: dict) -> dict:
    fields = parse(data)
    machine_id = new_id()
    item = {"pk": f"SITE#{site_id}", "sk": f"MACHINE#{machine_id}", "machine_id": machine_id, **fields,
            "created": now_ms(), "created_by": user_id, "measurements": 0}
    table.put(item, if_absent=True)
    stats.bump(table, "machines")
    return public(item)


def public(item: dict) -> dict:
    return {k: item.get(k) for k in PUBLIC_FIELDS}


def get(table: Table, site_id: str, machine_id: str) -> dict:
    item = table.get(f"SITE#{site_id}", f"MACHINE#{machine_id}")
    if item is None:
        raise NotFound("machine not found at this site")
    return item


def all_at(table: Table, site_id: str) -> list[dict]:
    rows = [public(m) for m in table.query(f"SITE#{site_id}", "MACHINE#", limit=500)]
    return sorted(rows, key=lambda m: (m["name"] or "").lower())


def record(table: Table, site_id: str, machine_id: str, saved: dict) -> None:
    current = get(table, site_id, machine_id)
    table.update(f"SITE#{site_id}", f"MACHINE#{machine_id}", {
        "measurements": int(current.get("measurements", 0)) + 1, "last_zone": saved.get("zone"),
        "last_velocity": saved.get("velocity_mm_s"), "last_verdict": saved.get("verdict"),
        "last_at": saved.get("created"), "last_change": (saved.get("change") or {}).get("text")})


def share(table: Table, site_id: str, machine_id: str) -> str:
    machine = get(table, site_id, machine_id)
    if machine.get("share_token"):
        return machine["share_token"]
    token = secrets.token_urlsafe(18)
    table.put({"pk": f"SHARE#{token}", "sk": "SHARE", "site_id": site_id, "machine_id": machine_id,
               "created": now_ms()}, if_absent=True)
    table.update(f"SITE#{site_id}", f"MACHINE#{machine_id}", {"share_token": token})
    return token


def unshare(table: Table, site_id: str, machine_id: str) -> None:
    machine = get(table, site_id, machine_id)
    token = machine.get("share_token")
    if token:
        table.delete(f"SHARE#{token}", "SHARE")
        table.update(f"SITE#{site_id}", f"MACHINE#{machine_id}", {"share_token": None})


def resolve_share(table: Table, token: str) -> tuple[str, dict]:
    item = table.get(f"SHARE#{token}", "SHARE") if isinstance(token, str) and token else None
    if item is None:
        raise NotFound("this share link is not valid or was turned off by the site lead")
    return item["site_id"], get(table, item["site_id"], item["machine_id"])
