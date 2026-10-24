"""Synthetic slow-motion clips with known vibration, for tests, benchmarks and the agent simulator.

A textured plate carrying ArUco id 0 vibrates in front of a static textured background that carries
ArUco id 1. Rendering is done at `supersample` times the output size and area-downsampled, so
sub-pixel motion is represented faithfully. Optional: camera shake, oblique view, sensor noise,
and a container frame rate that differs from the capture rate (as in phone slow-motion files).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

ARUCO_DICT = cv2.aruco.DICT_4X4_50
TARGET_ID, REFERENCE_ID = 0, 1


@dataclass(frozen=True)
class Tone:
    freq_hz: float
    amp_mm: float  # peak displacement in the plate's plane
    angle_deg: float = 90.0  # image direction: 0 = right, 90 = down
    phase: float = 0.0


@dataclass(frozen=True)
class SceneSpec:
    width: int = 320
    height: int = 240
    fps: float = 240.0
    duration_s: float = 2.0
    mm_per_px: float = 0.25
    tones: tuple[Tone, ...] = ()
    noise_sigma: float = 1.5
    shake_px: float = 0.0
    shake_hz: float = 7.0
    drift_px_per_s: tuple[float, float] = (0.0, 0.0)
    marker_mm: float = 20.0
    target_marker: bool = True
    reference_marker: bool = True
    tilt_deg: float = 0.0
    container_fps: float | None = None
    capture_tag: bool = True
    seed: int = 0
    supersample: int = 4


@dataclass(frozen=True)
class Truth:
    mm_per_px: float
    mm_per_px_x: float
    target_rect: tuple[int, int, int, int]
    reference_rect: tuple[int, int, int, int]
    tones: tuple[Tone, ...]
    camera_shift_px: np.ndarray = field(repr=False)


@dataclass(frozen=True)
class Clip:
    frames: np.ndarray  # (T, H, W) uint8 grayscale
    capture_fps: float
    container_fps: float
    capture_fps_tag: float | None
    truth: Truth


def _texture(rng: np.random.Generator, h: int, w: int, cell: int, lo: float, hi: float) -> np.ndarray:
    coarse = rng.random((max(2, h // cell), max(2, w // cell))).astype(np.float32)
    tex = cv2.resize(coarse, (w, h), interpolation=cv2.INTER_CUBIC)
    tex = cv2.GaussianBlur(tex, (0, 0), cell / 3.0)
    tex = (tex - tex.min()) / max(float(np.ptp(tex)), 1e-6)
    return lo + (hi - lo) * tex


def _marker(marker_id: int, side: int) -> np.ndarray:
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    img = cv2.aruco.generateImageMarker(dictionary, marker_id, side, borderBits=1).astype(np.float32)
    quiet = max(2, side // 5)
    return cv2.copyMakeBorder(img, quiet, quiet, quiet, quiet, cv2.BORDER_CONSTANT, value=255.0)


def _paste(canvas: np.ndarray, patch: np.ndarray, cx: int, cy: int) -> tuple[int, int, int, int]:
    h, w = patch.shape
    x0, y0 = cx - w // 2, cy - h // 2
    if x0 < 0 or y0 < 0 or x0 + w > canvas.shape[1] or y0 + h > canvas.shape[0]:
        raise ValueError("scene does not fit: lower marker_mm or raise mm_per_px")
    canvas[y0:y0 + h, x0:x0 + w] = patch
    return x0, y0, w, h


def _layout(spec: SceneSpec, rng: np.random.Generator):
    s = spec.supersample
    big_h, big_w = spec.height * s, spec.width * s
    background = _texture(rng, big_h, big_w, cell=24 * s, lo=60.0, hi=190.0)
    background = 0.6 * background + 0.4 * _texture(rng, big_h, big_w, cell=6 * s, lo=60.0, hi=190.0)
    side = int(round(spec.marker_mm / spec.mm_per_px * s))
    ref_rect = (0, 0, 0, 0)
    if spec.reference_marker:
        ref_rect = _paste(background, _marker(REFERENCE_ID, side), int(0.78 * big_w), big_h // 2)
    plate_side = int(side * 1.7)
    plate = _texture(rng, plate_side, plate_side, cell=3 * s, lo=30.0, hi=225.0)
    if spec.target_marker:
        _paste(plate, _marker(TARGET_ID, side), plate_side // 2, plate_side // 2)
    plate_center = (int(0.33 * big_w), big_h // 2)
    return background, plate, plate_center, ref_rect


def _displacement_px(spec: SceneSpec, t: np.ndarray) -> np.ndarray:
    d = np.zeros((t.size, 2))
    for tone in spec.tones:
        a = math.radians(tone.angle_deg)
        wave = (tone.amp_mm / spec.mm_per_px) * np.sin(2 * math.pi * tone.freq_hz * t + tone.phase)
        d[:, 0] += wave * math.cos(a)
        d[:, 1] += wave * math.sin(a)
    d[:, 0] += spec.drift_px_per_s[0] * t
    d[:, 1] += spec.drift_px_per_s[1] * t
    return d


def _shake_px(spec: SceneSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if spec.shake_px <= 0:
        return np.zeros((t.size, 2))
    walk = np.cumsum(rng.normal(0, spec.shake_px * 0.05, (t.size, 2)), axis=0)
    ph = rng.uniform(0, 2 * math.pi, 2)
    tremor = np.stack([np.sin(2 * math.pi * spec.shake_hz * t + ph[0]),
                       np.sin(2 * math.pi * spec.shake_hz * 1.13 * t + ph[1])], axis=1)
    return spec.shake_px * tremor + walk


def _out_rect(rect, s: int, sx: float, width: int, inset: int = 4) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    cx = width * s / 2.0
    x_out = (cx + (x - cx) * sx) / s
    return (int(math.ceil(x_out)) + inset, int(math.ceil(y / s)) + inset,
            int(w * sx / s) - 2 * inset, int(h / s) - 2 * inset)


def render(spec: SceneSpec) -> Clip:
    rng = np.random.default_rng(spec.seed)
    s = spec.supersample
    background, plate, (pcx, pcy), ref_rect = _layout(spec, rng)
    n = int(round(spec.duration_s * spec.fps))
    t = np.arange(n) / spec.fps
    disp = _displacement_px(spec, t) * s
    shake = _shake_px(spec, t, rng)
    sx = math.cos(math.radians(spec.tilt_deg))
    big_h, big_w = background.shape
    ph, pw = plate.shape
    frames = np.empty((n, spec.height, spec.width), np.uint8)
    for i in range(n):
        canvas = background.copy()
        move = np.float32([[1, 0, pcx - pw / 2 + disp[i, 0]], [0, 1, pcy - ph / 2 + disp[i, 1]]])
        cv2.warpAffine(plate, move, (big_w, big_h), dst=canvas, flags=cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_TRANSPARENT)
        if sx != 1.0 or spec.shake_px > 0:
            cx = big_w / 2.0
            glob = np.float32([[sx, 0, cx - sx * cx + shake[i, 0] * s], [0, 1, shake[i, 1] * s]])
            canvas = cv2.warpAffine(canvas, glob, (big_w, big_h), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_REFLECT)
        small = cv2.resize(canvas, (spec.width, spec.height), interpolation=cv2.INTER_AREA)
        if spec.noise_sigma > 0:
            small = small + rng.normal(0, spec.noise_sigma, small.shape)
        frames[i] = np.clip(np.rint(small), 0, 255).astype(np.uint8)
    plate_rect = (pcx - pw // 2, pcy - ph // 2, pw, ph)
    truth = Truth(
        mm_per_px=spec.mm_per_px,
        mm_per_px_x=spec.mm_per_px / sx,
        target_rect=_out_rect(plate_rect, s, sx, spec.width),
        reference_rect=_out_rect(ref_rect, s, sx, spec.width) if spec.reference_marker else (0, 0, 0, 0),
        tones=spec.tones,
        camera_shift_px=shake,
    )
    container = spec.container_fps if spec.container_fps is not None else spec.fps
    tag = spec.fps if spec.capture_tag else None
    return Clip(frames, spec.fps, container, tag, truth)
