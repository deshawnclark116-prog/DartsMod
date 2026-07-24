from dartsmod.checkout import BOGEY_NUMBERS, is_finishable, plan_route


def _route_sum(route):
    return sum(target[2] for target in route)


def test_one_dart_doubles():
    for score in range(2, 41, 2):
        route = plan_route(score)
        assert route is not None
        assert len(route) == 1
        assert route[0][0] == "D"
        assert _route_sum(route) == score


def test_bullseye_is_a_double_finish():
    route = plan_route(50)
    assert route == [("D", 25, 50)]


def test_odd_low_scores_take_two_darts():
    for score in range(3, 40, 2):
        route = plan_route(score)
        assert route is not None
        assert len(route) == 2
        assert route[-1][0] == "D"


def test_max_checkout_170():
    route = plan_route(170)
    assert route is not None
    assert _route_sum(route) == 170
    assert route[-1][0] == "D"
    assert len(route) == 3


def test_bogey_numbers_are_unfinishable():
    for score in BOGEY_NUMBERS:
        assert plan_route(score) is None
        assert not is_finishable(score)


def test_scores_above_170_unfinishable():
    assert plan_route(171) is None
    assert plan_route(180) is None


def test_all_finishes_end_on_a_double():
    finishable = 0
    for score in range(2, 171):
        route = plan_route(score)
        if route is None:
            continue
        finishable += 1
        assert route[-1][0] == "D"
        assert _route_sum(route) == score
        assert len(route) <= 3
    assert finishable > 150  # the vast majority of 2..170 is finishable


def test_darts_left_constraint():
    # 100 cannot be finished with a single dart, but can with three.
    assert plan_route(100, darts_left=1) is None
    assert plan_route(100, darts_left=3) is not None
