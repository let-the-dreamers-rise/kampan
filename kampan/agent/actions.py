"""What the agent can do after looking at a capture."""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class CaptureRequest:
    """Capture conditions. distance is relative to the first capture (0.5 = twice as close)."""
    fps: float | None = None
    distance: float = 1.0
    tripod: bool = False
    markers: bool = False
    square_on: bool = False


@dataclass(frozen=True)
class Recapture:
    reason: str
    instruction: str  # what the person holding the phone should do
    fps: float | None = None
    distance_factor: float | None = None
    tripod: bool = False
    add_markers: bool = False
    square_on: bool = False

    def apply(self, request: CaptureRequest) -> CaptureRequest:
        return replace(
            request,
            fps=self.fps if self.fps is not None else request.fps,
            distance=request.distance * (self.distance_factor or 1.0),
            tripod=request.tripod or self.tripod,
            markers=request.markers or self.add_markers,
            square_on=request.square_on or self.square_on,
        )


@dataclass(frozen=True)
class AskHuman:
    field: str  # capture_fps | running_hz | approve_ticket
    question: str
    reason: str


@dataclass(frozen=True)
class Report:
    verdict: str  # graded | below_detection | ambiguous | abstain
    summary: str
    dominant_hz: float | None = None
    velocity_mm_s: float | None = None
    zone: str | None = None
    signature: str | None = None
    alias_candidates: tuple[float, ...] = ()
    upper_bound_mm: float | None = None
    caveats: tuple[str, ...] = ()
    peaks_mm: tuple[tuple[float, float], ...] = ()  # (Hz, mm peak)


@dataclass(frozen=True)
class ProposeTicket:
    report: Report
    ticket: dict = field(default_factory=dict)
