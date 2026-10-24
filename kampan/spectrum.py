"""Spectral analysis of displacement time series: amplitude spectrum, peaks, noise floor."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_SAMPLES = 32
PAD_FACTOR = 4


@dataclass(frozen=True)
class Peak:
    freq_hz: float
    amplitude: float  # peak (not RMS) amplitude, same unit as the input signal
    snr: float  # amplitude over the spectrum's median amplitude


def _prepare(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or x.size < MIN_SAMPLES:
        raise ValueError(f"need a 1-D signal with at least {MIN_SAMPLES} samples, got shape {x.shape}")
    t = np.arange(x.size, dtype=np.float64)
    slope, intercept = np.polyfit(t, x, 1)
    return x - (slope * t + intercept)


def amplitude_spectrum(x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Single-sided peak-amplitude spectrum with a Hann window and 4x zero padding."""
    y = _prepare(x)
    window = np.hanning(y.size)
    n_fft = 1 << int(np.ceil(np.log2(y.size * PAD_FACTOR)))
    spectrum = np.fft.rfft(y * window, n_fft)
    amp = 2.0 * np.abs(spectrum) / window.sum()
    freqs = np.fft.rfftfreq(n_fft, 1.0 / fs)
    return freqs, amp


def _floor(freqs: np.ndarray, amp: np.ndarray, fmin: float) -> float:
    band = amp[(freqs >= fmin) & (freqs < freqs[-1])]
    return float(np.median(band)) if band.size else float(np.median(amp))


def noise_floor(x: np.ndarray, fs: float, fmin: float = 1.0) -> float:
    """Median spectral amplitude: a robust estimate of the measurement noise level."""
    freqs, amp = amplitude_spectrum(x, fs)
    return _floor(freqs, amp, fmin)


def _refine(freqs: np.ndarray, amp: np.ndarray, i: int) -> tuple[float, float]:
    if 0 < i < amp.size - 1:
        a, b, c = amp[i - 1], amp[i], amp[i + 1]
        denom = a - 2 * b + c
        offset = 0.5 * (a - c) / denom if denom != 0 else 0.0
        step = freqs[1] - freqs[0]
        peak = b - 0.25 * (a - c) * offset
        return float(freqs[i] + offset * step), float(peak)
    return float(freqs[i]), float(amp[i])


def find_peaks(x: np.ndarray, fs: float, min_snr: float = 6.0, max_peaks: int = 8,
               fmin: float = 1.0) -> tuple[Peak, ...]:
    """Spectral peaks above min_snr times the median amplitude, strongest first."""
    freqs, amp = amplitude_spectrum(x, fs)
    floor = max(_floor(freqs, amp, fmin), 1e-12)
    n = np.asarray(x).size
    min_sep = 2.5 * fs / n
    is_max = np.zeros(amp.size, bool)
    is_max[1:-1] = (amp[1:-1] > amp[:-2]) & (amp[1:-1] >= amp[2:])
    candidates = np.flatnonzero(is_max & (freqs >= fmin) & (amp > min_snr * floor))
    kept: list[Peak] = []
    for i in candidates[np.argsort(amp[candidates])[::-1]]:
        f, a = _refine(freqs, amp, int(i))
        if all(abs(f - p.freq_hz) > min_sep for p in kept):
            kept.append(Peak(f, a, a / floor))
        if len(kept) >= max_peaks:
            break
    return tuple(kept)
