"""The API's work: validate input, load clips, replay the agent session, attach pictures to the answer."""
from __future__ import annotations

import math
import tempfile
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any

from app.storage import Storage, check_clip_key
from app.web import BadRequest
from kampan.agent.config import AgentConfig
from kampan.agent.trace import to_jsonable
from kampan.measure import Capture
from kampan.session import run_session
from kampan.severity import ZONE_LIMITS
from kampan.video_io import load_video
from kampan.visual import annotated_frame, filmstrip, spectrum_series, to_jpeg_b64

MAX_CLIPS = 5
ALLOWED_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/3gpp",
                 "application/octet-stream"}
_CACHE: "OrderedDict[str, Capture]" = OrderedDict()
_CACHE_SIZE = 6


def _number(value: Any, lo: float, hi: float, name: str) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must be a number") from exc
    if not (lo <= x <= hi) or math.isnan(x):
        raise BadRequest(f"{name} must be between {lo} and {hi}")
    return x


def parse_config(raw: dict | None) -> AgentConfig:
    raw = raw or {}
    marker = _number(raw.get("marker_mm", 40.0), 5.0, 500.0, "marker_mm")
    machine_class = str(raw.get("machine_class", "I"))
    if machine_class not in ZONE_LIMITS:
        raise BadRequest("machine_class must be I, II, III or IV")
    rates = raw.get("phone_rates")
    if rates is None:
        return AgentConfig(marker_mm=marker, machine_class=machine_class)
    if not isinstance(rates, list) or not 1 <= len(rates) <= 12:
        raise BadRequest("phone_rates must be a list of 1 to 12 numbers")
    parsed = tuple(sorted({_number(r, 1.0, 1000.0, "phone_rates") for r in rates}))
    return AgentConfig(marker_mm=marker, machine_class=machine_class, phone_rates=parsed)


def parse_answers(raw: dict | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in (raw or {}).items():
        if key.startswith("capture_fps:") and key[12:].isdigit():
            out[key] = _number(value, 1.0, 10000.0, key)
        elif key == "running_hz":
            out[key] = None if value in (None, "", "unknown") else _number(value, 0.5, 2000.0, key)
        elif key == "approve_ticket":
            if not isinstance(value, bool):
                raise BadRequest("approve_ticket must be true or false")
            out[key] = value
        else:
            raise BadRequest(f"unknown answer: {key}")
    return out


def new_upload(storage: Storage, filename: str, content_type: str) -> dict:
    if content_type not in ALLOWED_TYPES:
        raise BadRequest("upload a video file (mp4, mov, avi, webm, 3gp)")
    suffix = Path(str(filename)).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".webm", ".3gp", ".m4v"}:
        suffix = ".mp4"
    key = f"uploads/{uuid.uuid4().hex}{suffix}"
    return {"key": key, **storage.upload_target(key, content_type)}


def _load(storage: Storage, key: str) -> Capture:
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    with tempfile.TemporaryDirectory() as tmp:
        path = storage.download(key, Path(tmp) / Path(key).name)
        video = load_video(path)
    capture = Capture(video.frames, video.container_fps, video.capture_fps_tag, label=key)
    _CACHE[key] = capture
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return capture


def _visuals(result, captures: list[Capture]) -> dict:
    ev = result.evidence[-1]
    frames = captures[min(ev.index, len(captures) - 1)].frames
    m = ev.measurement
    out: dict[str, Any] = {"frame": to_jpeg_b64(annotated_frame(frames, m.rect if m else None,
                                                                 m.angle_rad if m else None))}
    if m is None:
        return out
    mm = ev.scale.scale.mm_per_px_along(m.angle_rad) if ev.scale.scale is not None else None
    out["spectrum"] = spectrum_series(frames, ev.fps, m.rect, m.angle_rad, ev.camera, mm)
    if m.peaks_px:
        out["filmstrip"] = filmstrip(frames, ev.fps, m.peaks_px[0].freq_hz, m.rect)
    return out


def _capture_summaries(result) -> list[dict]:
    rows = []
    for ev in result.evidence:
        m = ev.measurement
        rows.append({"index": ev.index, "fps": ev.fps, "timebase": ev.timebase.source, "markers": list(ev.marker_ids),
                     "mm_per_px": ev.scale.mm_per_px, "jitter_px": ev.camera.jitter_px, "roi": ev.roi_source,
                     "top_hz": ev.top_hz, "noise_px": m.noise_px if m else None,
                     "velocity_mm_s": ev.velocity_mm_s, "request": to_jsonable(ev.request)})
    return rows


def analyze(body: dict, storage: Storage) -> dict:
    clips = body.get("clips")
    if not isinstance(clips, list) or not 1 <= len(clips) <= MAX_CLIPS:
        raise BadRequest(f"clips must be a list of 1 to {MAX_CLIPS} keys")
    try:
        keys = [check_clip_key(k) for k in clips]
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    cfg = parse_config(body.get("config"))
    answers = parse_answers(body.get("answers"))
    t0 = time.perf_counter()
    try:
        captures = [_load(storage, k) for k in keys]
    except (ValueError, FileNotFoundError) as exc:
        raise BadRequest(f"could not read a clip: {exc}") from exc
    session = run_session(captures, answers, cfg)
    response: dict[str, Any] = {"status": session.status, "events": session.events,
                                "seconds": round(time.perf_counter() - t0, 2)}
    if session.status == "need_capture":
        response.update(instruction=session.instruction, reason=session.reason)
    elif session.status == "need_answer":
        q = session.question
        response.update(question={"field": q.field, "text": q.question, "reason": q.reason},
                        answer_key=session.answer_key)
    else:
        r = session.result
        response.update(report=to_jsonable(r.report), ticket=r.ticket, ticket_approved=r.ticket_approved,
                        captures=_capture_summaries(r), visuals=_visuals(r, captures),
                        zone_limits=list(ZONE_LIMITS[cfg.machine_class]))
    return response
