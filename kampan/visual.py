"""Pictures for people: annotated frame, spectrum series, and a motion-magnified filmstrip."""
from __future__ import annotations

import base64
import math

import cv2
import numpy as np

from kampan.measure import CameraMotion, find_markers
from kampan.motion import Track, track_patch
from kampan.spectrum import amplitude_spectrum

JPEG_QUALITY = 82


def to_jpeg_b64(img: np.ndarray, quality: int = JPEG_QUALITY) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def annotated_frame(frames: np.ndarray, rect: tuple[int, int, int, int] | None, angle_rad: float | None) -> np.ndarray:
    """First frame with markers, the measured region and the vibration direction drawn on it."""
    img = cv2.cvtColor(frames[0], cv2.COLOR_GRAY2BGR)
    for marker_id, corners in _markers(frames).items():
        pts = corners.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [pts], True, (0, 200, 255) if marker_id == 0 else (255, 160, 0), 2, cv2.LINE_AA)
        cv2.putText(img, f"id {marker_id}", tuple(int(v) for v in corners[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)
    if rect is not None:
        x, y, w, h = rect
        cv2.rectangle(img, (x, y), (x + w, y + h), (80, 220, 80), 2, cv2.LINE_AA)
        if angle_rad is not None:
            cx, cy, r = x + w // 2, y + h // 2, max(12, min(w, h) // 2)
            tip = (int(cx + r * math.cos(angle_rad)), int(cy + r * math.sin(angle_rad)))
            tail = (int(cx - r * math.cos(angle_rad)), int(cy - r * math.sin(angle_rad)))
            cv2.arrowedLine(img, tail, tip, (80, 220, 80), 2, cv2.LINE_AA, tipLength=0.2)
            cv2.arrowedLine(img, tip, tail, (80, 220, 80), 2, cv2.LINE_AA, tipLength=0.2)
    return img


def _markers(frames: np.ndarray) -> dict[int, np.ndarray]:
    m = find_markers(frames)
    return {k: v for k, v in ((0, m.target), (1, m.reference)) if v is not None}


def spectrum_series(frames: np.ndarray, fps: float, rect: tuple[int, int, int, int], angle_rad: float,
                    camera: CameraMotion | None, mm_per_px: float | None, points: int = 400) -> dict:
    track = track_patch(frames, rect)
    if camera is not None and camera.track is not None:
        track = Track(track.dx - camera.track.dx, track.dy - camera.track.dy, track.response)
    signal = track.along(angle_rad) * (mm_per_px or 1.0)
    freqs, amp = amplitude_spectrum(signal, fps)
    step = max(1, freqs.size // points)
    n = min(signal.size, int(0.5 * fps))
    return {"unit": "mm" if mm_per_px else "px",
            "freqs": np.round(freqs[::step], 3).tolist(), "amp": np.round(amp[::step], 6).tolist(),
            "t": np.round(np.arange(n) / fps, 5).tolist(), "disp": np.round(signal[:n] - signal[:n].mean(), 6).tolist()}


def _pyramid(img: np.ndarray, levels: int) -> list[np.ndarray]:
    pyr, cur = [], img
    for _ in range(levels):
        down = cv2.pyrDown(cur)
        pyr.append(cur - cv2.pyrUp(down, dstsize=(cur.shape[1], cur.shape[0])))
        cur = down
    pyr.append(cur)
    return pyr


def _collapse(pyr: list[np.ndarray]) -> np.ndarray:
    cur = pyr[-1]
    for lap in reversed(pyr[:-1]):
        cur = cv2.pyrUp(cur, dstsize=(lap.shape[1], lap.shape[0])) + lap
    return cur


def magnify(frames: np.ndarray, fps: float, freq_hz: float, alpha: float = 40.0, levels: int = 4,
            rel_band: float = 0.25) -> np.ndarray:
    """Linear Eulerian motion magnification (Laplacian pyramid, IIR temporal band-pass around freq_hz)."""
    lo, hi = freq_hz * (1 - rel_band), min(freq_hz * (1 + rel_band), 0.45 * fps)
    r_hi, r_lo = 1 - math.exp(-2 * math.pi * hi / fps), 1 - math.exp(-2 * math.pi * lo / fps)
    lp_hi = lp_lo = None
    out = np.empty_like(frames)
    for i, frame in enumerate(frames):
        pyr = _pyramid(frame.astype(np.float32), levels)
        if lp_hi is None:
            lp_hi, lp_lo = [p.copy() for p in pyr], [p.copy() for p in pyr]
        boosted = []
        for k, p in enumerate(pyr):
            lp_hi[k] = lp_hi[k] + r_hi * (p - lp_hi[k])
            lp_lo[k] = lp_lo[k] + r_lo * (p - lp_lo[k])
            gain = 0.0 if k == 0 or k == len(pyr) - 1 else alpha
            boosted.append(p + gain * (lp_hi[k] - lp_lo[k]))
        out[i] = np.clip(_collapse(boosted), 0, 255).astype(np.uint8)
    return out


def filmstrip(frames: np.ndarray, fps: float, freq_hz: float, rect: tuple[int, int, int, int],
              cycles: float = 3.0, width: int = 240, alpha: float = 40.0) -> dict:
    """Original and magnified crops side by side, a few vibration cycles long, as one tall JPEG."""
    x, y, w, h = rect
    pad = int(0.3 * max(w, h))
    hh, ww = frames.shape[1:]
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(ww, x + w + pad), min(hh, y + h + pad)
    warm = min(frames.shape[0] - 2, int(1.5 * fps / max(freq_hz, 1.0)) + int(0.15 * fps))
    n = max(8, min(96, int(cycles * fps / max(freq_hz, 1.0))))
    crop = frames[:, y0:y1, x0:x1]
    mag = magnify(crop[: warm + n], fps, freq_hz, alpha=alpha)[warm: warm + n]
    orig = crop[warm: warm + n]
    scale = width / float(orig.shape[2])
    size = (width, max(8, int(orig.shape[1] * scale)))
    tiles = [np.hstack([cv2.resize(o, size), cv2.resize(m, size)]) for o, m in zip(orig, mag)]
    strip = np.vstack(tiles)
    return {"jpeg": to_jpeg_b64(strip, 75), "frames": len(tiles), "tile_w": size[0] * 2, "tile_h": size[1],
            "alpha": alpha, "capture_fps": fps, "freq_hz": freq_hz}
