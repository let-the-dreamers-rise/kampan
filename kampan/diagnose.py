"""Rotating-machinery fault signatures from spectral peaks expressed as orders of running speed.

Rules follow standard vibration-analysis practice (dominant 1x radial: unbalance; strong 2x: misalignment
or looseness; many harmonics or half orders: looseness or rub). They screen; they do not certify.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from kampan.spectrum import Peak

ORDER_TOL = 0.04  # relative tolerance when matching a peak to an order


@dataclass(frozen=True)
class Finding:
    signature: str  # unbalance | misalignment | looseness | none | unknown
    confidence: str  # low | medium
    evidence: str


def order_of(freq_hz: float, running_hz: float) -> float | None:
    """The (half-)order a frequency matches, or None."""
    ratio = freq_hz / running_hz
    nearest = round(ratio * 2) / 2
    if nearest > 0 and abs(ratio - nearest) <= ORDER_TOL * max(1.0, nearest):
        return nearest
    return None


def diagnose(peaks: Sequence[Peak], running_hz: float | None) -> Finding:
    if not peaks:
        return Finding("none", "medium", "no peak above the noise floor")
    if running_hz is None or running_hz <= 0:
        return Finding("unknown", "low", "running speed unknown; orders cannot be assigned")
    by_order: dict[float, float] = {}
    for p in peaks:
        o = order_of(p.freq_hz, running_hz)
        if o is not None:
            by_order[o] = max(by_order.get(o, 0.0), p.amplitude)
    one = by_order.get(1.0, 0.0)
    two = by_order.get(2.0, 0.0)
    halves = [o for o in by_order if o % 1 == 0.5]
    harmonics = [o for o in by_order if o >= 3.0]
    if one == 0.0:
        return Finding("unknown", "low", f"no peak at 1x ({running_hz:.1f} Hz); check the running speed")
    if halves or len(harmonics) >= 2:
        return Finding("looseness", "low", f"orders present: {sorted(by_order)}")
    if two >= 0.5 * one:
        return Finding("misalignment", "low", f"2x is {two / one:.2f} of 1x")
    return Finding("unbalance", "medium", f"1x dominant; 2x is {two / one:.2f} of 1x")
