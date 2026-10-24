"""People and their passkeys."""
from __future__ import annotations

from app.domain.common import now_ms
from app.repo.table import Table
from app.web import NotFound


def create(table: Table, user_id: str, name: str, credential: dict) -> dict:
    profile = {"pk": f"USER#{user_id}", "sk": "PROFILE", "user_id": user_id, "name": name, "created": now_ms()}
    table.put(profile, if_absent=True)
    cred = {"user_id": user_id, "public_key": credential["public_key"],
            "sign_count": int(credential.get("sign_count", 0)), "created": now_ms()}
    table.put({"pk": f"CRED#{credential['credential_id']}", "sk": "CRED", **cred}, if_absent=True)
    table.put({"pk": f"USER#{user_id}", "sk": f"CRED#{credential['credential_id']}", "created": now_ms()})
    return profile


def get(table: Table, user_id: str) -> dict:
    item = table.get(f"USER#{user_id}", "PROFILE")
    if item is None:
        raise NotFound("account not found")
    return item


def memberships(table: Table, user_id: str) -> list[dict]:
    return [{"site_id": m["sk"].removeprefix("MEMBER#"), "site_name": m.get("site_name", ""),
             "roles": list(m.get("roles", []))} for m in table.query(f"USER#{user_id}", "MEMBER#")]
