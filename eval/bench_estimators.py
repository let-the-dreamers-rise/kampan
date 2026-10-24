"""Sub-pixel shift estimators on known shifts: OpenCV phase correlation (with and without window) vs ECC.

Textures are random fields blurred to a feature size of 1, 2 or 4 output pixels, rendered at 4x and area
downsampled, as a camera would. Writes docs/results/estimators.{json,md}.
Usage: python -m eval.bench_estimators
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from kampan.motion import ecc_shift

SHIFTS = (0.02, 0.05, 0.1, 0.2, 0.3, 0.5)
FEATURE_PX = (1.0, 2.0, 4.0)
S, N, BIG = 4, 96, 1600


def texture(feature_px: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = cv2.GaussianBlur(rng.random((BIG, BIG)).astype(np.float32), (0, 0), feature_px * S)
    return (img - img.min()) / (img.max() - img.min()) * 200 + 20


def view(big: np.ndarray, dx: float, dy: float, noise: float, rng: np.random.Generator) -> np.ndarray:
    m = np.float32([[1, 0, dx * S], [0, 1, dy * S]])
    w = cv2.warpAffine(big, m, (BIG, BIG), flags=cv2.INTER_CUBIC)
    small = cv2.resize(w[400:400 + N * S, 400:400 + N * S], (N, N), interpolation=cv2.INTER_AREA)
    return np.clip(small + rng.normal(0, noise, small.shape), 0, 255).astype(np.float32)


def estimate(method: str, ref: np.ndarray, cur: np.ndarray) -> tuple[float, float]:
    if method == "ecc":
        dx, dy, _ = ecc_shift(ref, cur)
        return dx, dy
    a, b = ref.astype(np.float64).copy(), cur.astype(np.float64).copy()
    if method == "phase+hann":
        (dx, dy), _ = cv2.phaseCorrelate(a, b, cv2.createHanningWindow((N, N), cv2.CV_64F))
    else:
        (dx, dy), _ = cv2.phaseCorrelate(a, b)
    return dx, dy


def main() -> None:
    rows = []
    rng = np.random.default_rng(0)
    for feature in FEATURE_PX:
        for seed in range(3):
            big = texture(feature, seed)
            ref = view(big, 0, 0, 1.0, rng)
            for shift in SHIFTS:
                for axis in ("x", "y"):
                    cur = view(big, shift if axis == "x" else 0, shift if axis == "y" else 0, 1.0, rng)
                    for method in ("phase+hann", "phase", "ecc"):
                        dx, dy = estimate(method, ref, cur)
                        got = dx if axis == "x" else dy
                        rows.append({"feature_px": feature, "seed": seed, "shift": shift, "axis": axis,
                                     "method": method, "estimate": got, "rel_err": (got - shift) / shift})
    out = Path("docs/results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "estimators.json").write_text(json.dumps(rows, indent=1))
    lines = ["| Texture feature size | Method | Median estimate / true, 0.05 px | 0.1 px | 0.3 px | Median abs error, all shifts |",
             "|---|---|---|---|---|---|"]
    for feature in FEATURE_PX:
        for method in ("phase+hann", "phase", "ecc"):
            sel = [r for r in rows if r["feature_px"] == feature and r["method"] == method]
            ratio = {s: np.median([r["estimate"] / s for r in sel if r["shift"] == s]) for s in (0.05, 0.1, 0.3)}
            err = np.median([abs(r["rel_err"]) for r in sel])
            lines.append(f"| {feature:g} px | {method} | {ratio[0.05]:.2f} | {ratio[0.1]:.2f} | {ratio[0.3]:.2f} | "
                         f"{100 * err:.0f}% |")
    (out / "estimators.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
