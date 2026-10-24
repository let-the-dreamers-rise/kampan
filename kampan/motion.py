"""Sub-pixel motion of image patches over time.

Default estimator: enhanced correlation coefficient alignment (cv2.findTransformECC, translation model),
warm-started from the previous frame. Phase correlation (cv2.phaseCorrelate) is kept for comparison only:
in OpenCV 5.0.0 its sub-pixel estimate depends on image texture (see eval/bench_estimators.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

MIN_PATCH = 8
ECC_CRITERIA = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5)
ECC_BLUR = 3


@dataclass(frozen=True)
class Track:
    dx: np.ndarray  # pixels, positive right
    dy: np.ndarray  # pixels, positive down
    response: np.ndarray  # phase-correlation peak response per frame, 0..1

    def along(self, angle_rad: float) -> np.ndarray:
        return self.dx * np.cos(angle_rad) + self.dy * np.sin(angle_rad)

    def principal_angle(self) -> float:
        """Direction of largest displacement variance (radians, image coordinates)."""
        x = self.dx - self.dx.mean()
        y = self.dy - self.dy.mean()
        cov = np.cov(np.stack([x, y]))
        values, vectors = np.linalg.eigh(cov)
        v = vectors[:, int(np.argmax(values))]
        return float(np.arctan2(v[1], v[0]))


def _check_rect(frames: np.ndarray, rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = (int(v) for v in rect)
    if w < MIN_PATCH or h < MIN_PATCH:
        raise ValueError(f"patch must be at least {MIN_PATCH}x{MIN_PATCH}, got {w}x{h}")
    _, fh, fw = frames.shape
    x, y = max(0, x), max(0, y)
    w, h = min(w, fw - x), min(h, fh - y)
    if w < MIN_PATCH or h < MIN_PATCH:
        raise ValueError("patch lies outside the frame")
    return x, y, w, h


def ecc_shift(ref: np.ndarray, cur: np.ndarray, init: tuple[float, float] = (0.0, 0.0),
              mask: np.ndarray | None = None) -> tuple[float, float, float]:
    """(dx, dy, correlation) of `cur` relative to `ref`; correlation 0.0 when ECC does not converge."""
    warp = np.float32([[1, 0, init[0]], [0, 1, init[1]]])
    try:
        cc, warp = cv2.findTransformECC(ref, cur, warp, cv2.MOTION_TRANSLATION, ECC_CRITERIA, mask, ECC_BLUR)
    except cv2.error:
        return init[0], init[1], 0.0
    return float(warp[0, 2]), float(warp[1, 2]), float(cc)


def track_patch(frames: np.ndarray, rect: tuple[int, int, int, int], ref_index: int = 0,
                method: str = "ecc") -> Track:
    """Displacement of the patch in every frame relative to frame `ref_index`."""
    if frames.ndim != 3 or frames.shape[0] < 2:
        raise ValueError("frames must be (T, H, W) with T >= 2")
    x, y, w, h = _check_rect(frames, rect)
    if method == "ecc":
        return _track_ecc(frames, (x, y, w, h), ref_index)
    if method != "phase":
        raise ValueError("method must be 'ecc' or 'phase'")
    window = cv2.createHanningWindow((w, h), cv2.CV_64F)
    ref = frames[ref_index, y:y + h, x:x + w].astype(np.float64)
    n = frames.shape[0]
    dx, dy, resp = np.empty(n), np.empty(n), np.empty(n)
    for i in range(n):
        cur = frames[i, y:y + h, x:x + w].astype(np.float64)
        # OpenCV 5.0.0 multiplies both inputs by the window in place, so the reference must be copied.
        (sx, sy), r = cv2.phaseCorrelate(ref.copy(), cur, window)
        dx[i], dy[i], resp[i] = sx, sy, r
    return Track(dx, dy, resp)


def _track_ecc(frames: np.ndarray, rect: tuple[int, int, int, int], ref_index: int) -> Track:
    x, y, w, h = rect
    ref = frames[ref_index, y:y + h, x:x + w].astype(np.float32)
    n = frames.shape[0]
    dx, dy, resp = np.empty(n), np.empty(n), np.empty(n)
    prev = (0.0, 0.0)
    for i in range(n):
        sx, sy, cc = ecc_shift(ref, frames[i, y:y + h, x:x + w].astype(np.float32), prev)
        dx[i], dy[i], resp[i] = sx, sy, cc
        prev = (sx, sy)
    return Track(dx, dy, resp)


def block_rects(shape: tuple[int, int], block: int) -> list[tuple[int, int, int, int]]:
    h, w = shape
    return [(x, y, block, block) for y in range(0, h - block + 1, block) for x in range(0, w - block + 1, block)]
