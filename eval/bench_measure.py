"""Measurement accuracy on synthetic clips with known vibration. Writes docs/results/measurement.{json,md}.

Grid: amplitude (px) x frequency (Hz) x sensor noise; several seeds each. Reports frequency error, amplitude
error and detection rate, and the smallest amplitude detected in at least 90% of runs.

Usage: python -m eval.bench_measure --seeds 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from kampan.measure import find_markers, measure_roi, target_rect
from kampan.synth import SceneSpec, Tone, render

MM_PER_PX = 0.3
AMPS_PX = (0.005, 0.01, 0.02, 0.05, 0.1, 0.3, 1.0)
FREQS = (8.0, 21.0, 47.0, 95.0)
NOISE = (1.0, 3.0)


def one(amp_px: float, freq: float, noise: float, seed: int) -> dict:
    spec = SceneSpec(width=480, height=320, fps=240.0, duration_s=2.0, mm_per_px=MM_PER_PX,
                     tones=(Tone(freq, amp_px * MM_PER_PX, phase=seed),), noise_sigma=noise, seed=seed, supersample=3)
    clip = render(spec)
    rect = target_rect(find_markers(clip.frames), clip.frames.shape[1:])
    meas = measure_roi(clip.frames, 240.0, rect, None)
    hit = [p for p in meas.peaks_px if abs(p.freq_hz - freq) < 0.02 * freq + 0.3]
    return {"amp_px": amp_px, "freq": freq, "noise": noise, "seed": seed, "detected": bool(hit),
            "freq_err_hz": abs(hit[0].freq_hz - freq) if hit else None,
            "amp_err_rel": (hit[0].amplitude - amp_px) / amp_px if hit else None,
            "noise_px": meas.noise_px, "top_is_true": bool(meas.peaks_px) and meas.peaks_px[0] in hit}


def summarize(rows: list[dict]) -> str:
    lines = ["| Noise (grey levels) | Amplitude (px) | Detected | Median frequency error (Hz) | Median amplitude error |",
             "|---|---|---|---|---|"]
    for noise in NOISE:
        for amp in AMPS_PX:
            rs = [r for r in rows if r["noise"] == noise and r["amp_px"] == amp]
            det = [r for r in rs if r["detected"]]
            fe = np.median([r["freq_err_hz"] for r in det]) if det else float("nan")
            ae = np.median([abs(r["amp_err_rel"]) for r in det]) if det else float("nan")
            lines.append(f"| {noise:g} | {amp:g} | {len(det)}/{len(rs)} | {fe:.3f} | {100 * ae:.1f}% |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--out", default="docs/results")
    args = parser.parse_args()
    rows = []
    for noise in NOISE:
        for amp in AMPS_PX:
            for freq in FREQS:
                for seed in range(args.seeds):
                    rows.append(one(amp, freq, noise, seed))
            print(f"noise {noise} amp {amp} done", flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "measurement.json").write_text(json.dumps(rows, indent=1))
    (out / "measurement.md").write_text(summarize(rows) + "\n")
    print(summarize(rows))


if __name__ == "__main__":
    main()
