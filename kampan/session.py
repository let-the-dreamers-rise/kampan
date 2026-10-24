"""Run the agent against a person through a stateless web session.

The session is the list of clips uploaded so far plus the answers given. Every request replays the agent
from the first clip; it stops at the first point where it needs something the session does not have yet:
a new clip (with the agent's instruction) or an answer (with the agent's question).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from kampan.agent.actions import AskHuman, CaptureRequest, Recapture
from kampan.agent.config import AgentConfig
from kampan.agent.loop import AgentResult, run_agent
from kampan.measure import Capture


class NeedCapture(Exception):
    def __init__(self, request: CaptureRequest) -> None:
        super().__init__("need capture")
        self.request = request


class NeedAnswer(Exception):
    def __init__(self, question: AskHuman, capture_index: int) -> None:
        super().__init__("need answer")
        self.question = question
        self.capture_index = capture_index


@dataclass
class ReplayWorld:
    clips: Sequence[Capture]
    answers: dict[str, Any]
    served: int = 0
    requests: list[CaptureRequest] = field(default_factory=list)

    def capture(self, request: CaptureRequest) -> Capture:
        if self.served >= len(self.clips):
            raise NeedCapture(request)
        self.requests.append(request)
        self.served += 1
        return self.clips[self.served - 1]

    def ask_human(self, question: AskHuman) -> Any:
        key = answer_key(question.field, self.served - 1)
        if key not in self.answers:
            raise NeedAnswer(question, self.served - 1)
        return self.answers[key]


def answer_key(field_name: str, capture_index: int) -> str:
    """Frame-rate answers belong to one file; other answers hold for the whole session."""
    return f"capture_fps:{capture_index}" if field_name == "capture_fps" else field_name


@dataclass(frozen=True)
class SessionResult:
    status: str  # done | need_capture | need_answer
    events: list[dict]
    result: AgentResult | None = None
    instruction: str | None = None
    reason: str | None = None
    question: AskHuman | None = None
    answer_key: str | None = None


def run_session(clips: Sequence[Capture], answers: dict[str, Any], cfg: AgentConfig) -> SessionResult:
    events: list[dict] = []
    sink: Callable[[dict], None] = events.append
    world = ReplayWorld(clips, answers)
    try:
        result = run_agent(world, cfg, sink=sink)
    except NeedCapture:
        last = next((e for e in reversed(events) if e["kind"] == "decision" and e["action"] == "Recapture"), None)
        detail = last["detail"] if last else {}
        return SessionResult("need_capture", events, instruction=detail.get("instruction"),
                             reason=detail.get("reason"))
    except NeedAnswer as need:
        return SessionResult("need_answer", events, question=need.question, reason=need.question.reason,
                             answer_key=answer_key(need.question.field, need.capture_index))
    return SessionResult("done", result.events, result=result)


def requested_conditions(events: list[dict]) -> list[dict]:
    """The capture requests in order, for showing what each clip was supposed to fix."""
    return [e["request"] for e in events if e["kind"] == "capture"]


__all__ = ["run_session", "SessionResult", "answer_key", "requested_conditions", "Recapture"]
