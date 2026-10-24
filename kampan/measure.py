"""Measurement tools the agent calls. Each takes frames plus context and returns a frozen record."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from kampan.motion import Track, block_rects, ecc_shift, track_patch
from kampan.scale import PlaneScale, detect_markers, scale_from_marker
from kampan.spectrum import Peak, find_peaks, noise_floor

TARGET_ID, REFERENCE_ID = 0, 1
TRUSTED_CONTAINER_FPS = 90.0
MIN_SNR = 6.0
STABILIZE_MIN_PX = 0.05  # subtract camera motion only above this RMS; below it subtraction only adds noise
EXCLUDE_GROW = 2.0  # the machine extends beyond its marker: mask this multiple of the marker box


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


GLOBAL_SCALE = 0.5  # camera motion is estimated at half resolution; it is large compared with vibration


def _masked_global_track(frames: np.ndarray, exclude: tuple[int, int, int, int] | None) -> Track:
    """Whole-frame ECC translation at half resolution, with the machine region masked out."""
    h, w = frames.shape[1:]
    size = (max(16, int(w * GLOBAL_SCALE)), max(16, int(h * GLOBAL_SCALE)))
    mask = np.full((size[1], size[0]), 255, np.uint8)
    if exclude is not None:
        x, y, ew, eh = (int(v * GLOBAL_SCALE) for v in exclude)
        mask[max(0, y):y + eh, max(0, x):x + ew] = 0

    def small(img: np.ndarray) -> np.ndarray:
        return cv2.resize(img, size, interpolation=cv2.INTER_AREA).astype(np.float32)

    ref = small(frames[0])
    n = frames.shape[0]
    dx, dy, resp = np.empty(n), np.empty(n), np.empty(n)
    prev = (0.0, 0.0)
    for i in range(n):
        sx, sy, cc = ecc_shift(ref, small(frames[i]), prev, mask)
        dx[i], dy[i], resp[i] = sx / GLOBAL_SCALE, sy / GLOBAL_SCALE, cc
        prev = (sx, sy)
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
    stabilized = camera is not None and camera.track is not None and camera.jitter_px > STABILIZE_MIN_PX
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


DISCOVERY_SNR = 8.0


def block_flow_series(frames: np.ndarray, block: int) -> np.ndarray:
    """(T, rows, cols, 2) mean DIS optical flow from frame 0 to every frame, per image block."""
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
    h, w = frames.shape[1:]
    gh, gw = h // block, w // block
    out = np.empty((frames.shape[0], gh, gw, 2))
    for i, frame in enumerate(frames):
        flow = dis.calc(frames[0], frame, None)[: gh * block, : gw * block]
        out[i] = flow.reshape(gh, block, gw, block, 2).mean(axis=(1, 3))
    return out


def discover_regions(frames: np.ndarray, fps: float, camera: CameraMotion | None, block: int = 32,
                     seconds: float = 2.0, top: int = 5) -> tuple[Region, ...]:
    """Rank image blocks by periodic motion in dense DIS optical flow; the best one is then measured with ECC."""
    n = min(frames.shape[0], max(64, int(seconds * fps)))
    series = block_flow_series(frames[:n], block)
    cam = None
    if camera is not None and camera.track is not None and camera.jitter_px > STABILIZE_MIN_PX:
        cam = (camera.track.dx[:n], camera.track.dy[:n])
    found = []
    for r in range(series.shape[1]):
        for c in range(series.shape[2]):
            dx, dy = series[:, r, c, 0], series[:, r, c, 1]
            if cam is not None:
                dx, dy = dx - cam[0], dy - cam[1]
            track = Track(dx, dy, np.ones(n))
            peaks = find_peaks(track.along(track.principal_angle()), fps, min_snr=DISCOVERY_SNR)
            if peaks:
                found.append(Region((c * block, r * block, block, block), peaks[0].freq_hz, peaks[0].amplitude,
                                    peaks[0].snr))
    return tuple(sorted(found, key=lambda g: g.amplitude_px * math.sqrt(g.snr), reverse=True)[:top])


def target_rect(markers: Markers, shape: tuple[int, int]) -> tuple[int, int, int, int] | None:
    return _bbox(markers.target, 1.25, shape) if markers.target is not None else None


def exclusion_rect(markers: Markers, shape: tuple[int, int]) -> tuple[int, int, int, int] | None:
    """Region masked out when estimating camera motion from the whole frame."""
    return _bbox(markers.target, EXCLUDE_GROW, shape) if markers.target is not None else None
