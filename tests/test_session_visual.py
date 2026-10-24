import numpy as np
import pytest

from kampan.agent.config import AgentConfig
from kampan.measure import Capture
from kampan.session import answer_key, run_session
from kampan.synth import SceneSpec, Tone, render
from kampan.visual import annotated_frame, filmstrip, magnify, spectrum_series

CFG = AgentConfig(marker_mm=20.0)


def clip(**kw):
    spec = SceneSpec(width=480, height=320, fps=240.0, duration_s=1.0, mm_per_px=0.3, supersample=3,
                     tones=(Tone(21.0, 0.03),), **kw)
    c = render(spec)
    return Capture(c.frames, c.container_fps, c.capture_fps_tag)


def test_session_asks_for_a_new_clip_then_finishes():
    first = clip(target_marker=False, reference_marker=False)
    step1 = run_session([first], {}, CFG)
    assert step1.status == "need_capture"
    assert "marker" in step1.instruction
    step2 = run_session([first, clip()], {}, CFG)
    assert step2.status == "need_answer" and step2.answer_key == "running_hz"
    step3 = run_session([first, clip()], {"running_hz": 21.0, "approve_ticket": False}, CFG)
    assert step3.status == "done"
    assert step3.result.report.verdict == "graded"
    assert step3.result.ticket_approved is False


def test_session_asks_for_frame_rate_of_untagged_slow_motion():
    slow = clip(container_fps=30.0, capture_tag=False)
    step = run_session([slow], {}, CFG)
    assert step.status == "need_answer"
    assert step.answer_key == answer_key("capture_fps", 0) == "capture_fps:0"
    done = run_session([slow], {"capture_fps:0": 240.0}, CFG)
    assert done.status in ("done", "need_answer")


def test_visuals_render():
    c = clip()
    img = annotated_frame(c.frames, (100, 100, 60, 60), 1.57)
    assert img.shape == (320, 480, 3)
    series = spectrum_series(c.frames, 240.0, (60, 90, 140, 140), 1.57, None, 0.3)
    assert len(series["freqs"]) == len(series["amp"]) and series["unit"] == "mm"
    strip = filmstrip(c.frames, 240.0, 21.0, (60, 90, 140, 140))
    assert strip["frames"] >= 8 and len(strip["jpeg"]) > 1000


def test_magnify_amplifies_band_motion():
    c = clip()
    out = magnify(c.frames[:120], 240.0, 21.0, alpha=30.0)
    assert out.shape == c.frames[:120].shape
    diff_in = np.abs(np.diff(c.frames[60:120].astype(float), axis=0)).mean()
    diff_out = np.abs(np.diff(out[60:120].astype(float), axis=0)).mean()
    assert diff_out > 1.5 * diff_in
