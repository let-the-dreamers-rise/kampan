"""Live counters and the anonymous activity feed behind the public impact page."""
from __future__ import annotations

from app.domain.common import new_id, now_ms
from app.repo.table import Table, now

FIELDS = ("sites", "machines", "measurements", "graded", "refusals", "questions", "tickets",
          "tickets_approved", "tickets_declined", "demo_runs")
FEED_DAYS = 30


def bump(table: Table, field: str, amount: int = 1) -> None:
    if field not in FIELDS:
        raise ValueError(field)
    table.add("STATS", "GLOBAL", field, amount)


def read(table: Table) -> dict:
    item = table.get("STATS", "GLOBAL") or {}
    return {f: int(item.get(f, 0)) for f in FIELDS}


def feed_add(table: Table, kind: str, text: str) -> None:
    table.put({"pk": "FEED", "sk": f"{now_ms():013d}#{new_id(4)}", "kind": kind, "text": text,
               "at": now_ms(), "ttl": now() + FEED_DAYS * 86400})


def feed(table: Table, limit: int = 20) -> list[dict]:
    return [{"kind": i["kind"], "text": i["text"], "at": i["at"]}
            for i in table.query("FEED", limit=limit, newest_first=True)]
