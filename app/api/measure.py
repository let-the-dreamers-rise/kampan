"""Uploads and agent sessions: saved for a technician at a site, or a no-account demo on built-in samples."""
from __future__ import annotations

import json

from app import service
from app.api.context import caller, storage, table
from app.domain import machines, measurements, stats, tickets
from app.domain.common import ident
from app.samples import list_samples
from app.repo.table import now
from app.web import BadRequest, Forbidden, Request, ok

UPLOAD_TTL = 86400  # matches the bucket's one-day expiry for uploads/


def samples(req: Request) -> dict:
    return ok({"samples": list_samples()})


def new_upload(req: Request) -> dict:
    c = caller(req, "technician")
    body = req.json()
    target = service.new_upload(storage(), body.get("filename", "clip.mp4"), body.get("content_type", "video/mp4"))
    table().put({"pk": f"UPLOAD#{target['key']}", "sk": "UPLOAD", "site_id": c.site_id, "ttl": now() + UPLOAD_TTL})
    return ok(target)


def _check_uploads(clips: object, site_id: str) -> None:
    """An uploaded clip may only be measured at the site that asked to upload it."""
    for key in clips if isinstance(clips, list) else []:
        if isinstance(key, str) and key.startswith("uploads/"):
            owner = table().get(f"UPLOAD#{key}", "UPLOAD")
            if owner is None or owner.get("site_id") != site_id:
                raise Forbidden("refused: that clip was not uploaded at this site")


def _sample_for(clips: list) -> dict | None:
    if not clips or not all(isinstance(c, str) and c.startswith("samples/") for c in clips):
        return None
    for s in list_samples():
        if clips[0] in s["clips"]:
            return s
    raise BadRequest("unknown sample clip")


def _count(result: dict) -> None:
    if result["status"] == "need_capture":
        stats.bump(table(), "refusals")
    elif result["status"] == "need_answer":
        stats.bump(table(), "questions")


def demo(req: Request) -> dict:
    """No account needed: built-in simulated samples only, nothing is saved."""
    body = req.json()
    sample = _sample_for(body.get("clips"))
    if sample is None:
        raise BadRequest("the demo runs on built-in samples only; sign in to measure your own clips")
    result = service.analyze({"clips": body["clips"], "answers": body.get("answers"), "config": sample["config"]},
                             storage())
    if result["status"] == "done":
        stats.bump(table(), "demo_runs")
    return ok(result)


def measure(req: Request) -> dict:
    c = caller(req, "technician")
    body = req.json()
    machine = machines.get(table(), c.site_id, ident(body.get("machine_id"), "machine_id"))
    session_id = ident(body.get("session_id"), "session_id")
    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        raise BadRequest("answers must be an object")
    _check_uploads(body.get("clips"), c.site_id)
    sample = _sample_for(body.get("clips"))
    config = {"machine_class": machine["machine_class"],
              "marker_mm": sample["config"]["marker_mm"] if sample else machine["marker_mm"]}
    if machine.get("rpm") and not sample and "running_hz" not in answers:
        answers = {**answers, "running_hz": machine["rpm"] / 60.0}  # the agent need not ask what the lead entered
    result = service.analyze({"clips": body.get("clips"), "answers": answers, "config": config}, storage())
    _count(result)
    if result["status"] != "done":
        return ok(result)
    trace_key = f"traces/{c.site_id}/{session_id}.json"
    storage().put_bytes(trace_key, json.dumps({
        "session_id": session_id, "machine": machines.public(machine), "report": result["report"],
        "ticket": result.get("ticket"), "ticket_sent": result.get("ticket_approved"),
        "captures": result.get("captures"), "events": result["events"]}, default=str).encode(), "application/json")
    user = {"user_id": c.user_id, "name": c.name}
    record, created = measurements.save(table(), c.site_id, machine["machine_id"], user, session_id, result,
                                        trace_key, sample is not None)
    if created:
        machines.record(table(), c.site_id, machine["machine_id"], record)
        report = result["report"]
        stats.feed_add(table(), "measurement", f"A class {machine['machine_class']} machine was " + (
            f"graded zone {report.get('zone')}" if report.get("verdict") == "graded" else
            f"measured: {report.get('verdict', '').replace('_', ' ')}"))
        if result.get("ticket") and result.get("ticket_approved"):
            ticket = tickets.open_ticket(table(), c.site_id, machine, record, result["ticket"], c.name)
            record = measurements.attach_ticket(table(), c.site_id, record, ticket["ticket_id"])
    return ok({**result, "saved": measurements.public(record), "machine": machines.public(machine)})
