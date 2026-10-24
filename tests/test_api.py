"""Accounts, roles and the records they protect, driven through the real handler."""
import pytest

from app.api import measure as measure_api
from tests.api_client import Client

DONE = {"status": "done", "events": [{"kind": "human", "field": "running_hz"}], "seconds": 1.0,
        "report": {"verdict": "graded", "zone": "C", "velocity_mm_s": 3.5, "dominant_hz": 21.0,
                   "signature": "unbalance", "summary": "zone C", "caveats": []},
        "ticket": {"title": "Vibration zone C", "evidence": "1x dominant"}, "ticket_approved": True,
        "captures": [{}], "visuals": {}}


@pytest.fixture()
def agent(monkeypatch):
    """Replace the OpenCV run with a fixed result; these tests are about records and permissions."""
    results = []

    def fake(body, storage):
        results.append(body)
        out = dict(DONE)
        out["report"] = {**DONE["report"], "velocity_mm_s": 3.5 if len(results) == 1 else 5.0}
        return out
    monkeypatch.setattr(measure_api.service, "analyze", fake)
    return results


def team(api):
    lead = Client("10.0.0.1")
    lead.sign_up("Asha")
    _, inv = lead.post("/api/team/invites")
    tech = Client("10.0.0.2")
    me = tech.sign_up("Ravi", invite=inv["data"]["token"])
    assert me["role"] == "technician"
    _, m = lead.post("/api/machines", {"name": "Cooling fan", "machine_class": "I", "rpm": 1260})
    return lead, tech, m["data"]["machine_id"], inv["data"]["token"]


def test_sign_up_then_sign_in_with_the_same_passkey(api):
    c = Client()
    me = c.sign_up("Asha")
    assert me["role"] == "lead" and me["site"]["name"] == "Asha's site"
    assert "kampan_session" in c.cookies
    c.post("/api/auth/logout")
    assert c.get("/api/me")[1]["data"] == {"signed_in": False}
    status, again = c.sign_in()
    assert status == 200 and again["data"]["user"] == me["user"]


def test_wrong_challenge_and_replayed_challenge_are_refused(api):
    c = Client()
    _, opts = c.post("/api/auth/register/options", {"name": "Eve"})
    cred = c.authenticator.register({"challenge": "not-the-challenge"})
    assert c.post("/api/auth/register/verify", {"challenge_id": opts["data"]["challenge_id"],
                                               "credential": cred})[0] == 401
    cred = c.authenticator.register(opts["data"]["options"])
    assert c.post("/api/auth/register/verify", {"challenge_id": opts["data"]["challenge_id"],
                                               "credential": cred})[0] == 401  # challenge was used up


def test_unknown_passkey_cannot_sign_in(api):
    assert Client().sign_in()[0] == 401


def test_forged_or_edited_cookie_is_ignored(api):
    c = Client()
    c.sign_up("Asha")
    payload, sig = c.cookies["kampan_session"].split(".")
    c.cookies["kampan_session"] = payload[:-2] + "xx." + sig
    assert c.get("/api/me")[1]["data"] == {"signed_in": False}
    assert c.get("/api/machines")[0] == 401


def test_roles_are_enforced_by_the_server(api, agent):
    lead, tech, machine_id, _ = team(api)
    assert tech.post("/api/machines", {"name": "x"})[0] == 403
    assert tech.post("/api/team/invites")[0] == 403
    assert lead.post("/api/measure", {"machine_id": machine_id, "session_id": "abcdef12",
                                     "clips": ["uploads/a.mp4"]})[0] == 403
    assert lead.post("/api/uploads", {"filename": "a.mp4"})[0] == 403


def test_invite_is_single_use(api):
    _, _, _, token = team(api)
    other = Client("10.0.0.3")
    other.sign_up("Mallory")
    assert other.post(f"/api/invites/{token}/accept")[0] == 409
    assert other.get(f"/api/invites/{token}")[0] == 409


