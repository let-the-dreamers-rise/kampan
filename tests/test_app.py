import json

import pytest

from app import service
from app.storage import check_clip_key, check_key
from tests.api_client import Client


def test_health_and_index(api):
    c = Client()
    status, body = c.get("/api/health")
    assert status == 200 and body["ok"] is True
    from app import handler as h
    page = h.handler({"rawPath": "/", "requestContext": {"http": {"method": "GET"}}})
    assert page["statusCode"] == 200 and "Kampan" in page["body"]
    assert "Content-Security-Policy" in page["headers"]


def test_static_path_traversal_blocked(api):
    assert Client().get("/static/../handler.py")[0] == 404


def test_unknown_route_and_bad_json(api):
    c = Client()
    assert c.get("/nope") == (404, {"ok": False, "error": "not found"})
    from app import handler as h
    res = h.handler({"rawPath": "/api/demo/analyze", "body": "{not json", "headers": {"host": "localhost"},
                     "requestContext": {"http": {"method": "POST", "sourceIp": "1.1.1.1"}}})
    assert res["statusCode"] == 400 and json.loads(res["body"])["ok"] is False


@pytest.mark.parametrize("body", [
    {"clips": []},
    {"clips": ["../etc/passwd"]},
    {"clips": ["uploads/x.mp4"]},
    {"clips": ["traces/s/x.json"]},
])
def test_demo_runs_on_samples_only(api, body):
    assert Client().post("/api/demo/analyze", body)[0] == 400


def test_key_patterns():
    assert check_key("samples/clean-0.avi") == "samples/clean-0.avi"
    with pytest.raises(ValueError):
        check_key("uploads/../x")
    with pytest.raises(ValueError):
        check_clip_key("traces/site/run.json")


def test_answers_and_config_parsing():
    parsed = service.parse_answers({"capture_fps:0": 240, "running_hz": "unknown", "approve_ticket": True})
    assert parsed == {"capture_fps:0": 240.0, "running_hz": None, "approve_ticket": True}
    with pytest.raises(service.BadRequest):
        service.parse_answers({"evil": 1})
    with pytest.raises(service.BadRequest):
        service.parse_config({"machine_class": "V"})
    cfg = service.parse_config({"marker_mm": 30, "machine_class": "II", "phone_rates": [240, 30, 25]})
    assert cfg.phone_rates == (25.0, 30.0, 240.0) and cfg.machine_class == "II"
