import numpy as np
import pytest

from kampan.motion import track_patch
from kampan.spectrum import find_peaks
from kampan.synth import SceneSpec, Tone, render


def test_static_patch_has_near_zero_motion():
    spec = SceneSpec(width=320, height=240, fps=120.0, duration_s=1.0, tones=(), noise_sigma=1.0)
    clip = render(spec)
    track = track_patch(clip.frames, clip.truth.target_rect)
    assert np.std(track.dy) < 0.02
    assert np.std(track.dx) < 0.02


def test_subpixel_vertical_vibration_recovered():
    amp_mm, mm_per_px = 0.05, 0.25  # 0.2 px peak
    spec = SceneSpec(width=320, height=240, fps=240.0, duration_s=2.0, mm_per_px=mm_per_px,
                     tones=(Tone(23.0, amp_mm),), noise_sigma=1.5)
    clip = render(spec)
    track = track_patch(clip.frames, clip.truth.target_rect)
    top = find_peaks(track.dy, 240.0)[0]
    assert top.freq_hz == pytest.approx(23.0, abs=0.1)
    assert top.amplitude == pytest.approx(amp_mm / mm_per_px, rel=0.1)


def test_sign_convention_positive_down():
    spec = SceneSpec(width=320, height=240, fps=60.0, duration_s=0.5, tones=(), drift_px_per_s=(0.0, 4.0))
    clip = render(spec)
    track = track_patch(clip.frames, clip.truth.target_rect)
    assert track.dy[-1] > 1.5


def test_rejects_empty_rect():
    frames = np.zeros((4, 32, 32), np.uint8)
    with pytest.raises(ValueError):
        track_patch(frames, (0, 0, 0, 0))