def test_other_sites_records_are_invisible(api, agent):
    _, _, machine_id, _ = team(api)
    outsider = Client("10.0.0.4")
    outsider.sign_up("Mallory")
    assert outsider.get(f"/api/machines/{machine_id}")[0] == 404
    assert outsider.post(f"/api/machines/{machine_id}/share")[0] == 404
    outsider.post("/api/session/switch", {"role": "technician"})
    assert outsider.post("/api/measure", {"machine_id": machine_id, "session_id": "abcdef12",
                                         "clips": ["uploads/a.mp4"]})[0] == 404


def test_switching_to_a_role_you_do_not_hold_is_refused(api):
    _, tech, _, _ = team(api)
    me = tech.get("/api/me")[1]["data"]
    status, body = tech.post("/api/session/switch", {"role": "lead", "site_id": me["site"]["site_id"]})
    assert status == 403
    status, body = tech.post("/api/session/switch", {"role": "lead"})  # own site, created on demand
    assert status == 200 and body["data"]["site"]["site_id"] != me["site"]["site_id"]


def test_measurement_ticket_loop_and_trend(api, agent):
    lead, tech, machine_id, _ = team(api)
    body = {"machine_id": machine_id, "session_id": "run000001", "clips": ["uploads/a.mp4"]}
    status, first = tech.post("/api/measure", body)
    assert status == 200 and first["data"]["saved"]["ticket_id"]
    assert agent[0]["answers"]["running_hz"] == pytest.approx(21.0)  # rpm from the machine record
    assert tech.post("/api/measure", body)[1]["data"]["saved"] == first["data"]["saved"]  # idempotent
    _, second = tech.post("/api/measure", {**body, "session_id": "run000002"})
    assert second["data"]["saved"]["change"]["alert"] is True
    tickets = lead.get("/api/tickets")[1]["data"]["tickets"]
    assert [t["status"] for t in tickets] == ["open", "open"]
    tid = tickets[0]["ticket_id"]
    assert tech.post(f"/api/tickets/{tid}/decision", {"approve": True})[0] == 403
    assert lead.post(f"/api/tickets/{tid}/decision", {"approve": True})[1]["data"]["status"] == "approved"
    assert lead.post(f"/api/tickets/{tid}/decision", {"approve": False})[0] == 409
    detail = lead.get(f"/api/machines/{machine_id}")[1]["data"]
    assert detail["machine"]["measurements"] == 2 and detail["machine"]["last_velocity"] == 5.0
    mid = detail["measurements"][0]["measurement_id"]
    status, trace = tech.get(f"/api/machines/{machine_id}/measurements/{mid}/trace")
    assert status == 200 and trace["data"]["report"]["zone"] == "C"


def test_share_link_is_read_only_and_revocable(api, agent):
    lead, tech, machine_id, _ = team(api)
    tech.post("/api/measure", {"machine_id": machine_id, "session_id": "run000001", "clips": ["uploads/a.mp4"]})
    token = lead.post(f"/api/machines/{machine_id}/share")[1]["data"]["share_token"]
    status, page = Client("10.0.0.9").get(f"/api/share/{token}")
    assert status == 200 and page["data"]["machine"]["name"] == "Cooling fan"
    assert "by_name" not in page["data"]["measurements"][0]
    lead.post(f"/api/machines/{machine_id}/unshare")
    assert Client("10.0.0.9").get(f"/api/share/{token}")[0] == 404


def test_cross_site_post_is_refused(api):
    c = Client()
    c.sign_up("Asha")
    assert c.post("/api/machines", {"name": "x"}, origin="https://evil.example")[0] == 403


def test_rate_limit(api):
    c = Client("10.9.9.9")
    codes = [c.post("/api/auth/login/options")[0] for _ in range(22)]
    assert codes[:20] == [200] * 20 and codes[-1] == 429


def test_impact_counts_come_from_records(api, agent):
    _, tech, machine_id, _ = team(api)
    tech.post("/api/measure", {"machine_id": machine_id, "session_id": "run000001", "clips": ["uploads/a.mp4"]})
    stats = Client("10.0.0.8").get("/api/impact")[1]["data"]["stats"]
    assert stats["sites"] == 1 and stats["machines"] == 1 and stats["measurements"] == 1 and stats["tickets"] == 1
