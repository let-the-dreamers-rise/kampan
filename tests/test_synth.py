import numpy as np
import pytest

from kampan.synth import SceneSpec, Tone, render


def test_render_shapes_and_metadata():
    spec = SceneSpec(width=160, height=120, fps=120.0, duration_s=0.5, mm_per_px=0.6, tones=(Tone(10.0, 0.05),))
    clip = render(spec)
    assert clip.frames.shape == (60, 120, 160)
    assert clip.frames.dtype == np.uint8
    assert clip.capture_fps == 120.0
    assert clip.truth.mm_per_px == pytest.approx(spec.mm_per_px)


def test_render_is_deterministic_for_a_seed():
    spec = SceneSpec(width=96, height=72, fps=60.0, duration_s=0.2, mm_per_px=1.0, tones=(Tone(5.0, 0.1),), seed=7)
    assert np.array_equal(render(spec).frames, render(spec).frames)


def test_container_fps_can_lie_like_slow_motion_files():
    spec = SceneSpec(width=96, height=72, fps=240.0, duration_s=0.2, mm_per_px=1.0, container_fps=30.0,
                     capture_tag=False)
    clip = render(spec)
    assert clip.container_fps == 30.0
    assert clip.capture_fps_tag is None


def test_scene_that_does_not_fit_is_rejected():
    with pytest.raises(ValueError):
        render(SceneSpec(width=96, height=72, mm_per_px=0.1, duration_s=0.1))

