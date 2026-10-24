"""Pages anyone can open: the live impact numbers and a lead's read-only machine report."""
from __future__ import annotations

from app.api.context import table
from app.domain import machines, measurements, sites, stats
from app.web import Request, ok


def impact(req: Request) -> dict:
    return ok({"stats": stats.read(table()), "feed": stats.feed(table(), 25)})


def shared_machine(req: Request, token: str) -> dict:
    site_id, item = machines.resolve_share(table(), token)
    rows = [measurements.public(m, with_people=False) for m in measurements.for_machine(table(), site_id,
                                                                                         item["machine_id"])]
    return ok({"site": sites.get(table(), site_id)["name"], "machine": machines.public(item), "measurements": rows})
