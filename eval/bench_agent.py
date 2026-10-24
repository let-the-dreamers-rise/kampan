"""Agent vs baseline on the simulated scenario suite. Writes docs/results/agent_vs_baseline.{json,md}.

Usage: python -m eval.bench_agent --seeds 3
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from kampan.agent.config import AgentConfig
from kampan.agent.loop import run_agent
from kampan.baseline import run_baseline
from kampan.sim_world import SimWorld, describe, scenario_library

CFG = AgentConfig(marker_mm=20.0)
FREQ_TOL = 0.03


def outcome(report, scenario) -> str:
    """correct | wrong | abstained | missed."""
    if not scenario.tones:
        ok = report.verdict == "below_detection" or (report.verdict == "graded" and report.zone == "A")
        return "correct" if ok else "wrong"
    if report.verdict == "graded":
        freq_ok = report.dominant_hz is not None and \
            abs(report.dominant_hz - scenario.dominant_hz()) <= FREQ_TOL * scenario.dominant_hz()
        return "correct" if freq_ok and report.zone == scenario.true_zone() else "wrong"
    if report.verdict == "below_detection":
        return "missed"
    return "abstained"


def run(seeds: int) -> list[dict]:
    rows = []
    for seed in range(seeds):
        for scenario in scenario_library(seed=seed):
            t0 = time.perf_counter()
            world = SimWorld(scenario)
            agent = run_agent(world, CFG)
            t_agent = time.perf_counter() - t0
            base = run_baseline(SimWorld(scenario), CFG)
            actions = [e["action"] for e in agent.events if e["kind"] == "decision"]
            rows.append({
                **describe(scenario),
                "agent": {"outcome": outcome(agent.report, scenario), "verdict": agent.report.verdict,
                          "zone": agent.report.zone, "hz": agent.report.dominant_hz,
                          "velocity": agent.report.velocity_mm_s, "captures": agent.captures,
                          "questions": agent.questions, "actions": actions,
                          "ticket": agent.ticket is not None, "seconds": round(t_agent, 1),
                          "summary": agent.report.summary},
                "baseline": {"outcome": outcome(base, scenario), "verdict": base.verdict, "zone": base.zone,
                             "hz": base.dominant_hz, "velocity": base.velocity_mm_s},
            })
            print(f"seed {seed} {scenario.name:22s} agent={rows[-1]['agent']['outcome']:9s} "
                  f"baseline={rows[-1]['baseline']['outcome']:9s} {t_agent:5.1f}s", flush=True)
    return rows


def table(rows: list[dict]) -> str:
    names = list(dict.fromkeys(r["name"] for r in rows))
    lines = ["| Scenario | What is wrong with the capture | Agent correct | Baseline correct | Agent captures (mean) |"
             " Agent questions (mean) | Agent actions (seed 0) |", "|---|---|---|---|---|---|---|"]
    for name in names:
        rs = [r for r in rows if r["name"] == name]
        a = sum(r["agent"]["outcome"] == "correct" for r in rs)
        b = sum(r["baseline"]["outcome"] == "correct" for r in rs)
        caps = sum(r["agent"]["captures"] for r in rs) / len(rs)
        qs = sum(r["agent"]["questions"] for r in rs) / len(rs)
        acts = " > ".join(rs[0]["agent"]["actions"])
        lines.append(f"| {name} | {rs[0]['note']} | {a}/{len(rs)} | {b}/{len(rs)} | {caps:.1f} | {qs:.1f} | {acts} |")
    totals = {k: {o: sum(r[k]["outcome"] == o for r in rows) for o in ("correct", "wrong", "abstained", "missed")}
              for k in ("agent", "baseline")}
    lines += ["", "| | Correct | Confidently wrong | Abstained | Missed |", "|---|---|---|---|---|"]
    for k in ("agent", "baseline"):
        t = totals[k]
        lines.append(f"| {k} | {t['correct']}/{len(rows)} | {t['wrong']} | {t['abstained']} | {t['missed']} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--out", default="docs/results")
    args = parser.parse_args()
    rows = run(args.seeds)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "agent_vs_baseline.json").write_text(json.dumps(rows, indent=1))
    (out / "agent_vs_baseline.md").write_text(table(rows) + "\n")
    print(table(rows))


if __name__ == "__main__":
    main()
