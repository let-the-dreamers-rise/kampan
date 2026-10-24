"""Sub-pixel motion of image patches over time, by windowed phase correlation (cv2.phaseCorrelate)."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

MIN_PATCH = 8


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


def track_patch(frames: np.ndarray, rect: tuple[int, int, int, int], ref_index: int = 0) -> Track:
    """Displacement of the patch in every frame relative to frame `ref_index`."""
    if frames.ndim != 3 or frames.shape[0] < 2:
        raise ValueError("frames must be (T, H, W) with T >= 2")
    x, y, w, h = _check_rect(frames, rect)
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


def block_rects(shape: tuple[int, int], block: int) -> list[tuple[int, int, int, int]]:
    h, w = shape
    return [(x, y, block, block) for y in range(0, h - block + 1, block) for x in range(0, w - block + 1, block)]
