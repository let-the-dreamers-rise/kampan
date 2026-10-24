"""The perception-decision-action loop, driven against any World (simulator or a person with a phone)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from kampan.agent.actions import AskHuman, CaptureRequest, ProposeTicket, Recapture, Report
from kampan.agent.config import AgentConfig
from kampan.agent.evidence import Evidence, assess
from kampan.agent.policy import decide
from kampan.agent.trace import Trace
from kampan.measure import Capture


class World(Protocol):
    def capture(self, request: CaptureRequest) -> Capture: ...

    def ask_human(self, question: AskHuman) -> Any: ...


@dataclass(frozen=True)
class AgentResult:
    report: Report
    events: list[dict] = field(repr=False)
    captures: int
    questions: int
    ticket: dict | None = None
    ticket_approved: bool | None = None
    evidence: tuple[Evidence, ...] = field(default=(), repr=False)


def _because(ev: Evidence, rule: str) -> dict:
    m = ev.measurement
    return {
        "rule": rule,
        "fps": ev.fps,
        "timebase": ev.timebase.source,
        "markers": list(ev.marker_ids),
        "jitter_px": ev.camera.jitter_px,
        "anisotropy": ev.scale.anisotropy,
        "roi": ev.roi_source,
        "top_hz": ev.top_hz,
        "snr": m.peaks_px[0].snr if m and m.peaks_px else None,
        "noise_px": m.noise_px if m else None,
        "velocity_mm_s": ev.velocity_mm_s,
        "alias_suspect": ev.alias_suspect,
    }


def run_agent(world: World, cfg: AgentConfig = AgentConfig(), first: CaptureRequest = CaptureRequest(),
              sink: Callable[[dict], None] | None = None) -> AgentResult:
    trace = Trace(sink)
    answers: dict[str, Any] = {}
    history: list[Evidence] = []
    request, captures, questions = first, 1, 0
    capture = world.capture(request)
    trace.capture(0, request, {"container_fps": capture.container_fps, "tag": capture.capture_fps_tag,
                               "label": capture.label})
    while True:
        ev = assess(capture, request, answers, cfg, trace, captures - 1)
        action, rule = decide(ev, tuple(history), answers, cfg)
        trace.decision(action, _because(ev, rule))
        if isinstance(action, AskHuman):
            if questions >= cfg.max_questions:
                return _finish(Report("abstain", "Question budget used up."), trace, captures, questions, history, ev)
            answer = world.ask_human(action)
            questions += 1
            trace.human(action.field, action.question, answer)
            if answer is None and action.field == "capture_fps":
                return _finish(Report("abstain", f"No answer to: {action.question}"), trace, captures, questions,
                               history, ev)
            answers = {**answers, action.field: answer}
            continue
        if isinstance(action, Recapture):
            if captures >= cfg.max_captures:
                return _finish(Report("abstain", f"Capture budget used up; last issue: {action.reason}"), trace,
                               captures, questions, history, ev)
            history.append(ev)
            answers = {k: v for k, v in answers.items() if k != "capture_fps"}  # a new file needs its own answer
            request = action.apply(request)
            capture = world.capture(request)
            trace.capture(captures, request, {"container_fps": capture.container_fps, "tag": capture.capture_fps_tag,
                                              "label": capture.label})
            captures += 1
            continue
        if isinstance(action, ProposeTicket):
            approval = AskHuman("approve_ticket", f"Approve maintenance ticket: {action.ticket['title']}?",
                                "severity zone C or D")
            approved = bool(world.ask_human(approval))
            questions += 1
            trace.human(approval.field, approval.question, approved)
            return _finish(action.report, trace, captures, questions, history, ev, action.ticket, approved)
        return _finish(action, trace, captures, questions, history, ev)


def _finish(report: Report, trace: Trace, captures: int, questions: int, history: list[Evidence], ev: Evidence,
            ticket: dict | None = None, approved: bool | None = None) -> AgentResult:
    return AgentResult(report, trace.events, captures, questions, ticket, approved, (*history, ev))
