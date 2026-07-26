import dartsmod.data as data


def _fake_payloads():
    return {
        data.RANK_KEYS["average"]: {"data": [
            {"player_key": 1, "player_name": "Alpha", "country": "ENG", "stat": "100.0"},
            {"player_key": 2, "player_name": "Beta", "country": "NED", "stat": "95.5"},
        ]},
        data.RANK_KEYS["first9"]: {"data": [
            {"player_key": 1, "player_name": "Alpha", "country": "ENG", "stat": "105.0"},
            # Beta missing First-9 on purpose -> should fall back to three-dart avg.
        ]},
        data.RANK_KEYS["checkout"]: {"data": [
            {"player_key": 1, "player_name": "Alpha", "country": "ENG", "stat": "42.0%"},
            {"player_key": 2, "player_name": "Beta", "country": "NED", "stat": "999%"},  # outlier
        ]},
    }


def test_build_database_joins_and_validates(monkeypatch):
    payloads = _fake_payloads()
    monkeypatch.setattr(data, "_fetch_json", lambda rank_key, *a, **k: payloads[rank_key])

    players = data.build_player_database(top_n=10)
    by_name = {p["name"]: p for p in players}

    # Ranked by three-dart average, highest first.
    assert [p["name"] for p in players] == ["Alpha", "Beta"]

    # Alpha: First-9 used as scoring average, checkout parsed.
    assert by_name["Alpha"]["scoring_average"] == 105.0
    assert by_name["Alpha"]["checkout_percentage"] == 42.0

    # Beta: missing First-9 -> falls back to three-dart avg; outlier checkout -> default.
    assert by_name["Beta"]["scoring_average"] == 95.5
    assert by_name["Beta"]["checkout_percentage"] == data._DEFAULT_CHECKOUT


def test_get_players_falls_back_on_failure(monkeypatch):
    data._cache["players"] = None
    data._cache["ts"] = 0.0

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(data, "build_player_database", boom)
    players = data.get_players(force_refresh=True)
    assert players == data._FALLBACK_PLAYERS
    assert any(p["name"] == "Luke Littler" for p in players)


def test_get_players_uses_cache(monkeypatch):
    sentinel = [{"key": 99, "name": "Cached", "country": "ENG",
                 "scoring_average": 100.0, "three_dart_average": 95.0, "checkout_percentage": 40.0}]
    data._cache["players"] = sentinel
    data._cache["ts"] = data.time.time()

    def boom(*a, **k):
        raise AssertionError("should not refetch while cache is fresh")

    monkeypatch.setattr(data, "build_player_database", boom)
    assert data.get_players() == sentinel


def test_find_players_search(monkeypatch):
    roster = [
        {"key": 1, "name": "Luke Littler", "country": "ENG", "scoring_average": 105.0, "three_dart_average": 101.0, "checkout_percentage": 43.0},
        {"key": 2, "name": "Gerwyn Price", "country": "WAL", "scoring_average": 99.0, "three_dart_average": 98.0, "checkout_percentage": 39.0},
    ]
    monkeypatch.setattr(data, "get_players", lambda force_refresh=False: roster)
    assert [p["name"] for p in data.find_players("luke")] == ["Luke Littler"]
    assert len(data.find_players("", limit=1)) == 1


def test_parse_stat():
    assert data._parse_stat("101.47") == 101.47
    assert data._parse_stat("43.5%") == 43.5
    assert data._parse_stat("1,234") == 1234.0
    assert data._parse_stat(None) is None
    assert data._parse_stat("n/a") is None
