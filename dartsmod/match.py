"""Match simulation across leg- and set-play formats.

Throwing order is tracked faithfully: within a set the players alternate who
throws first each leg, and the player who starts a new set is the one who did
*not* start the previous set. This "advantage of throw" is a genuine edge and the
simulation honours it exactly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Optional

from .engine import simulate_leg
from .formats import Format
from .player import DartsPlayer


@dataclass
class LiveState:
    """A partially-played match, used to resume a simulation for in-play prediction.

    ``sets`` and ``legs_in_set`` are ``{1: p1, 2: p2}`` counts. The in-progress leg
    (if any) is described by the remaining ``leg_scores`` and whose turn it is
    (``p1_to_throw``). ``set_starter_p1`` / ``leg_starter_p1`` capture who opened
    the current set and current leg respectively.
    """

    sets: Dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    legs_in_set: Dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    leg_scores: Dict[int, int] = field(default_factory=lambda: {1: 501, 2: 501})
    p1_to_throw: bool = True
    set_starter_p1: bool = True
    leg_starter_p1: bool = True


@dataclass
class MatchResult:
    winner: int
    sets: Dict[int, int]
    legs: Dict[int, int]              # total legs across the match
    darts: Dict[int, int]
    points: Dict[int, int]
    one_eighties: Dict[int, int]
    double_attempts: Dict[int, int]
    double_hits: Dict[int, int]
    high_checkout: Dict[int, int]
    legs_played: int

    def average(self, player: int) -> float:
        """The player's simulated three-dart average for the match."""
        if self.darts[player] == 0:
            return 0.0
        return self.points[player] / self.darts[player] * 3.0

    def doubles_pct(self, player: int) -> float:
        if self.double_attempts[player] == 0:
            return 0.0
        return self.double_hits[player] / self.double_attempts[player] * 100.0


def simulate_match(
    player_1: DartsPlayer,
    player_2: DartsPlayer,
    fmt: Format,
    rng: random.Random,
    first_thrower_p1: bool = True,
    state: Optional[LiveState] = None,
) -> MatchResult:
    """Simulate a full match (optionally resuming from a :class:`LiveState`)."""
    sets = {1: 0, 2: 0}
    darts = {1: 0, 2: 0}
    points = {1: 0, 2: 0}
    one_eighties = {1: 0, 2: 0}
    double_attempts = {1: 0, 2: 0}
    double_hits = {1: 0, 2: 0}
    high_checkout = {1: 0, 2: 0}
    total_legs = {1: 0, 2: 0}
    legs_played = 0

    if state is None:
        set_starter_p1 = first_thrower_p1
        legs_in_set = {1: 0, 2: 0}
        leg_starter_p1 = set_starter_p1
        resume_scores = None
        resume_turn = None
    else:
        sets.update(state.sets)
        set_starter_p1 = state.set_starter_p1
        legs_in_set = dict(state.legs_in_set)
        leg_starter_p1 = state.leg_starter_p1
        resume_scores = dict(state.leg_scores)
        resume_turn = state.p1_to_throw

    def record_leg(leg) -> None:
        nonlocal legs_played
        for pid in (1, 2):
            darts[pid] += leg.darts[pid]
            points[pid] += leg.points[pid]
            one_eighties[pid] += leg.one_eighties[pid]
            double_attempts[pid] += leg.double_attempts[pid]
            double_hits[pid] += leg.double_hits[pid]
        total_legs[leg.winner] += 1
        legs_in_set[leg.winner] += 1
        high_checkout[leg.winner] = max(high_checkout[leg.winner], leg.checkout)
        legs_played += 1

    while sets[1] < fmt.sets_to_win and sets[2] < fmt.sets_to_win:
        # Play out the current set.
        while (
            legs_in_set[1] < fmt.legs_to_win_set
            and legs_in_set[2] < fmt.legs_to_win_set
        ):
            if resume_scores is not None:
                leg = simulate_leg(
                    player_1, player_2, leg_starter_p1, rng,
                    p1_start=resume_scores[1], p2_start=resume_scores[2],
                    p1_to_throw=resume_turn,
                )
                resume_scores = None
                resume_turn = None
            else:
                leg = simulate_leg(player_1, player_2, leg_starter_p1, rng)
            record_leg(leg)
            leg_starter_p1 = not leg_starter_p1

        set_winner = 1 if legs_in_set[1] > legs_in_set[2] else 2
        sets[set_winner] += 1
        legs_in_set = {1: 0, 2: 0}
        set_starter_p1 = not set_starter_p1
        leg_starter_p1 = set_starter_p1

    winner = 1 if sets[1] == fmt.sets_to_win else 2
    return MatchResult(
        winner=winner,
        sets=sets,
        legs=total_legs,
        darts=darts,
        points=points,
        one_eighties=one_eighties,
        double_attempts=double_attempts,
        double_hits=double_hits,
        high_checkout=high_checkout,
        legs_played=legs_played,
    )
