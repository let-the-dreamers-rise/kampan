"""Decision: ordered rules over the evidence. The first rule that fires decides the next action.

Every rule cites the measured quantity that triggered it, so the trace shows how OpenCV output
changed what the agent did next.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from kampan.agent.actions import AskHuman, ProposeTicket, Recapture, Report
from kampan.agent.config import AgentConfig
from kampan.agent.evidence import Evidence
from kampan.dealias import best_next_rate, dealias
from kampan.diagnose import diagnose
from kampan.measure import MIN_SNR
from kampan.severity import iso_zone, velocity_rms_mm_s

Action = Recapture | AskHuman | Report | ProposeTicket


@dataclass(frozen=True)
class Context:
    ev: Evidence
    history: tuple[Evidence, ...]
    answers: dict
    cfg: AgentConfig


def rule_timebase(c: Context) -> Action | None:
    if not c.ev.timebase.trusted and "capture_fps" not in c.answers:
        return AskHuman("capture_fps", "What frame rate did you record at? For slow motion, enter the slow-motion "
                        "rate (for example 240).", c.ev.timebase.note)
    return None


def rule_shake(c: Context) -> Action | None:
    cam, req, cfg = c.ev.camera, c.ev.request, c.cfg
    if req.tripod:
        return None
    shake = f" with a {cam.shake_hz:.1f} Hz component" if cam.shake_hz else ""
    if cam.jitter_px > cfg.max_jitter_px:
        return Recapture(f"camera moved {cam.jitter_px:.2f} px RMS{shake}; above {cfg.max_jitter_px} px it cannot be "
                         "subtracted reliably", "Rest the phone on a support (books or a tripod) and film again.",
                         tripod=True)
    if cam.source != "reference marker" and cam.jitter_px > cfg.max_jitter_unreferenced_px:
        return Recapture(f"camera moved {cam.jitter_px:.2f} px RMS{shake} and no static reference marker is visible "
                         "to subtract it", "Rest the phone on a support and tape marker id 1 on a still surface "
                         "behind the machine, then film again.", tripod=True, add_markers=True)
    return None


def rule_scale(c: Context) -> Action | None:
    s, req = c.ev.scale, c.ev.request
    if s.source == "none" and not req.markers:
        return Recapture("no ArUco marker visible, so pixels cannot be converted to millimetres",
                         "Tape marker id 0 flat on the machine and marker id 1 on a still surface in the same plane, "
                         "then film again.", add_markers=True)
    if s.anisotropy and s.anisotropy > c.cfg.max_anisotropy and not req.square_on:
        return Recapture(f"oblique view: the scale differs {s.anisotropy:.2f}x between directions",
                         "Face the machine square-on and film again.", square_on=True)
    return None


def rule_quality(c: Context) -> Action | None:
    m = c.ev.measurement
    if m is None or m.response >= c.cfg.min_response:
        return None
    if any(h.measurement and h.measurement.response < c.cfg.min_response for h in c.history):
        return None
    return Recapture(f"tracking quality {m.response:.2f} is below {c.cfg.min_response} (blur, darkness or no texture)",
                     "Add light, check focus, and keep a marker on the machine for texture, then film again.")


def rule_snr(c: Context) -> Action | None:
    m, req, cfg = c.ev.measurement, c.ev.request, c.cfg
    if m is not None and m.peaks_px:
        return None
    noise = f"{m.noise_px:.3f} px" if m else "unknown"
    if req.distance > cfg.min_distance + 1e-9:
        factor = max(0.5, cfg.min_distance / req.distance)
        return Recapture(f"no vibration peak above {MIN_SNR:g}x the noise floor ({noise}); motion in pixels grows as "
                         "the camera gets closer", f"Move the phone to about {factor:.0%} of its current distance, "
                         "keep the same region in frame, and film again.", distance_factor=factor)
    bound = c.ev.upper_bound_mm
    text = f"below {bound:.4f} mm peak displacement" if bound else "below the detection limit"
    return Report("below_detection", f"No vibration above the noise floor: {text} at the closest distance tried.",
                  upper_bound_mm=bound)


def alias_flag(c: Context) -> str | None:
    """An aliasing suspicion raised on this capture or on any earlier one."""
    return c.ev.alias_suspect or next((h.alias_suspect for h in c.history if h.alias_suspect), None)


def resolve_alias(c: Context) -> tuple[float | None, tuple[float, ...], float | None]:
    """(true frequency or None, candidates, next frame rate to try or None)."""
    if not alias_flag(c):
        return c.ev.top_hz, (), None
    observed = {e.fps: e.top_hz for e in (*c.history, c.ev) if e.top_hz is not None}
    top = c.ev.top_hz or 0.0
    tol = max(0.5, 0.015 * top)
    result = dealias(sorted(observed.items()), f_max=max(c.cfg.phone_rates), tol_hz=tol)
    if result.frequency_hz is not None and not result.ambiguous and len(observed) > 1:
        return result.frequency_hz, result.candidates, None
    candidates = result.candidates or (top,)
    untried = [r for r in c.cfg.phone_rates if r not in observed]
    return None, candidates, best_next_rate(candidates, untried, tol)


def rule_alias(c: Context) -> Action | None:
    suspicion = alias_flag(c)
    if not suspicion:
        return None
    freq, candidates, rate = resolve_alias(c)
    if freq is not None:
        return None
    listed = ", ".join(f"{f:.1f}" for f in candidates)
    if rate is not None:
        return Recapture(f"{suspicion}; the true frequency could be {listed} Hz",
                         f"Film the same view at {rate:g} fps (normal video, bright light for a short exposure).",
                         fps=rate)
    return Report("ambiguous", f"Possible aliasing: the vibration is at one of {listed} Hz and no available frame "
                  "rate separates them.", dominant_hz=c.ev.top_hz, alias_candidates=candidates)


def _caveats(c: Context) -> tuple[str, ...]:
    ev, notes = c.ev, []
    if ev.timebase.source == "human":
        notes.append("frame rate confirmed by a person, not by file metadata")
    if ev.camera.source == "reference marker" and ev.camera.jitter_px > 0.1:
        notes.append(f"camera motion of {ev.camera.jitter_px:.2f} px RMS was subtracted using the reference marker")
    if ev.scale.anisotropy and ev.scale.anisotropy > 1.1:
        notes.append(f"oblique view corrected along the vibration direction (anisotropy {ev.scale.anisotropy:.2f})")
    if ev.scale.marker_agreement and abs(ev.scale.marker_agreement - 1.0) > 0.15:
        notes.append("the two markers disagree on scale by more than 15%: they may not be in the same plane")
    if ev.roi_source == "discovered":
        notes.append("measured on an automatically found region, not on a marker")
    notes.append("camera screening estimate in the image plane, not a certified ISO 10816 measurement")
    return tuple(notes)


def rule_grade(c: Context) -> Action:
    ev, cfg = c.ev, c.cfg
    if ev.scale.source == "none":
        return Report("abstain", "Frequency measured, but there is no metric scale, so severity cannot be graded.",
                      dominant_hz=ev.top_hz, caveats=_caveats(c))
    freq, candidates, _ = resolve_alias(c)
    peaks = list(ev.peaks_mm)
    if freq is not None and peaks and abs(freq - peaks[0].freq_hz) > 1e-6:
        peaks[0] = replace(peaks[0], freq_hz=freq)
    hi = cfg.band_hz[1] if candidates else min(cfg.band_hz[1], ev.fps / 2.0)
    velocity = velocity_rms_mm_s(peaks, cfg.band_hz[0], hi)
    severity = iso_zone(velocity, cfg.machine_class)
    if severity.zone in ("C", "D") and "running_hz" not in c.answers:
        return AskHuman("running_hz", "What is the machine's running speed in rpm (nameplate or speed setting)? "
                        "It names the fault.", f"severity zone {severity.zone} at {velocity:.2f} mm/s")
    finding = diagnose(peaks, c.answers.get("running_hz"))
    report = Report("graded", f"Zone {severity.zone}: {severity.meaning}. {velocity:.2f} mm/s RMS, strongest at "
                    f"{peaks[0].freq_hz:.1f} Hz.", peaks[0].freq_hz, velocity, severity.zone, finding.signature,
                    candidates, ev.upper_bound_mm, _caveats(c), tuple((p.freq_hz, p.amplitude) for p in peaks))
    if severity.zone in ("C", "D"):
        ticket = {"title": f"Vibration zone {severity.zone} ({velocity:.2f} mm/s): probable {finding.signature}",
                  "evidence": finding.evidence, "limits_mm_s": list(severity.limits),
                  "status": "awaiting human approval; nothing is sent automatically"}
        return ProposeTicket(report, ticket)
    return report


RULES: tuple[Callable[[Context], Action | None], ...] = (
    rule_timebase, rule_shake, rule_scale, rule_quality, rule_snr, rule_alias, rule_grade)


def decide(ev: Evidence, history: tuple[Evidence, ...], answers: dict, cfg: AgentConfig) -> tuple[Action, str]:
    ctx = Context(ev, history, dict(answers), cfg)
    for rule in RULES:
        action = rule(ctx)
        if action is not None:
            return action, rule.__name__
    raise AssertionError("rule_grade always returns an action")
