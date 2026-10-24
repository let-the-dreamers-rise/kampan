"""Machines, their measurement history, traces, share links, tickets and site activity."""
from __future__ import annotations

import json

from app.api.context import caller, storage, table
from app.domain import machines, measurements, stats, tickets
from app.domain.common import ident
from app.web import BadRequest, NotFound, Request, ok


def list_machines(req: Request) -> dict:
    c = caller(req)
    return ok({"machines": machines.all_at(table(), c.site_id)})


def create_machine(req: Request) -> dict:
    c = caller(req, "lead")
    machine = machines.create(table(), c.site_id, c.user_id, req.json())
    stats.feed_add(table(), "machine", f"A class {machine['machine_class']} machine was registered")
    return ok(machine, status=201)


def machine_detail(req: Request, machine_id: str) -> dict:
    c = caller(req)
    item = machines.get(table(), c.site_id, ident(machine_id, "machine id"))
    data = {"machine": machines.public(item),
            "measurements": [measurements.public(m) for m in measurements.for_machine(table(), c.site_id,
                                                                                       item["machine_id"])]}
    if c.role == "lead":
        data["share_token"] = item.get("share_token")
    return ok(data)


def share_machine(req: Request, machine_id: str) -> dict:
    c = caller(req, "lead")
    return ok({"share_token": machines.share(table(), c.site_id, ident(machine_id, "machine id"))})


def unshare_machine(req: Request, machine_id: str) -> dict:
    c = caller(req, "lead")
    machines.unshare(table(), c.site_id, ident(machine_id, "machine id"))
    return ok({"share_token": None})


def trace(req: Request, machine_id: str, measurement_id: str) -> dict:
    c = caller(req)
    record = measurements.get(table(), c.site_id, ident(machine_id, "machine id"), ident(measurement_id,
                                                                                          "measurement id"))
    if not record.get("trace_key"):
        raise NotFound("no trace was stored for this measurement")
    try:
        return ok(json.loads(storage().get_bytes(record["trace_key"])))
    except FileNotFoundError as exc:
        raise NotFound("the trace file is missing") from exc


def activity(req: Request) -> dict:
    c = caller(req)
    names = {m["machine_id"]: m["name"] for m in machines.all_at(table(), c.site_id)}
    rows = [{**measurements.public(m), "machine_name": names.get(m["machine_id"], "(removed)")}
            for m in measurements.at_site(table(), c.site_id, limit=100)]
    return ok({"measurements": rows})


def list_tickets(req: Request) -> dict:
    c = caller(req)
    return ok({"tickets": tickets.at_site(table(), c.site_id)})


def decide_ticket(req: Request, ticket_id: str) -> dict:
    c = caller(req, "lead")
    body = req.json()
    approve = body.get("approve")
    if not isinstance(approve, bool):
        raise BadRequest("approve must be true or false")
    ticket = tickets.decide(table(), c.site_id, ident(ticket_id, "ticket id"), approve, c.name, body.get("note"))
    stats.feed_add(table(), "ticket", f"A lead {ticket['status']} a zone {ticket.get('zone') or '?'} maintenance ticket")
    return ok(ticket)
