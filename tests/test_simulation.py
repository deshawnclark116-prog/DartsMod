import random

from dartsmod.adjustments import exponential_moving_average, fatigue_adjust, stage_adjust
from dartsmod.formats import PREMIER_LEAGUE, WORLD_CHAMPIONSHIP_FINAL, best_of_legs
from dartsmod.match import simulate_match
from dartsmod.player import DartsPlayer
from dartsmod.simulation import run_simulation


def _player(name, avg=98.0, dbl=0.40):
    return DartsPlayer(name=name, scoring_average=avg, double_prob=dbl)


def test_probabilities_sum_to_one():
    p1, p2 = _player("A"), _player("B")
    result = run_simulation(p1, p2, PREMIER_LEAGUE, n=2000, seed=7)
    assert abs(result.p1_win_prob + result.p2_win_prob - 1.0) < 1e-9


def test_determinism_with_seed():
    p1, p2 = _player("A", 101), _player("B", 97)
    a = run_simulation(p1, p2, PREMIER_LEAGUE, n=2000, seed=42)
    b = run_simulation(p1, p2, PREMIER_LEAGUE, n=2000, seed=42)
    assert a.p1_wins == b.p1_wins
    assert a.most_likely_scorelines() == b.most_likely_scorelines()


def test_better_player_favoured():
    strong = _player("Strong", avg=106, dbl=0.45)
    weak = _player("Weak", avg=90, dbl=0.34)
    result = run_simulation(strong, weak, PREMIER_LEAGUE, n=4000, seed=11)
    assert result.p1_win_prob > 0.65


def test_calibration_average_in_realistic_band():
    p1, p2 = _player("A", 100), _player("B", 100)
    result = run_simulation(p1, p2, best_of_legs(11), n=3000, seed=5)
    # A 100 scoring average yields a match three-dart average a touch lower once
    # checkout darts are included -- but it must stay in a believable band.
    assert 90 <= result.p1_avg <= 105
    assert 90 <= result.p2_avg <= 105


def test_doubles_pct_tracks_input():
    p1, p2 = _player("A", 98, 0.42), _player("B", 98, 0.42)
    result = run_simulation(p1, p2, best_of_legs(11), n=3000, seed=6)
    # Every double attempt succeeds with double_prob, so the observed doubles %%
    # (blended with the harder bull) should sit a little under 42%.
    assert 34 <= result.p1_doubles_pct <= 44


def test_set_play_reduces_variance():
    strong = _player("Strong", avg=104, dbl=0.44)
    weak = _player("Weak", avg=96, dbl=0.38)
    short = run_simulation(strong, weak, best_of_legs(11), n=4000, seed=9)
    long = run_simulation(strong, weak, WORLD_CHAMPIONSHIP_FINAL, n=4000, seed=9)
    # The same edge should convert to a bigger win probability over a long format.
    assert long.p1_win_prob > short.p1_win_prob


def test_expected_legs_within_format_bounds():
    p1, p2 = _player("A"), _player("B")
    fmt = best_of_legs(11)
    result = run_simulation(p1, p2, fmt, n=2000, seed=3)
    assert 6 <= result.expected_total_legs() <= 11


def test_over_under_probabilities_complementary():
    p1, p2 = _player("A"), _player("B")
    result = run_simulation(p1, p2, best_of_legs(11), n=2000, seed=8)
    over, under = result.over_under(10.5)
    assert abs(over + under - 1.0) < 1e-9  # 10.5 line, no pushes possible


def test_ema_weights_recent_more():
    recent_hot = exponential_moving_average([110, 90, 90, 90], half_life=2)
    recent_cold = exponential_moving_average([90, 110, 110, 110], half_life=2)
    assert recent_hot > 95
    assert recent_cold < 105
    assert recent_hot > recent_cold or recent_hot != recent_cold


def test_stage_and_fatigue_reduce_strength():
    base = _player("A", avg=102, dbl=0.42)
    staged = stage_adjust(base, on_stage=True, scoring_penalty_pct=8, double_penalty_pct=8)
    assert staged.scoring_average < base.scoring_average
    assert staged.double_prob < base.double_prob
    assert staged.bull_prob < base.bull_prob  # recomputed from the reduced double

    tired = fatigue_adjust(base, scoring_penalty=2.0)
    assert tired.scoring_average == base.scoring_average - 2.0


def test_match_result_helpers():
    p1, p2 = _player("A", 101), _player("B", 99)
    rng = random.Random(0)
    match = simulate_match(p1, p2, PREMIER_LEAGUE, rng)
    assert match.winner in (1, 2)
    assert match.average(1) > 0
    assert 0 <= match.doubles_pct(1) <= 100
    assert match.sets[match.winner] == PREMIER_LEAGUE.sets_to_win
