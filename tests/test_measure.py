import numpy as np
import pytest

from kampan.measure import (Capture, camera_motion, discover_regions, find_markers, measure_roi, measure_scale,
                            probe_timebase, target_rect)
from kampan.synth import SceneSpec, Tone, render

W, H = 400, 300


def capture_of(spec):
    clip = render(spec)
    return clip, Capture(clip.frames, clip.container_fps, clip.capture_fps_tag)


def test_timebase_rules():
    assert probe_timebase(Capture(np.zeros((2, 2, 2)), 30.0, 240.0)).fps == 240.0
    assert probe_timebase(Capture(np.zeros((2, 2, 2)), 240.0, None)).trusted
    untrusted = probe_timebase(Capture(np.zeros((2, 2, 2)), 30.0, None))
    assert not untrusted.trusted
    assert probe_timebase(Capture(np.zeros((2, 2, 2)), 30.0, None), human_fps=120.0).fps == 120.0


def test_markers_and_scale_agree():
    clip, cap = capture_of(SceneSpec(width=W, height=H, fps=60.0, duration_s=0.2, mm_per_px=0.3))
    markers = find_markers(cap.frames)
    report = measure_scale(markers, 20.0)
    assert markers.ids == (0, 1)
    assert report.source == "target marker"
    assert report.mm_per_px == pytest.approx(0.3, rel=0.05)
    assert report.marker_agreement == pytest.approx(1.0, abs=0.06)


def test_no_markers_no_scale():
    _, cap = capture_of(SceneSpec(width=W, height=H, fps=60.0, duration_s=0.2, mm_per_px=0.3,
                                  target_marker=False, reference_marker=False))
    assert measure_scale(find_markers(cap.frames), 20.0).source == "none"


def test_stabilization_removes_hand_shake():
    spec = SceneSpec(width=W, height=H, fps=240.0, duration_s=2.0, mm_per_px=0.3,
                     tones=(Tone(31.0, 0.06),), shake_px=1.5, shake_hz=7.0)
    clip, cap = capture_of(spec)
    markers = find_markers(cap.frames)
    cam = camera_motion(cap.frames, markers, 240.0)
    assert cam.source == "reference marker"
    assert cam.jitter_px > 0.5
    no_ref = camera_motion(cap.frames, find_markers(cap.frames[:, :, :W // 2]), 240.0,
                           target_rect(markers, cap.frames.shape[1:]))
    assert no_ref.source == "masked frame"
    assert no_ref.jitter_px == pytest.approx(cam.jitter_px, rel=0.25)
    rect = target_rect(markers, cap.frames.shape[1:])
    raw = measure_roi(cap.frames, 240.0, rect, None)
    fixed = measure_roi(cap.frames, 240.0, rect, cam)
    assert raw.peaks_px[0].freq_hz != pytest.approx(31.0, abs=0.5)
    assert fixed.peaks_px[0].freq_hz == pytest.approx(31.0, abs=0.2)
    assert fixed.peaks_px[0].amplitude == pytest.approx(0.06 / 0.3, rel=0.12)


def test_discovery_finds_the_vibrating_plate():
    spec = SceneSpec(width=W, height=H, fps=240.0, duration_s=1.0, mm_per_px=0.3, tones=(Tone(40.0, 0.12),),
                     target_marker=False)
    clip, cap = capture_of(spec)
    regions = discover_regions(cap.frames, 240.0, None, block=32)
    assert regions, "expected at least one region"
    x, y, w, h = regions[0].rect
    tx, ty, tw, th = clip.truth.target_rect
    assert tx - 32 <= x <= tx + tw and ty - 32 <= y <= ty + th
    assert regions[0].freq_hz == pytest.approx(40.0, abs=0.5)
