import numpy as np
import pytest

from kampan.scale import detect_markers, scale_from_marker
from kampan.synth import SceneSpec, render


def test_detects_target_and_reference_markers():
    clip = render(SceneSpec(width=320, height=240, fps=30.0, duration_s=0.1))
    found = detect_markers(clip.frames[0])
    assert set(found) == {0, 1}


def test_scale_matches_truth():
    spec = SceneSpec(width=320, height=240, fps=30.0, duration_s=0.1, mm_per_px=0.3)
    clip = render(spec)
    corners = detect_markers(clip.frames[0])[1]
    scale = scale_from_marker(corners, marker_mm=spec.marker_mm)
    mm = scale.to_mm(np.array([0.0, 1.0]))
    assert abs(mm[1]) == pytest.approx(0.3, rel=0.04)


def test_oblique_view_scales_directions_differently():
    spec = SceneSpec(width=320, height=240, fps=30.0, duration_s=0.1, mm_per_px=0.3, tilt_deg=40.0)
    clip = render(spec)
    scale = scale_from_marker(detect_markers(clip.frames[0])[1], marker_mm=spec.marker_mm)
    assert scale.anisotropy > 1.2
    assert abs(scale.to_mm(np.array([1.0, 0.0]))[0]) == pytest.approx(0.3 / np.cos(np.radians(40)), rel=0.06)


def test_no_markers_returns_empty():
    assert detect_markers(np.full((120, 160), 128, np.uint8)) == {}
