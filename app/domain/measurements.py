"""Saved measurements: one record per finished agent session, compared with the machine's previous reading."""
from __future__ import annotations

from app.domain import stats
from app.domain.common import new_id, now_ms
from app.repo.table import ConditionFailed, Table
from app.web import NotFound

PUBLIC_FIELDS = ("measurement_id", "machine_id", "verdict", "zone", "velocity_mm_s", "dominant_hz", "signature",
                 "summary", "caveats", "clips", "questions", "created", "change", "ticket_id", "sample")
CHANGE_ALERT = 0.25  # a 25% rise in velocity is worth a look even inside the same zone


def change_from(previous: dict | None, velocity: float | None) -> dict | None:
    if previous is None or velocity is None or not previous.get("velocity_mm_s"):
        return None
    before = float(previous["velocity_mm_s"])
    ratio = velocity / before - 1.0
    direction = "up" if ratio > 0 else "down"
    text = f"{direction} {abs(ratio) * 100:.0f}% since the previous reading ({before:.2f} mm/s)"
    return {"previous_velocity": before, "ratio": round(ratio, 3), "alert": ratio >= CHANGE_ALERT, "text": text}


def for_machine(table: Table, site_id: str, machine_id: str, limit: int = 100) -> list[dict]:
    rows = table.query(f"SITE#{site_id}", f"MEAS#{machine_id}#", limit=limit, newest_first=True)
    return [r for r in rows]


def latest(table: Table, site_id: str, machine_id: str) -> dict | None:
    rows = [r for r in for_machine(table, site_id, machine_id, 20) if r.get("verdict") == "graded"]
    return rows[0] if rows else None


def at_site(table: Table, site_id: str, limit: int = 50) -> list[dict]:
    rows = table.query(f"SITE#{site_id}", "MEAS#", limit=1000)
    return sorted(rows, key=lambda r: r.get("created", 0), reverse=True)[:limit]


def public(item: dict, with_people: bool = True) -> dict:
    out = {k: item.get(k) for k in PUBLIC_FIELDS}
    if with_people:
        out["by_name"] = item.get("by_name")
        out["by_user"] = item.get("by_user")
    return out


def get(table: Table, site_id: str, machine_id: str, measurement_id: str) -> dict:
    item = table.get(f"SITE#{site_id}", f"MEAS#{machine_id}#{measurement_id}")
    if item is None:
        raise NotFound("measurement not found at this site")
    return item


def save(table: Table, site_id: str, machine_id: str, user: dict, session_id: str, result: dict,
         trace_key: str | None, sample: bool) -> tuple[dict, bool]:
    """Store a finished session once. Returns (record, created); a repeated call returns the first record."""
    guard = {"pk": f"RUN#{session_id}", "sk": "RUN", "site_id": site_id, "machine_id": machine_id}
    measurement_id = f"{now_ms():013d}-{new_id(3)}"
    try:
        table.put({**guard, "measurement_id": measurement_id}, if_absent=True)
    except ConditionFailed:
        first = table.get(f"RUN#{session_id}", "RUN")
        if first is None or first["site_id"] != site_id:
            raise NotFound("this session belongs to another site") from None
        return get(table, site_id, first["machine_id"], first["measurement_id"]), False
    report = result.get("report") or {}
    velocity = report.get("velocity_mm_s")
    record = {"pk": f"SITE#{site_id}", "sk": f"MEAS#{machine_id}#{measurement_id}", "measurement_id": measurement_id,
              "machine_id": machine_id, "verdict": report.get("verdict"), "zone": report.get("zone"),
              "velocity_mm_s": velocity, "dominant_hz": report.get("dominant_hz"),
              "signature": report.get("signature"), "summary": report.get("summary"),
              "caveats": list(report.get("caveats") or []), "clips": len(result.get("captures") or []),
              "questions": sum(1 for e in result.get("events", []) if e.get("kind") == "human"),
              "created": now_ms(), "by_user": user["user_id"], "by_name": user["name"], "trace_key": trace_key,
              "change": change_from(latest(table, site_id, machine_id), velocity) if not sample else None,
              "sample": sample, "session_id": session_id}
    table.put(record, if_absent=True)
    stats.bump(table, "measurements")
    if record["verdict"] == "graded":
        stats.bump(table, "graded")
    return record, True


def attach_ticket(table: Table, site_id: str, record: dict, ticket_id: str) -> dict:
    return table.update(f"SITE#{site_id}", record["sk"], {"ticket_id": ticket_id})
