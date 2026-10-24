"""Generate the capture kit: a printable ArUco sheet (A4, 300 DPI) and test-tone WAV files.

Usage: python -m tools.make_capture_kit --out capture_kit
"""
from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path

import cv2
import numpy as np

DPI = 300
A4_MM = (210.0, 297.0)
MARKER_MM = 40.0
DICT_ID = cv2.aruco.DICT_4X4_50
TONES_HZ = (31.0, 47.0, 73.0)
TONE_SECONDS = 30
SAMPLE_RATE = 44100


def mm_to_px(mm: float) -> int:
    return int(round(mm / 25.4 * DPI))


def marker_sheet() -> np.ndarray:
    """White A4 page with six 40 mm markers (ids 0-5) and a 100 mm scale bar."""
    width, height = mm_to_px(A4_MM[0]), mm_to_px(A4_MM[1])
    page = np.full((height, width), 255, np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(DICT_ID)
    side = mm_to_px(MARKER_MM)
    for idx in range(6):
        col, row = idx % 2, idx // 2
        x0 = mm_to_px(30 + col * 90)
        y0 = mm_to_px(25 + row * 75)
        marker = cv2.aruco.generateImageMarker(dictionary, idx, side, borderBits=1)
        page[y0:y0 + side, x0:x0 + side] = marker
        cv2.putText(page, f"id {idx}  {MARKER_MM:.0f} mm", (x0, y0 + side + mm_to_px(7)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 3, cv2.LINE_AA)
    bar_y = mm_to_px(262)
    x0, x1 = mm_to_px(55), mm_to_px(155)
    cv2.rectangle(page, (x0, bar_y), (x1, bar_y + mm_to_px(3)), 0, -1)
    cv2.putText(page, "100 mm: print at 100% (no fit to page), check with a ruler", (mm_to_px(20), bar_y + mm_to_px(12)),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, 0, 3, cv2.LINE_AA)
    return page


def write_pdf(path: Path, page: np.ndarray) -> None:
    """Single A4 page PDF embedding the sheet as JPEG at exact physical size."""
    ok, jpg = cv2.imencode(".jpg", page, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    data = jpg.tobytes()
    h, w = page.shape[:2]
    pw, ph = A4_MM[0] / 25.4 * 72, A4_MM[1] / 25.4 * 72
    content = f"q {pw:.2f} 0 0 {ph:.2f} 0 0 cm /Im0 Do Q".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw:.2f} {ph:.2f}] "
        f"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>".encode(),
        f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray "
        f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def write_tone(path: Path, freq_hz: float) -> None:
    """Pure sine at -3 dBFS with 0.5 s fades, 16-bit mono."""
    n = TONE_SECONDS * SAMPLE_RATE
    t = np.arange(n) / SAMPLE_RATE
    fade = np.clip(np.minimum(t, TONE_SECONDS - t) / 0.5, 0.0, 1.0)
    samples = (0.707 * fade * np.sin(2 * math.pi * freq_hz * t) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(struct.pack(f"<{n}h", *samples))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="capture_kit")
    out = Path(parser.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    sheet = marker_sheet()
    cv2.imwrite(str(out / "kampan-markers-A4-300dpi.png"), sheet)
    write_pdf(out / "kampan-markers-A4.pdf", sheet)
    for freq in TONES_HZ:
        write_tone(out / f"tone-{freq:.0f}hz.wav", freq)
    print(f"wrote kit to {out.resolve()}")


if __name__ == "__main__":
    main()
