import numpy as np
import pytest

from kampan.spectrum import amplitude_spectrum, find_peaks, noise_floor

FS = 240.0


def sine(freq, amp, seconds=4.0, fs=FS, phase=0.3):
    t = np.arange(int(seconds * fs)) / fs
    return amp * np.sin(2 * np.pi * freq * t + phase)


def test_single_tone_frequency_and_amplitude():
    peaks = find_peaks(sine(21.7, 0.4), FS)
    assert peaks, "expected one peak"
    top = peaks[0]
    assert top.freq_hz == pytest.approx(21.7, abs=0.05)
    assert top.amplitude == pytest.approx(0.4, rel=0.03)


def test_two_tones_sorted_by_amplitude():
    x = sine(20.0, 0.3) + sine(40.0, 0.1, phase=1.0)
    peaks = find_peaks(x, FS)
    freqs = [round(p.freq_hz) for p in peaks[:2]]
    assert freqs == [20, 40]
    assert peaks[1].amplitude == pytest.approx(0.1, rel=0.05)


def test_noise_only_has_no_confident_peak():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.05, int(4 * FS))
    assert find_peaks(x, FS, min_snr=8.0) == ()


def test_noise_floor_scales_with_noise():
    rng = np.random.default_rng(2)
    low = noise_floor(rng.normal(0, 0.01, 960), FS)
    high = noise_floor(rng.normal(0, 0.1, 960), FS)
    assert high > 5 * low


def test_dc_offset_and_drift_ignored():
    t = np.arange(960) / FS
    x = sine(30.0, 0.2) + 5.0 + 0.5 * t
    top = find_peaks(x, FS)[0]
    assert top.freq_hz == pytest.approx(30.0, abs=0.05)


def test_amplitude_spectrum_shapes():
    freqs, amp = amplitude_spectrum(sine(10.0, 1.0), FS)
    assert freqs.shape == amp.shape
    assert freqs[0] == 0.0 and freqs[-1] == pytest.approx(FS / 2)


def test_too_short_signal_raises():
    with pytest.raises(ValueError):
        find_peaks(np.zeros(8), FS)
