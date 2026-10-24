import json

import pytest

from app import handler as h
from app import service
from app.storage import LocalStorage, check_key


def event(method, path, body=None):
    return {"rawPath": path, "body": json.dumps(body) if body is not None else "", "isBase64Encoded": False,
            "requestContext": {"http": {"method": method}, "requestId": "test"}}


@pytest.fixture(autouse=True)
def local_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_STORAGE", LocalStorage(tmp_path))
    return tmp_path


def test_health_and_index():
    assert json.loads(h.handler(event("GET", "/api/health"))["body"])["ok"] is True
    page = h.handler(event("GET", "/"))
    assert page["statusCode"] == 200 and "Kampan" in page["body"]
    assert "Content-Security-Policy" in page["headers"]


def test_static_path_traversal_blocked():
    assert h.handler(event("GET", "/static/../handler.py"))["statusCode"] == 404


def test_upload_returns_a_key_and_target():
    res = json.loads(h.handler(event("POST", "/api/upload", {"filename": "a.mov", "content_type": "video/quicktime"}))["body"])
    assert res["key"].startswith("uploads/") and res["key"].endswith(".mov")
    assert res["method"] == "PUT"


def test_upload_rejects_non_video():
    res = h.handler(event("POST", "/api/upload", {"filename": "a.exe", "content_type": "application/x-msdownload"}))
    assert res["statusCode"] == 400


@pytest.mark.parametrize("body", [
    {"clips": []},
    {"clips": ["../etc/passwd"]},
    {"clips": ["uploads/x.mp4"], "config": {"marker_mm": -1}},
    {"clips": ["uploads/x.mp4"], "config": {"machine_class": "V"}},
    {"clips": ["uploads/x.mp4"], "answers": {"evil": 1}},
    {"clips": ["uploads/x.mp4"], "answers": {"approve_ticket": "yes"}},
])
def test_analyze_validates_input(body):
    assert h.handler(event("POST", "/api/analyze", body))["statusCode"] == 400


def test_analyze_missing_clip_is_a_clean_400():
    res = h.handler(event("POST", "/api/analyze", {"clips": ["uploads/missing.mp4"]}))
    assert res["statusCode"] == 400


def test_bad_json_is_400():
    bad = event("POST", "/api/analyze")
    bad["body"] = "{not json"
    assert h.handler(bad)["statusCode"] == 400


def test_unknown_route_404():
    assert h.handler(event("GET", "/nope"))["statusCode"] == 404


def test_key_pattern():
    assert check_key("samples/clean-0.avi") == "samples/clean-0.avi"
    with pytest.raises(ValueError):
        check_key("uploads/../x")


def test_answers_parsing():
    parsed = service.parse_answers({"capture_fps:0": 240, "running_hz": "unknown", "approve_ticket": True})
    assert parsed == {"capture_fps:0": 240.0, "running_hz": None, "approve_ticket": True}


def test_config_phone_rates():
    cfg = service.parse_config({"marker_mm": 30, "machine_class": "II", "phone_rates": [240, 30, 25]})
    assert cfg.phone_rates == (25.0, 30.0, 240.0) and cfg.machine_class == "II"
