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


def test_players_endpoint(monkeypatch):
    import dartsmod.api as api_mod
    roster = [
        {"key": 1, "name": "Luke Littler", "country": "ENG",
         "scoring_average": 105.0, "three_dart_average": 101.0, "checkout_percentage": 43.0},
    ]
    monkeypatch.setattr(api_mod, "find_players", lambda query="", limit=200: roster)
    resp = client.get("/players?q=luke")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["name"] == "Luke Littler"
    assert body[0]["checkout_percentage"] == 43.0


def test_fixtures_endpoint(monkeypatch):
    import dartsmod.api as api_mod
    roster = [{"key": 34, "name": "Luke Humphries", "country": "ENG",
               "scoring_average": 109.3, "three_dart_average": 99.7, "checkout_percentage": 41.1}]
    matches = [{"event": "World Matchplay", "round": "Final", "date": "2026-07-26T19:00:00Z",
                "p1_key": 34, "p1_name": "Luke Humphries",
                "p2_key": 9999, "p2_name": "Qualifier X"}]
    monkeypatch.setattr(api_mod, "get_players", lambda: roster)
    monkeypatch.setattr(api_mod, "get_upcoming_matches", lambda: matches)
    resp = client.get("/fixtures")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["player_1"]["known"] is True   # in roster -> real stats
    assert body[0]["player_1"]["scoring_average"] == 109.3
    assert body[0]["player_2"]["known"] is False  # unknown -> defaults
    assert body[0]["event"] == "World Matchplay"


def test_fixtures_empty(monkeypatch):
    import dartsmod.api as api_mod
    monkeypatch.setattr(api_mod, "get_upcoming_matches", lambda: [])
    resp = client.get("/fixtures")
    assert resp.status_code == 200
    assert resp.json() == []


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
