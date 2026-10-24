"""The same OpenCV measurement without the agent: one capture, file frame rate, no checks, no stabilization."""
from __future__ import annotations

from kampan.agent.actions import CaptureRequest, Report
from kampan.agent.config import AgentConfig
from kampan.measure import discover_regions, find_markers, measure_roi, measure_scale, target_rect
from kampan.severity import iso_zone, velocity_rms_mm_s
from kampan.spectrum import Peak


def run_baseline(world, cfg: AgentConfig = AgentConfig()) -> Report:
    cap = world.capture(CaptureRequest())
    fps = cap.capture_fps_tag or cap.container_fps
    frames = cap.frames
    markers = find_markers(frames)
    scale = measure_scale(markers, cfg.marker_mm)
    rect = target_rect(markers, frames.shape[1:])
    if rect is None:
        regions = discover_regions(frames, fps, None, cfg.discover_block)
        rect = regions[0].rect if regions else None
    if rect is None:
        return Report("below_detection", "no moving region found")
    meas = measure_roi(frames, fps, rect, None)
    if not meas.peaks_px:
        return Report("below_detection", "no peak")
    if scale.mm_per_px is None:
        return Report("abstain", "no scale", dominant_hz=meas.peaks_px[0].freq_hz)
    peaks = tuple(Peak(p.freq_hz, p.amplitude * scale.mm_per_px, p.snr) for p in meas.peaks_px)
    velocity = velocity_rms_mm_s(peaks, cfg.band_hz[0], min(cfg.band_hz[1], fps / 2))
    sev = iso_zone(velocity, cfg.machine_class)
    return Report("graded", f"zone {sev.zone}", peaks[0].freq_hz, velocity, sev.zone,
                  peaks_mm=tuple((p.freq_hz, p.amplitude) for p in peaks))
