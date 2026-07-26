from dartsmod import backtest as bt

SAMPLE_ROW = '''
<tbody><tr>
<td><a href="https://dartsorakel.com/player/details/34/luke-humphries">Luke Humphries</a></td>
<td>6 V 3</td>
<td><a href="https://dartsorakel.com/player/details/1/michael-van-gerwen">Michael van Gerwen</a></td>
<td><a href="/match/stats/1">eye</a></td>
</tr></tbody>
'''


def test_row_regex_parses_winner_first():
    m = bt._ROW_RE.search(SAMPLE_ROW)
    assert m is not None
    k1, n1, s1, s2, k2, n2 = m.groups()
    assert (int(k1), int(s1), int(s2), int(k2)) == (34, 6, 3, 1)


def test_parse_event_results_orders_winner(monkeypatch):
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return SAMPLE_ROW.encode("utf-8")
    monkeypatch.setattr(bt.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    matches = bt.parse_event_results(9999)
    assert len(matches) == 1
    m = matches[0]
    assert m["winner_key"] == 34 and m["w_score"] == 6
    assert m["loser_key"] == 1 and m["l_score"] == 3


def test_run_backtest_metrics_favour_stronger_player():
    # A clearly stronger player as the actual winner of every match.
    index = {
        10: {"name": "Strong", "scoring_average": 108, "checkout_percentage": 45,
             "with_throw_average": 109, "against_throw_average": 107, "form_std": 4.0},
        20: {"name": "Weak", "scoring_average": 88, "checkout_percentage": 33,
             "with_throw_average": 88, "against_throw_average": 88, "form_std": 8.0},
    }
    matches = [
        {"winner_key": 10, "winner_name": "Strong", "w_score": 6,
         "loser_key": 20, "loser_name": "Weak", "l_score": 1}
        for _ in range(6)
    ]
    result = bt.run_backtest(matches, index, n=400, rich=True, seed=1)
    assert result["n_matches"] == 6
    assert result["mean_winner_prob"] > 0.6      # model liked the actual winner
    assert result["brier"] < 0.25                # better than a coin flip
    assert result["accuracy"] >= 0.8


def test_make_player_defaults_for_unknown():
    p = bt._make_player(999999, "Nobody", {}, rich=True)
    assert p.name == "Nobody" and p.scoring_average == 95.0
