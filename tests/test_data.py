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
    monkeypatch.setattr(data, "_fetch_json", lambda rank_key, *a, **k: payloads.get(rank_key, {"data": []}))

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
    assert len(players) == len(data._FALLBACK_PLAYERS)
    assert any(p["name"] == "Luke Littler" for p in players)
    # Fallback records are normalized to the full schema.
    from dartsmod.api import PlayerOut
    for p in players:
        PlayerOut(**p)


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


def test_all_records_have_full_schema():
    # Every record (fallback or normalized) must carry the fields the API returns,
    # otherwise the /players response fails validation with a 500.
    required = {"key", "name", "country", "scoring_average", "three_dart_average", "checkout_percentage"}
    for p in data._FALLBACK_PLAYERS:
        assert required <= set(p.keys()), f"fallback player missing fields: {p['name']}"
    normalized = data._normalize({"name": "X", "scoring_average": 90.0})
    assert required <= set(normalized.keys())
    assert normalized["three_dart_average"] == 90.0  # defaults to scoring average


def test_fallback_roster_validates_against_response_model():
    from dartsmod.api import PlayerOut
    for p in data._FALLBACK_PLAYERS:
        PlayerOut(**data._normalize(p))  # must not raise


def test_null_and_malformed_values_do_not_break(monkeypatch):
    # The live feed sometimes has a player with a null country or a non-numeric
    # stat. A single bad record must not 500 the /players response.
    from dartsmod.api import PlayerOut
    payloads = {
        data.RANK_KEYS["average"]: {"data": [
            {"player_key": 1, "player_name": "Good", "country": "ENG", "stat": "100.0"},
            {"player_key": 2, "player_name": "NoCountry", "country": None, "stat": "96.0"},
            {"player_key": 3, "player_name": None, "country": "NED", "stat": "95.0"},
        ]},
        data.RANK_KEYS["first9"]: {"data": []},
        data.RANK_KEYS["checkout"]: {"data": []},
    }
    monkeypatch.setattr(data, "_fetch_json", lambda rank_key, *a, **k: payloads.get(rank_key, {"data": []}))
    data._cache["players"] = None
    data._cache["ts"] = 0.0

    players = data.get_players(force_refresh=True)
    for p in players:
        PlayerOut(**p)  # must not raise
    assert any(p["country"] == "" for p in players)  # null country coerced


def test_upcoming_matches_parsing(monkeypatch):
    rows = [
        {"event_title": "World Matchplay", "round_name": "Quarter Final",
         "match_date": "2026-07-26T19:00:00Z",
         "first_player_key": 34, "first_player_name": "Luke Humphries",
         "second_player_key": 5403, "second_player_name": "Luke Littler"},
        {"first_player_key": None, "second_player_key": 2},  # incomplete -> skipped
    ]
    monkeypatch.setattr(data, "_fetch_upcoming", lambda: rows)
    data._upcoming_cache["matches"] = None
    data._upcoming_cache["ts"] = 0.0

    matches = data.get_upcoming_matches(force_refresh=True)
    assert len(matches) == 1
    m = matches[0]
    assert m["p1_key"] == 34 and m["p2_key"] == 5403
    assert m["event"] == "World Matchplay"
    assert m["round"] == "Quarter Final"


def test_upcoming_matches_fallback_on_error(monkeypatch):
    data._upcoming_cache["matches"] = None
    data._upcoming_cache["ts"] = 0.0
    monkeypatch.setattr(data, "_fetch_upcoming", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert data.get_upcoming_matches(force_refresh=True) == []


def test_infer_match_format():
    # World Matchplay is leg play, not sets.
    f = data.infer_match_format("World Matchplay 2026", "Final")
    assert f["sets_to_win"] == 1 and f["legs_to_win_set"] == 18
    assert data.infer_match_format("World Matchplay 2026", "Quarter Final")["legs_to_win_set"] == 16
    # World Championship is set play.
    wc = data.infer_match_format("PDC World Championship 2026", "Final")
    assert wc["sets_to_win"] == 7 and wc["legs_to_win_set"] == 3
    # Women's Matchplay stays leg play (shorter), never sets.
    w = data.infer_match_format("PDC Womens World Matchplay 2026", "Semi Final")
    assert w["sets_to_win"] == 1
    # Unknown event -> sensible leg-play default.
    d = data.infer_match_format("Some Random Open", "Round 1")
    assert d["sets_to_win"] == 1 and d["legs_to_win_set"] == 6


def test_coerce_float():
    assert data._coerce_float("42.5", 0.0) == 42.5
    assert data._coerce_float(None, 9.0) == 9.0
    assert data._coerce_float("n/a", 9.0) == 9.0


def test_fraction_parsing():
    payload = {"data": [
        {"player_key": 1, "stat": "84/147"},
        {"player_key": 2, "stat": "0/0"},      # zero denominator -> skipped
        {"player_key": 3, "stat": "bad"},      # no slash -> skipped
    ]}
    import dartsmod.data as d
    orig = d._fetch_json
    d._fetch_json = lambda *a, **k: payload
    try:
        m = d._fetch_fraction_map(10006, "a", "b", 1)
    finally:
        d._fetch_json = orig
    assert round(m[1]["frac"], 3) == round(84 / 147, 3)
    assert m[1]["total"] == 147
    assert 2 not in m and 3 not in m


def test_form_std_estimate():
    # A player averaging 100 who hits 100+ half the time and 110+ rarely
    # should get a moderate, clamped std.
    std = data._estimate_form_std(100.0, [(100.0, 0.5), (105.0, 0.30), (110.0, 0.12)])
    assert 3.0 <= std <= 12.0
    # No usable buckets -> default.
    assert data._estimate_form_std(100.0, [(100.0, None), (105.0, None), (110.0, None)]) == 6.0


def test_blend_recency():
    long_map = {1: {"stat": 90.0}}
    recent_map = {1: {"stat": 100.0}}
    # 0.6 recent + 0.4 long
    assert abs(data._blend(long_map, recent_map, 1, 0.6) - 96.0) < 1e-9
    # falls back to whichever exists
    assert data._blend(long_map, {}, 1) == 90.0
    assert data._blend({}, recent_map, 1) == 100.0
    assert data._blend({}, {}, 1) is None


def test_parse_stat():
    assert data._parse_stat("101.47") == 101.47
    assert data._parse_stat("43.5%") == 43.5
    assert data._parse_stat("1,234") == 1234.0
    assert data._parse_stat(None) is None
    assert data._parse_stat("n/a") is None
