"""Agent thresholds. Every number here is a decision boundary that appears in the trace."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    marker_mm: float = 40.0
    machine_class: str = "I"
    phone_rates: tuple[float, ...] = (24.0, 25.0, 30.0, 60.0, 120.0, 240.0)
    max_captures: int = 5
    max_questions: int = 4
    max_jitter_px: float = 2.0  # stabilization is not trusted above this camera motion (RMS px)
    max_jitter_unreferenced_px: float = 0.3  # without a static marker, tolerate only this much
    max_anisotropy: float = 1.6  # oblique view limit before asking for a square-on view
    min_response: float = 0.12  # phase-correlation quality below which tracking is not trusted
    alias_fraction: float = 0.8  # peaks above this fraction of Nyquist may be aliased
    min_distance: float = 0.25  # closest relative distance the agent will ask for
    band_hz: tuple[float, float] = (10.0, 1000.0)  # ISO 10816 broadband velocity band
    discover_block: int = 32
