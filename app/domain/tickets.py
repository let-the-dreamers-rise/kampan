"""Maintenance tickets the agent drafts, the technician sends, and the lead decides."""
from __future__ import annotations

from app.domain import stats
from app.domain.common import new_id, now_ms, text
from app.repo.table import ConditionFailed, Table
from app.web import Conflict, NotFound

PUBLIC_FIELDS = ("ticket_id", "machine_id", "machine_name", "measurement_id", "title", "evidence", "zone",
                 "velocity_mm_s", "status", "created", "sent_by", "decided_by", "decided_at", "note")


def open_ticket(table: Table, site_id: str, machine: dict, record: dict, draft: dict, sent_by: str) -> dict:
    ticket_id = new_id()
    item = {"pk": f"SITE#{site_id}", "sk": f"TICKET#{ticket_id}", "ticket_id": ticket_id,
            "machine_id": machine["machine_id"], "machine_name": machine["name"],
            "measurement_id": record["measurement_id"], "title": str(draft.get("title", ""))[:200],
            "evidence": str(draft.get("evidence", ""))[:1000], "zone": record.get("zone"),
            "velocity_mm_s": record.get("velocity_mm_s"), "status": "open", "created": now_ms(), "sent_by": sent_by}
    table.put(item, if_absent=True)
    stats.bump(table, "tickets")
    return public(item)


def public(item: dict) -> dict:
    return {k: item.get(k) for k in PUBLIC_FIELDS}


def at_site(table: Table, site_id: str) -> list[dict]:
    rows = [public(t) for t in table.query(f"SITE#{site_id}", "TICKET#", limit=500)]
    return sorted(rows, key=lambda t: (t["status"] != "open", -(t["created"] or 0)))


def decide(table: Table, site_id: str, ticket_id: str, approve: bool, by_name: str, note: object) -> dict:
    if table.get(f"SITE#{site_id}", f"TICKET#{ticket_id}") is None:
        raise NotFound("ticket not found at this site")
    status = "approved" if approve else "declined"
    try:
        item = table.update(f"SITE#{site_id}", f"TICKET#{ticket_id}",
                            {"status": status, "decided_by": by_name, "decided_at": now_ms(),
                             "note": text(note, "note", 300, False)}, expect={"status": "open"})
    except ConditionFailed as exc:
        raise Conflict("refused: this ticket was already decided") from exc
    stats.bump(table, "tickets_approved" if approve else "tickets_declined")
    return public(item)
