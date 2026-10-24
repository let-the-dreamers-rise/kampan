"""Load phone video with OpenCV and recover the true capture rate of slow-motion files.

Android slow-motion MP4s often play back at 30 fps while the sensor captured 120 or 240 fps; the
capture rate is stored as the metadata key `com.android.capture.fps`. iPhone slow-motion files carry
the capture rate as the stream frame rate. When neither is available the agent asks the human.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

CAPTURE_KEY = b"com.android.capture.fps"
MAX_BYTES_SCANNED = 64 * 1024 * 1024


@dataclass(frozen=True)
class Video:
    frames: np.ndarray  # (T, H, W) uint8 grayscale, possibly downscaled
    container_fps: float
    capture_fps_tag: float | None
    source_size: tuple[int, int]  # (width, height) before downscaling
    scale_factor: float  # output pixels per source pixel


def _tag_after_key(blob: bytes) -> float | None:
    """Find the capture-fps value stored in the MP4 'keys'/'ilst' metadata or as text."""
    idx = blob.find(CAPTURE_KEY)
    if idx < 0:
        return None
    tail = blob[idx + len(CAPTURE_KEY): idx + len(CAPTURE_KEY) + 4096]
    data = tail.find(b"data")
    while data >= 0:
        payload = tail[data + 12: data + 16]
        type_code = tail[data + 5: data + 8]
        if len(payload) == 4 and type_code == b"\x00\x00\x17":  # big-endian float32
            value = struct.unpack(">f", payload)[0]
            if 1.0 < value < 10000.0:
                return float(value)
        data = tail.find(b"data", data + 4)
    text = re.search(rb"(\d{2,4}(?:\.\d+)?)", tail[:64])
    return float(text.group(1)) if text else None


def read_capture_tag(path: str | Path) -> float | None:
    with open(path, "rb") as fh:
        head = fh.read(MAX_BYTES_SCANNED)
        tag = _tag_after_key(head)
        if tag is None and fh.tell() >= MAX_BYTES_SCANNED:
            fh.seek(-min(MAX_BYTES_SCANNED, Path(path).stat().st_size), 2)
            tag = _tag_after_key(fh.read())
    return tag


def load_video(path: str | Path, max_seconds: float = 6.0, max_width: int = 640,
               start_seconds: float = 0.5) -> Video:
    """Decode up to max_seconds of grayscale frames, skipping the first start_seconds (shutter tap)."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"cannot open video: {path}")
    try:
        container_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if container_fps <= 0:
            raise ValueError("video reports no frame rate")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        tag = read_capture_tag(path)
        rate = tag or container_fps
        skip = int(start_seconds * rate)
        limit = int(max_seconds * rate)
        frames: list[np.ndarray] = []
        factor = 1.0
        index = 0
        while len(frames) < limit:
            ok, frame = cap.read()
            if not ok:
                break
            index += 1
            if index <= skip:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            factor = min(1.0, max_width / float(max(w, h)))
            if factor < 1.0:
                gray = cv2.resize(gray, (round(w * factor), round(h * factor)), interpolation=cv2.INTER_AREA)
            frames.append(gray)
    finally:
        cap.release()
    if len(frames) < 32:
        raise ValueError("video too short: need at least 32 frames after the first half second")
    return Video(np.stack(frames), container_fps, tag, (width, height), factor)
