"""Render the simulated sample sessions by letting the agent drive the simulator, saving every clip it asks for.

Replaying the saved clips in order reproduces the same recapture path in the web app.
Usage: python -m tools.make_samples --out out/storage   (then upload out/storage/samples/* to S3)
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from kampan.agent.config import AgentConfig
from kampan.agent.loop import run_agent
from kampan.measure import Capture
from kampan.sim_world import SimWorld, scenario_library

INDEX = Path(__file__).resolve().parents[1] / "app" / "samples.json"
CFG = AgentConfig(marker_mm=20.0)
CHOSEN = {
    "clean": ("Healthy fan (simulated)", "A good capture of a healthy machine. One clip, graded directly."),
    "unbalanced": ("Unbalanced fan (simulated)", "Strong 1x vibration. The agent asks the running speed, names the "
                   "fault and holds a maintenance ticket for your approval."),
    "far": ("Camera too far (simulated)", "The first clip is below the noise floor. The agent asks for closer clips."),
    "slowmo-untagged": ("Slow-motion file without metadata (simulated)", "The file says 30 fps. The agent asks what "
                        "rate it was really filmed at."),
    "handheld-unreferenced": ("Handheld, no reference (simulated)", "Hand shake with nothing still to subtract. The "
                              "agent asks for a support and a reference marker."),
    "aliased": ("Faster than the frame rate (simulated)", "A 140 Hz vibration filmed at 240 fps shows up at 100 Hz. "
                "The agent picks a frame rate that tells the candidates apart."),
}


class RecordingWorld(SimWorld):
    """A simulator that keeps every clip it renders."""

    def __init__(self, scenario):
        super().__init__(scenario)
        self.clips: list[Capture] = []

    def capture(self, request):
        cap = super().capture(request)
        self.clips.append(cap)
        return cap


def write_avi(path: Path, cap: Capture) -> None:
    h, w = cap.frames.shape[1:]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), cap.container_fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"cannot write {path}")
    writer.set(cv2.VIDEOWRITER_PROP_QUALITY, 97)
    pad = np.repeat(cap.frames[:1], int(0.5 * cap.container_fps) + 1, axis=0)  # the loader skips 0.5 s
    for frame in np.concatenate([pad, cap.frames]):
        writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
    writer.release()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/storage")
    args = parser.parse_args()
    root = Path(args.out)
    entries = []
    for scenario in scenario_library(seed=0):
        if scenario.name not in CHOSEN:
            continue
        world = RecordingWorld(replace(scenario, duration_s=2.0))
        result = run_agent(world, CFG)
        keys = []
        for i, cap in enumerate(world.clips):
            key = f"samples/{scenario.name}-{i}.avi"
            dst = root / key
            dst.parent.mkdir(parents=True, exist_ok=True)
            write_avi(dst, cap)
            keys.append(key)
        title, text = CHOSEN[scenario.name]
        entries.append({"id": scenario.name, "title": title, "description": text, "label": "simulated",
                        "clips": keys, "config": {"marker_mm": 20.0, "machine_class": "I"},
                        "answers": {"running_hz": scenario.running_hz} if scenario.running_hz else {},
                        "expected_verdict": result.report.verdict})
        print(scenario.name, len(keys), result.report.verdict, result.report.zone, flush=True)
    INDEX.write_text(json.dumps(entries, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
