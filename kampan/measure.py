"""Measurement tools the agent calls. Each takes frames plus context and returns a frozen record."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from kampan.motion import Track, block_rects, track_patch
from kampan.scale import PlaneScale, detect_markers, scale_from_marker
from kampan.spectrum import Peak, find_peaks, noise_floor

TARGET_ID, REFERENCE_ID = 0, 1
TRUSTED_CONTAINER_FPS = 90.0
MIN_SNR = 6.0


@dataclass(frozen=True)
class Capture:
    frames: np.ndarray = field(repr=False)
    container_fps: float
    capture_fps_tag: float | None
    label: str = ""


@dataclass(frozen=True)
class TimeBase:
    fps: float
    source: str  # human | capture-fps tag | container
    trusted: bool
    note: str


def probe_timebase(capture: Capture, human_fps: float | None = None, requested_fps: float | None = None) -> TimeBase:
    if human_fps:
        return TimeBase(float(human_fps), "human", True, "frame rate confirmed by the person who filmed")
    if capture.capture_fps_tag:
        return TimeBase(capture.capture_fps_tag, "capture-fps tag", True, "slow-motion capture rate from file metadata")
    if capture.container_fps >= TRUSTED_CONTAINER_FPS:
        return TimeBase(capture.container_fps, "container", True, "high-frame-rate stream")
    if requested_fps and abs(capture.container_fps - requested_fps) < 0.5:
        return TimeBase(capture.container_fps, "container", True, "file rate matches the rate the agent asked for")
    return TimeBase(capture.container_fps, "container", False,
                    f"file says {capture.container_fps:g} fps with no slow-motion tag; a slow-motion file would be faster")


@dataclass(frozen=True)
class Markers:
    target: np.ndarray | None = field(repr=False)
    reference: np.ndarray | None = field(repr=False)
    ids: tuple[int, ...] = ()


def find_markers(frames: np.ndarray) -> Markers:
    found = detect_markers(frames[0])
    if not found and frames.shape[0] > 8:
        found = detect_markers(np.median(frames[:8], axis=0).astype(np.uint8))
    return Markers(found.get(TARGET_ID), found.get(REFERENCE_ID), tuple(sorted(found)))


@dataclass(frozen=True)
class ScaleReport:
    scale: PlaneScale | None = field(repr=False)
    source: str  # target marker | reference marker | human length | none
    mm_per_px: float | None
    anisotropy: float | None
    marker_agreement: float | None  # target / reference mm-per-px ratio when both exist


def measure_scale(markers: Markers, marker_mm: float) -> ScaleReport:
    scales = {}
    if markers.target is not None:
        scales["target marker"] = scale_from_marker(markers.target, marker_mm)
    if markers.reference is not None:
        scales["reference marker"] = scale_from_marker(markers.reference, marker_mm)
    if not scales:
        return ScaleReport(None, "none", None, None, None)
    source = "target marker" if "target marker" in scales else "reference marker"
    chosen = scales[source]
    agreement = None
    if len(scales) == 2:
        t, r = scales["target marker"], scales["reference marker"]
        agreement = float(np.sqrt(abs(np.linalg.det(t.jacobian)) / abs(np.linalg.det(r.jacobian))))
    mm_per_px = float(np.sqrt(abs(np.linalg.det(chosen.jacobian))))
    return ScaleReport(chosen, source, mm_per_px, chosen.anisotropy, agreement)


def _bbox(corners: np.ndarray, grow: float, shape: tuple[int, int]) -> tuple[int, int, int, int]:
    (x0, y0), (x1, y1) = corners.min(axis=0), corners.max(axis=0)
    cx, cy, half = (x0 + x1) / 2, (y0 + y1) / 2, grow * max(x1 - x0, y1 - y0) / 2
    h, w = shape
    left, top = int(max(0, cx - half)), int(max(0, cy - half))
    right, bottom = int(min(w, cx + half)), int(min(h, cy + half))
    return left, top, right - left, bottom - top


@dataclass(frozen=True)
class CameraMotion:
    track: Track | None = field(repr=False)
    source: str  # reference marker | frame median | none
    jitter_px: float  # std of camera displacement magnitude
    shake_hz: float | None


def _masked_global_track(frames: np.ndarray, exclude: tuple[int, int, int, int] | None) -> Track:
    """Whole-frame phase correlation with the machine region replaced by the frame mean."""
    h, w = frames.shape[1:]
    window = cv2.createHanningWindow((w, h), cv2.CV_64F)

    def prep(img: np.ndarray) -> np.ndarray:
        out = img.astype(np.float64)
        if exclude is not None:
            x, y, ew, eh = exclude
            out[max(0, y):y + eh, max(0, x):x + ew] = out.mean()
        return out

    ref = prep(frames[0])
    n = frames.shape[0]
    dx, dy, resp = np.empty(n), np.empty(n), np.empty(n)
    for i in range(n):
        (sx, sy), r = cv2.phaseCorrelate(ref.copy(), prep(frames[i]), window)
        dx[i], dy[i], resp[i] = sx, sy, r
    return Track(dx, dy, resp)


def camera_motion(frames: np.ndarray, markers: Markers, fps: float,
                  exclude: tuple[int, int, int, int] | None = None) -> CameraMotion:
    """Camera shake from a static reference marker, else from the whole frame minus the machine region."""
    if markers.reference is not None:
        track = track_patch(frames, _bbox(markers.reference, 1.3, frames.shape[1:]))
        source = "reference marker"
    else:
        track = _masked_global_track(frames, exclude)
        source = "masked frame"
    mag = np.hypot(track.dx - track.dx.mean(), track.dy - track.dy.mean())
    peaks = find_peaks(track.along(track.principal_angle()), fps, min_snr=MIN_SNR)
    return CameraMotion(track, source, float(np.sqrt(np.mean(mag ** 2))), peaks[0].freq_hz if peaks else None)


@dataclass(frozen=True)
class Measurement:
    rect: tuple[int, int, int, int]
    angle_rad: float
    peaks_px: tuple[Peak, ...]
    noise_px: float
    response: float  # mean phase-correlation response: texture and sharpness quality
    stabilized: bool


def measure_roi(frames: np.ndarray, fps: float, rect: tuple[int, int, int, int],
                camera: CameraMotion | None) -> Measurement:
    track = track_patch(frames, rect)
    stabilized = camera is not None and camera.track is not None
    if stabilized:
        track = Track(track.dx - camera.track.dx, track.dy - camera.track.dy, track.response)
    angle = track.principal_angle()
    signal = track.along(angle)
    peaks = find_peaks(signal, fps, min_snr=MIN_SNR)
    return Measurement(tuple(int(v) for v in rect), angle, peaks, noise_floor(signal, fps),
                       float(np.mean(track.response)), stabilized)


@dataclass(frozen=True)
class Region:
    rect: tuple[int, int, int, int]
    freq_hz: float
    amplitude_px: float
    snr: float


def discover_regions(frames: np.ndarray, fps: float, camera: CameraMotion | None, block: int = 32,
                     seconds: float = 2.0, top: int = 5) -> tuple[Region, ...]:
    """Rank image blocks by vibration strength; skip blocks whose content changes (rotating parts)."""
    n = min(frames.shape[0], max(64, int(seconds * fps)))
    clip = frames[:n]
    cam = None
    if camera is not None and camera.track is not None:
        cam = Track(camera.track.dx[:n], camera.track.dy[:n], camera.track.response[:n])
    found = []
    for rect in block_rects(clip.shape[1:], block):
        track = track_patch(clip, rect)
        if np.mean(track.response) < 0.15:
            continue
        if cam is not None:
            track = Track(track.dx - cam.dx, track.dy - cam.dy, track.response)
        peaks = find_peaks(track.along(track.principal_angle()), fps, min_snr=MIN_SNR)
        if peaks:
            found.append(Region(rect, peaks[0].freq_hz, peaks[0].amplitude, peaks[0].snr))
    return tuple(sorted(found, key=lambda r: r.amplitude_px * math.sqrt(r.snr), reverse=True)[:top])


def target_rect(markers: Markers, shape: tuple[int, int]) -> tuple[int, int, int, int] | None:
    return _bbox(markers.target, 1.25, shape) if markers.target is not None else None
