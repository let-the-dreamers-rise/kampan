"""Aliasing: fold a true frequency into a frame rate, and recover it from several rates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class DealiasResult:
    frequency_hz: float | None  # lowest consistent frequency, None if nothing fits
    ambiguous: bool
    candidates: tuple[float, ...]


def alias_of(freq_hz: float, fs: float) -> float:
    """Frequency at which a sinusoid of freq_hz appears when sampled at fs."""
    r = freq_hz % fs
    return min(r, fs - r)


def _candidates(fs: float, observed: float, f_max: float) -> list[float]:
    out, k = [], 0
    while k * fs - observed <= f_max:
        for c in (k * fs - observed, k * fs + observed):
            if 0.0 <= c <= f_max:
                out.append(c)
        k += 1
    return sorted(set(round(c, 9) for c in out))


def _merge(values: Iterable[float], tol: float) -> tuple[float, ...]:
    merged: list[float] = []
    for v in sorted(values):
        if not merged or v - merged[-1] > tol:
            merged.append(v)
    return tuple(merged)


def dealias(observations: Sequence[tuple[float, float]], f_max: float, tol_hz: float) -> DealiasResult:
    """Frequencies up to f_max consistent with every (frame rate, observed frequency) pair."""
    if not observations:
        raise ValueError("need at least one observation")
    fs0, f0 = observations[0]
    consistent = [c for c in _candidates(fs0, f0, f_max)
                  if all(abs(alias_of(c, fs) - fo) <= tol_hz for fs, fo in observations)]
    merged = _merge(consistent, tol_hz)
    if not merged:
        return DealiasResult(None, False, ())
    return DealiasResult(merged[0], len(merged) > 1, merged)


def best_next_rate(candidates: Sequence[float], available_rates: Sequence[float], tol_hz: float) -> float | None:
    """The available frame rate whose aliases separate the candidates best, or None if none does."""
    best_rate, best_gap = None, 2.0 * tol_hz
    for rate in available_rates:
        folded = sorted(alias_of(c, rate) for c in candidates)
        gap = min((b - a for a, b in zip(folded, folded[1:])), default=0.0)
        if gap > best_gap:
            best_rate, best_gap = rate, gap
    return best_rate
