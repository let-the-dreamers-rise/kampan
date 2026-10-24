"""A simulated person with a phone: renders a new clip for each capture request, answers questions truthfully.

Used only for evaluation. Every clip it produces is synthetic and labelled as such.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

from kampan.agent.actions import AskHuman, CaptureRequest
from kampan.measure import Capture
from kampan.severity import iso_zone, velocity_rms_mm_s
from kampan.spectrum import Peak
from kampan.synth import SceneSpec, Tone, render


@dataclass(frozen=True)
class Scenario:
    name: str
    tones: tuple[Tone, ...]
    running_hz: float | None = None
    fps: float = 240.0
    base_mm_per_px: float = 0.3
    shake_px: float = 0.0
    markers: bool = True
    reference_marker: bool = True
    tilt_deg: float = 0.0
    untagged_slowmo: bool = False
    noise_sigma: float = 1.5
    duration_s: float = 2.0
    width: int = 480
    height: int = 320
    marker_mm: float = 20.0
    seed: int = 0
    note: str = ""

    def true_velocity(self, band: tuple[float, float] = (10.0, 1000.0)) -> float:
        return velocity_rms_mm_s(tuple(Peak(t.freq_hz, t.amp_mm, 1.0) for t in self.tones), *band)

    def true_zone(self, machine_class: str = "I") -> str:
        return iso_zone(self.true_velocity(), machine_class).zone

    def dominant_hz(self) -> float | None:
        return max(self.tones, key=lambda t: t.amp_mm).freq_hz if self.tones else None


@dataclass
class SimWorld:
    scenario: Scenario
    supersample: int = 3
    captures: list[CaptureRequest] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    _current_fps: float = 0.0

    def _spec(self, request: CaptureRequest, distance: float) -> SceneSpec:
        s = self.scenario
        fps = request.fps or s.fps
        slowmo = s.untagged_slowmo and fps > 60
        return SceneSpec(
            width=s.width, height=s.height, fps=fps, duration_s=max(s.duration_s, 64 / fps),
            mm_per_px=s.base_mm_per_px * distance, tones=s.tones, noise_sigma=s.noise_sigma,
            shake_px=0.0 if request.tripod else s.shake_px, marker_mm=s.marker_mm,
            target_marker=s.markers or request.markers,
            reference_marker=(s.markers and s.reference_marker) or request.markers,
            tilt_deg=0.0 if request.square_on else s.tilt_deg,
            container_fps=30.0 if slowmo else fps, capture_tag=not slowmo,
            seed=s.seed * 1000 + len(self.captures), supersample=self.supersample)

    def capture(self, request: CaptureRequest) -> Capture:
        distance = request.distance
        while True:
            try:
                clip = render(self._spec(request, distance))
                break
            except ValueError:
                distance *= 1.1  # the scene no longer fits the frame: the person cannot get closer
                if distance > 4:
                    raise
        self.captures.append(replace(request, distance=distance))
        self._current_fps = clip.capture_fps
        tag = clip.capture_fps_tag if clip.capture_fps > 60 else None
        return Capture(clip.frames, clip.container_fps, tag, label=f"simulated:{self.scenario.name}")

    def ask_human(self, question: AskHuman) -> Any:
        self.questions.append(question.field)
        if question.field == "capture_fps":
            return self._current_fps
        if question.field == "running_hz":
            return self.scenario.running_hz
        if question.field == "approve_ticket":
            return True
        return None


def scenario_library(seed: int = 0) -> tuple[Scenario, ...]:
    """The evaluation suite. Amplitudes are peak displacement in mm; zones are ISO 10816-1 class I."""
    fan = (Tone(21.0, 0.010), Tone(42.0, 0.0015, phase=1.0))
    fault = (Tone(21.0, 0.035), Tone(42.0, 0.004, phase=1.0))
    return (
        Scenario("clean", fan, 21.0, seed=seed, note="good capture of a healthy machine"),
        Scenario("slowmo-untagged", fan, 21.0, untagged_slowmo=True, seed=seed,
                 note="slow-motion file whose container says 30 fps and carries no capture tag"),
        Scenario("far", (Tone(21.0, 0.0035),), 21.0, base_mm_per_px=0.6, seed=seed,
                 note="camera too far: motion below the noise floor"),
        Scenario("handheld-referenced", fan, 21.0, shake_px=1.2, seed=seed,
                 note="hand shake, static reference marker visible"),
        Scenario("handheld-unreferenced", fan, 21.0, shake_px=1.2, reference_marker=False, seed=seed,
                 note="hand shake, no static reference"),
        Scenario("aliased", (Tone(140.0, 0.006),), None, seed=seed,
                 note="vibration above the Nyquist limit of 240 fps"),
        Scenario("no-markers", fan, 21.0, markers=False, seed=seed, note="no marker in view"),
        Scenario("oblique", (Tone(21.0, 0.022, angle_deg=0.0),), 21.0, tilt_deg=60.0, seed=seed,
                 note="camera at 60 degrees to the machine face, horizontal vibration"),
        Scenario("unbalanced", fault, 21.0, seed=seed, note="coin on a blade: strong 1x"),
        Scenario("machine-off", (), None, seed=seed, note="nothing vibrates"),
    )


def describe(s: Scenario) -> dict:
    return {"name": s.name, "true_hz": s.dominant_hz(), "true_velocity_mm_s": round(s.true_velocity(), 3),
            "true_zone": s.true_zone() if s.tones else "A", "note": s.note,
            "amp_px_at_start": [round(t.amp_mm / s.base_mm_per_px, 4) for t in s.tones], "seed": s.seed,
            "nyquist": s.fps / 2, "aliased": any(t.freq_hz > s.fps / 2 for t in s.tones),
            "two_pi": round(2 * math.pi, 3)}
