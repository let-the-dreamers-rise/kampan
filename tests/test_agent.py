import json

import pytest

from kampan.agent.actions import ProposeTicket, Recapture
from kampan.agent.config import AgentConfig
from kampan.agent.loop import run_agent
from kampan.baseline import run_baseline
from kampan.sim_world import SimWorld, scenario_library

CFG = AgentConfig(marker_mm=20.0)
SCENARIOS = {s.name: s for s in scenario_library(seed=1)}


def run(name):
    world = SimWorld(SCENARIOS[name])
    return run_agent(world, CFG), world


def decisions(result):
    return [e for e in result.events if e["kind"] == "decision"]


def test_clean_capture_is_graded_in_one_shot():
    result, world = run("clean")
    assert result.report.verdict == "graded"
    assert result.report.zone == SCENARIOS["clean"].true_zone()
    assert result.report.dominant_hz == pytest.approx(21.0, rel=0.02)
    assert result.captures == 1 and result.questions == 0


def test_untagged_slow_motion_asks_for_frame_rate():
    result, world = run("slowmo-untagged")
    assert world.questions[0] == "capture_fps"
    assert result.report.dominant_hz == pytest.approx(21.0, rel=0.02)


def test_missing_markers_trigger_a_recapture_with_markers():
    result, world = run("no-markers")
    assert decisions(result)[0]["action"] == "Recapture"
    assert world.captures[1].markers
    assert result.report.verdict == "graded"


def test_unreferenced_hand_shake_asks_for_support():
    result, world = run("handheld-unreferenced")
    assert world.captures[1].tripod
    assert result.report.dominant_hz == pytest.approx(21.0, rel=0.02)


def test_aliasing_is_resolved_with_a_separating_rate():
    result, world = run("aliased")
    assert any(c.fps not in (None, 240.0) for c in world.captures)
    assert result.report.dominant_hz == pytest.approx(140.0, rel=0.02)


def test_machine_off_reports_below_detection_with_a_bound():
    result, _ = run("machine-off")
    assert result.report.verdict == "below_detection"
    assert result.report.upper_bound_mm is not None


def test_fault_proposes_a_ticket_that_needs_approval():
    result, world = run("unbalanced")
    assert result.report.zone == "C"
    assert result.ticket is not None and result.ticket_approved is True
    assert "approve_ticket" in world.questions
    assert result.report.signature == "unbalance"


def test_trace_is_json_serializable_and_cites_measurements():
    result, _ = run("no-markers")
    text = json.dumps(result.events)
    first = decisions(result)[0]
    assert "no ArUco marker" in first["detail"]["reason"]
    assert first["because"]["rule"] == "rule_scale"
    assert len(text) > 100


def test_baseline_is_fooled_by_hand_shake():
    report = run_baseline(SimWorld(SCENARIOS["handheld-referenced"]), CFG)
    assert report.dominant_hz != pytest.approx(21.0, rel=0.02)


def test_recapture_apply_is_immutable():
    from kampan.agent.actions import CaptureRequest
    req = CaptureRequest()
    new = Recapture("r", "i", distance_factor=0.5, tripod=True).apply(req)
    assert req.distance == 1.0 and not req.tripod
    assert new.distance == 0.5 and new.tripod
