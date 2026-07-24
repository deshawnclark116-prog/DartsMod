"""The visit-level simulation engine.

A leg of 501 is simulated one *visit* (three-dart turn) at a time, and within a
visit one dart at a time. Each dart decides its own target from the current
remaining score:

* If the score is finishable in the remaining darts, the player throws the next
  dart of the standard checkout route (a setup single/treble, or the finishing
  double).
* Otherwise the player is scoring, and throws at the treble-20 bed.

This mirrors the physical reality of the game, so the emergent statistics -- three
-dart average, doubles percentage, 180 count, checkout distribution -- fall out of
the simulation instead of being asserted up front.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, NamedTuple, Optional

from .checkout import plan_route
from .player import DartsPlayer

# Outcome distribution for a dart aimed at the treble-20 bed but not hitting the
# treble. Values must match ``dartsmod.player._NON_TREBLE_EV``.
_SCORING_MISS_PROFILE = ((20, 0.60), (5, 0.25), (1, 0.10), (0, 0.05))


class VisitResult(NamedTuple):
    new_score: int
    darts: int
    checked_out: bool
    scored: int          # points scored this visit (0 on a bust)
    double_attempts: int
    double_hits: int


@dataclass
class LegResult:
    winner: int                      # 1 or 2
    darts: Dict[int, int]
    points: Dict[int, int]
    one_eighties: Dict[int, int]
    double_attempts: Dict[int, int]
    double_hits: Dict[int, int]
    checkout: int                    # the score the winner checked out from


def _scoring_dart(player: DartsPlayer, rng: random.Random) -> int:
    """Return the points from a single dart thrown while scoring (aiming T20)."""
    if rng.random() < player.treble_prob:
        return 60
    roll = rng.random()
    cumulative = 0.0
    for value, weight in _SCORING_MISS_PROFILE:
        cumulative += weight
        if roll < cumulative:
            return value
    return 0


def play_visit(score: int, player: DartsPlayer, rng: random.Random) -> VisitResult:
    """Simulate one three-dart visit from ``score`` and return the outcome."""
    start = score
    darts = 0
    double_attempts = 0
    double_hits = 0

    for i in range(3):
        darts_left = 3 - i
        darts += 1
        route = plan_route(score, darts_left)

        if route is not None:
            kind, number, value = route[0]
            if kind == "D":
                double_attempts += 1
                if rng.random() < player.double_prob_for(number):
                    double_hits += 1
                    return VisitResult(0, darts, True, start, double_attempts, double_hits)
                # Missed the double.
                if rng.random() < player.single_on_miss:
                    landed = score - number  # clipped the single of the double's number
                    if landed < 2:
                        # Bust: the whole visit is void, score reverts.
                        return VisitResult(start, darts, False, 0, double_attempts, double_hits)
                    score = landed
                # else: missed the board entirely, score unchanged; try again.
            else:
                # Setup dart (single or treble).
                success = player.treble_prob if kind == "T" else player.single_prob
                if rng.random() < success:
                    score -= value
                elif kind == "T":
                    # A missed treble usually clips the single of that number.
                    score -= number
                # A missed single is treated as a wasted dart (score unchanged).
        else:
            # Pure scoring dart.
            gained = _scoring_dart(player, rng)
            if score - gained >= 2:
                score -= gained
            # Otherwise the dart would bust; the player would pull it, no change.

    return VisitResult(score, darts, False, start - score, double_attempts, double_hits)


def simulate_leg(
    player_1: DartsPlayer,
    player_2: DartsPlayer,
    p1_throws_first: bool,
    rng: random.Random,
    p1_start: int = 501,
    p2_start: int = 501,
    p1_to_throw: Optional[bool] = None,
) -> LegResult:
    """Simulate a single leg of 501.

    The leg can be resumed mid-way for live/in-play prediction by supplying the
    current remaining scores and whose turn it is (``p1_to_throw``). By default the
    leg starts fresh with the thrower given by ``p1_throws_first``.
    """
    scores = {1: p1_start, 2: p2_start}
    players = {1: player_1, 2: player_2}
    darts = {1: 0, 2: 0}
    one_eighties = {1: 0, 2: 0}
    double_attempts = {1: 0, 2: 0}
    double_hits = {1: 0, 2: 0}

    to_throw = p1_throws_first if p1_to_throw is None else p1_to_throw
    turn = 1 if to_throw else 2

    winner = 0
    checkout_from = 0
    while winner == 0:
        player = players[turn]
        before = scores[turn]
        result = play_visit(before, player, rng)

        scores[turn] = result.new_score
        darts[turn] += result.darts
        double_attempts[turn] += result.double_attempts
        double_hits[turn] += result.double_hits
        if result.scored == 180 and result.darts == 3 and not result.checked_out:
            one_eighties[turn] += 1

        if result.checked_out:
            winner = turn
            checkout_from = before
            break
        turn = 2 if turn == 1 else 1

    points = {1: 501 - scores[1], 2: 501 - scores[2]}
    points[winner] = 501
    return LegResult(
        winner=winner,
        darts=darts,
        points=points,
        one_eighties=one_eighties,
        double_attempts=double_attempts,
        double_hits=double_hits,
        checkout=checkout_from,
    )
