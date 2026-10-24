"""Metric scale from ArUco markers: a local image-to-plane Jacobian (mm per pixel) via a homography."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

ARUCO_DICT = cv2.aruco.DICT_4X4_50


def _detector() -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(ARUCO_DICT), params)


def detect_markers(gray: np.ndarray) -> dict[int, np.ndarray]:
    """Marker id -> (4, 2) float corners in ArUco order (top-left, top-right, bottom-right, bottom-left)."""
    corners, ids, _ = _detector().detectMarkers(gray)
    if ids is None:
        return {}
    return {int(i): c.reshape(4, 2).astype(np.float64) for i, c in zip(ids.ravel(), corners)}


@dataclass(frozen=True)
class PlaneScale:
    jacobian: np.ndarray  # 2x2, plane mm per image px at the marker centre
    anisotropy: float  # ratio of the Jacobian's singular values; 1.0 for a frontal view
    marker_px: float  # mean marker side length in pixels

    def to_mm(self, d_px: np.ndarray) -> np.ndarray:
        return self.jacobian @ np.asarray(d_px, dtype=np.float64)

    def mm_per_px_along(self, angle_rad: float) -> float:
        return float(np.linalg.norm(self.to_mm(np.array([np.cos(angle_rad), np.sin(angle_rad)]))))


def scale_from_marker(corners: np.ndarray, marker_mm: float) -> PlaneScale:
    if marker_mm <= 0:
        raise ValueError("marker_mm must be positive")
    src = np.asarray(corners, np.float32).reshape(4, 2)
    dst = np.float32([[0, 0], [marker_mm, 0], [marker_mm, marker_mm], [0, marker_mm]])
    hom = cv2.getPerspectiveTransform(src, dst)
    center = src.mean(axis=0).astype(np.float64)
    probe = np.float32([center, center + (1, 0), center + (0, 1)]).reshape(-1, 1, 2)
    mapped = cv2.perspectiveTransform(probe, hom).reshape(3, 2).astype(np.float64)
    jac = np.stack([mapped[1] - mapped[0], mapped[2] - mapped[0]], axis=1)
    sv = np.linalg.svd(jac, compute_uv=False)
    sides = np.linalg.norm(src - np.roll(src, -1, axis=0), axis=1)
    return PlaneScale(jac, float(sv[0] / max(sv[1], 1e-12)), float(sides.mean()))
