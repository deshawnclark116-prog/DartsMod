import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dartsmod.api import api  # noqa: E402

client = TestClient(api)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_formats_lists_presets():
    resp = client.get("/formats")
    assert resp.status_code == 200
    body = resp.json()
    assert "premier_league" in body["presets"]


def test_simulate_basic():
    resp = client.post("/simulate", json={
        "player_1": {"name": "A", "scoring_average": 104, "double_prob": 0.44},
        "player_2": {"name": "B", "scoring_average": 92, "checkout_percentage": 35},
        "format": "premier_league",
        "sims": 2000,
        "seed": 1,
        "over_under_line": 10.5,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert abs(body["win_prob"]["player_1"] + body["win_prob"]["player_2"] - 1.0) < 1e-9
    assert body["win_prob"]["player_1"] > 0.6  # stronger player favoured
    assert len(body["scorelines"]) > 0
    assert body["over_under"]["over"] + body["over_under"]["under"] == pytest.approx(1.0)


def test_simulate_custom_setplay_format():
    resp = client.post("/simulate", json={
        "player_1": {"name": "A", "scoring_average": 100},
        "player_2": {"name": "B", "scoring_average": 100},
        "legs_to_win_set": 3,
        "sets_to_win": 5,
        "sims": 1000,
        "seed": 2,
    })
    assert resp.status_code == 200
    assert "sets" in resp.json()["format"]


def test_simulate_inplay_state():
    resp = client.post("/simulate", json={
        "player_1": {"name": "A", "scoring_average": 110, "double_prob": 0.5},
        "player_2": {"name": "B", "scoring_average": 85, "double_prob": 0.3},
        "format": "bestof11",
        "sims": 1000,
        "seed": 3,
        "state": {"legs_p1": 5, "legs_p2": 0, "score_p1": 40, "score_p2": 400, "p1_to_throw": True},
    })
    assert resp.status_code == 200
    assert resp.json()["win_prob"]["player_1"] > 0.95  # basically won


def test_simulate_rejects_unknown_format():
    resp = client.post("/simulate", json={
        "player_1": {"name": "A"},
        "player_2": {"name": "B"},
        "format": "not_a_real_format",
        "sims": 100,
    })
    assert resp.status_code == 422
