"""Velocity severity against ISO 10816-1 (ISO 20816-1) zone boundaries for small to large machines."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from kampan.spectrum import Peak

# Zone boundaries A/B, B/C, C/D in mm/s RMS, broadband 10-1000 Hz, per machine class.
# Class I: small machines up to 15 kW. II: 15-75 kW. III/IV: large machines, rigid/soft supports.
ZONE_LIMITS = {
    "I": (0.71, 1.8, 4.5),
    "II": (1.12, 2.8, 7.1),
    "III": (1.8, 4.5, 11.2),
    "IV": (2.8, 7.1, 18.0),
}
ZONE_MEANING = {
    "A": "typical of newly commissioned machines",
    "B": "acceptable for unrestricted long-term operation",
    "C": "unsatisfactory for long-term operation; plan maintenance",
    "D": "severe enough to cause damage",
}


@dataclass(frozen=True)
class Severity:
    velocity_mm_s: float
    zone: str
    machine_class: str
    meaning: str
    limits: tuple[float, float, float]


def velocity_rms_mm_s(peaks_mm: Sequence[Peak], f_min: float, f_max: float) -> float:
    """Overall RMS velocity from displacement peaks (mm, peak) inside [f_min, f_max]."""
    total = 0.0
    for p in peaks_mm:
        if f_min <= p.freq_hz <= f_max:
            v_rms = 2.0 * math.pi * p.freq_hz * p.amplitude / math.sqrt(2.0)
            total += v_rms * v_rms
    return math.sqrt(total)


def exposure_attenuation(freq_hz: float, exposure_s: float) -> float:
    """Fraction of a sinusoid's amplitude that survives averaging over the exposure: |sinc(pi f t)|."""
    x = math.pi * freq_hz * exposure_s
    return 1.0 if x == 0 else abs(math.sin(x) / x)


def iso_zone(velocity_mm_s: float, machine_class: str = "I") -> Severity:
    if machine_class not in ZONE_LIMITS:
        raise ValueError(f"machine_class must be one of {sorted(ZONE_LIMITS)}")
    limits = ZONE_LIMITS[machine_class]
    zone = "D"
    for name, limit in zip("ABC", limits):
        if velocity_mm_s < limit:
            zone = name
            break
    return Severity(velocity_mm_s, zone, machine_class, ZONE_MEANING[zone], limits)
