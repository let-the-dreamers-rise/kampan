import struct

import cv2
import numpy as np
import pytest

from kampan.video_io import _tag_after_key, load_video, read_capture_tag


def test_tag_parsed_from_keys_ilst_float():
    blob = b"xxxxmdta" + b"com.android.capture.fps" + b"\x00\x00\x00\x10" + b"data" + b"\x00\x00\x00\x17" + \
        b"\x00\x00\x00\x00" + struct.pack(">f", 240.0)
    assert _tag_after_key(blob) == pytest.approx(240.0)


def test_no_tag_returns_none():
    assert _tag_after_key(b"no metadata here") is None


def test_load_video_roundtrip(tmp_path):
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 120.0, (160, 120))
    assert writer.isOpened()
    for i in range(100):
        frame = np.full((120, 160, 3), 40 + i, np.uint8)
        writer.write(frame)
    writer.release()
    video = load_video(path, max_seconds=0.5, max_width=80, start_seconds=0.1)
    assert video.container_fps == pytest.approx(120.0)
    assert video.frames.shape[1:] == (60, 80)
    assert video.frames.shape[0] == 60
    assert read_capture_tag(path) is None


def test_missing_file_raises(tmp_path):
    with pytest.raises(ValueError):
        load_video(tmp_path / "nope.mp4")
