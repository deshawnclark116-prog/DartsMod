import random

from dartsmod.engine import play_visit, simulate_leg
from dartsmod.player import DartsPlayer


def _player(avg=98.0, dbl=0.40):
    return DartsPlayer(name="Test", scoring_average=avg, double_prob=dbl)


def test_visit_never_produces_illegal_score():
    rng = random.Random(0)
    player = _player()
    for start in range(2, 502):
        for _ in range(5):
            result = play_visit(start, player, rng)
            assert result.new_score == 0 or result.new_score >= 2
            assert result.new_score <= start
            assert 1 <= result.darts <= 3


def test_leg_terminates_with_valid_winner():
    rng = random.Random(1)
    p1, p2 = _player(), _player()
    for _ in range(200):
        leg = simulate_leg(p1, p2, True, rng)
        assert leg.winner in (1, 2)
        # A leg cannot be won in fewer than 9 darts.
        assert leg.darts[leg.winner] >= 9


def test_throw_advantage():
    rng = random.Random(2)
    p1, p2 = _player(), _player()
    first_thrower_wins = sum(simulate_leg(p1, p2, True, rng).winner == 1 for _ in range(5000))
    # Two identical players: the one throwing first should win clearly more than half.
    assert first_thrower_wins / 5000 > 0.52


def test_better_player_wins_more_legs():
    rng = random.Random(3)
    strong = _player(avg=105.0, dbl=0.45)
    weak = _player(avg=88.0, dbl=0.33)
    strong_wins = sum(simulate_leg(strong, weak, True, rng).winner == 1 for _ in range(3000))
    assert strong_wins / 3000 > 0.65


def test_resume_mid_leg():
    rng = random.Random(4)
    strong = _player(avg=110.0, dbl=0.50)
    weak = _player(avg=85.0, dbl=0.30)
    # Strong player needs 40, weak needs 400+; strong should almost always win.
    wins = sum(
        simulate_leg(strong, weak, True, rng, p1_start=40, p2_start=420, p1_to_throw=True).winner == 1
        for _ in range(2000)
    )
    assert wins / 2000 > 0.85
