"""Perception: run the OpenCV tools on one capture and summarize what they show."""
from __future__ import annotations

from dataclasses import dataclass, field

from kampan.agent.actions import CaptureRequest
from kampan.agent.config import AgentConfig
from kampan.agent.trace import Trace
from kampan.diagnose import order_of
from kampan.measure import (MIN_SNR, CameraMotion, Capture, Measurement, ScaleReport, TimeBase, camera_motion,
                            discover_regions, find_markers, measure_roi, measure_scale, probe_timebase, target_rect)
from kampan.severity import velocity_rms_mm_s
from kampan.spectrum import Peak


@dataclass(frozen=True)
class Evidence:
    index: int
    request: CaptureRequest
    timebase: TimeBase
    marker_ids: tuple[int, ...]
    scale: ScaleReport
    camera: CameraMotion
    roi_source: str  # target marker | discovered | none
    measurement: Measurement | None
    peaks_mm: tuple[Peak, ...]
    velocity_mm_s: float | None
    upper_bound_mm: float | None = None
    alias_suspect: str | None = None
    frames_shape: tuple[int, ...] = field(default=(), repr=False)

    @property
    def fps(self) -> float:
        return self.timebase.fps

    @property
    def top_hz(self) -> float | None:
        m = self.measurement
        return m.peaks_px[0].freq_hz if m and m.peaks_px else None


def _alias_reason(meas: Measurement | None, fps: float, running_hz: float | None, cfg: AgentConfig) -> str | None:
    if meas is None or not meas.peaks_px:
        return None
    top = meas.peaks_px[0].freq_hz
    nyquist = fps / 2.0
    if top > cfg.alias_fraction * nyquist:
        return f"strongest peak {top:.1f} Hz is within {100 * (1 - cfg.alias_fraction):.0f}% of the Nyquist limit {nyquist:.0f} Hz"
    if running_hz and order_of(top, running_hz) is None:
        return f"strongest peak {top:.1f} Hz is not a multiple of the running speed {running_hz:.1f} Hz"
    return None


def assess(capture: Capture, request: CaptureRequest, answers: dict, cfg: AgentConfig, trace: Trace,
           index: int) -> Evidence:
    frames = capture.frames
    tb = trace.tool("probe_timebase", probe_timebase, capture, answers.get("capture_fps"), request.fps,
                    inputs={"container_fps": capture.container_fps, "tag": capture.capture_fps_tag,
                            "requested_fps": request.fps})
    markers = trace.tool("find_markers", find_markers, frames, inputs={"frames": list(frames.shape)})
    scale = trace.tool("measure_scale", measure_scale, markers, cfg.marker_mm, inputs={"marker_mm": cfg.marker_mm})
    rect, source = target_rect(markers, frames.shape[1:]), "target marker"
    camera = trace.tool("camera_motion", camera_motion, frames, markers, tb.fps, rect,
                        inputs={"fps": tb.fps, "exclude": rect})
    if rect is None:
        regions = trace.tool("discover_regions", discover_regions, frames, tb.fps, camera, cfg.discover_block,
                             inputs={"block": cfg.discover_block})
        rect, source = (regions[0].rect, "discovered") if regions else (None, "none")
    meas = None
    if rect is not None:
        meas = trace.tool("measure_roi", measure_roi, frames, tb.fps, rect, camera,
                          inputs={"rect": rect, "fps": tb.fps, "stabilize": camera.source})
    peaks_mm: tuple[Peak, ...] = ()
    velocity = upper = None
    if meas is not None and scale.scale is not None:
        k = scale.scale.mm_per_px_along(meas.angle_rad)
        peaks_mm = tuple(Peak(p.freq_hz, p.amplitude * k, p.snr) for p in meas.peaks_px)
        hi = min(cfg.band_hz[1], tb.fps / 2.0)
        velocity = velocity_rms_mm_s(peaks_mm, cfg.band_hz[0], hi) if peaks_mm else None
        upper = MIN_SNR * meas.noise_px * k
    alias = _alias_reason(meas, tb.fps, answers.get("running_hz"), cfg)
    return Evidence(index, request, tb, markers.ids, scale, camera, source, meas, peaks_mm, velocity, upper, alias,
                    tuple(frames.shape))
