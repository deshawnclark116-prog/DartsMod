"""Monte Carlo driver and result aggregation.

Running thousands of independent match simulations turns the per-match outcomes
into probabilities: not just who wins, but the full distribution of scorelines,
total legs (over/under markets), 180 counts and player averages.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .formats import Format
from .match import LiveState, MatchResult, simulate_match
from .player import DartsPlayer


@dataclass
class SimulationResult:
    player_1: str
    player_2: str
    fmt: Format
    n: int
    p1_wins: int
    p2_wins: int
    set_scorelines: Counter = field(default_factory=Counter)
    leg_scorelines: Counter = field(default_factory=Counter)
    total_legs: List[int] = field(default_factory=list)
    p1_avg: float = 0.0
    p2_avg: float = 0.0
    p1_180s: float = 0.0
    p2_180s: float = 0.0
    p1_doubles_pct: float = 0.0
    p2_doubles_pct: float = 0.0

    # --- Headline probabilities ---------------------------------------------

    @property
    def p1_win_prob(self) -> float:
        return self.p1_wins / self.n

    @property
    def p2_win_prob(self) -> float:
        return self.p2_wins / self.n

    def fair_odds(self) -> Tuple[float, float]:
        """Fair decimal odds (1 / probability) for each player."""
        p1 = self.p1_win_prob or 1e-9
        p2 = self.p2_win_prob or 1e-9
        return 1.0 / p1, 1.0 / p2

    # --- Market helpers ------------------------------------------------------

    def most_likely_scorelines(self, k: int = 5) -> List[Tuple[str, float]]:
        counter = self.set_scorelines if self.fmt.is_set_play else self.leg_scorelines
        return [(s, c / self.n) for s, c in counter.most_common(k)]

    def over_under(self, line: float) -> Tuple[float, float]:
        """Probability of total legs going over / under ``line`` (e.g. 10.5)."""
        over = sum(1 for t in self.total_legs if t > line) / self.n
        under = sum(1 for t in self.total_legs if t < line) / self.n
        return over, under

    def expected_total_legs(self) -> float:
        return sum(self.total_legs) / self.n

    def summary(self) -> str:
        lines = [
            f"=== {self.player_1} vs {self.player_2} ===",
            f"Format: {self.fmt.name}   |   Simulations: {self.n:,}",
            "",
            f"{self.player_1} win probability: {self.p1_win_prob:6.2%}  (fair odds {1/max(self.p1_win_prob,1e-9):.2f})",
            f"{self.player_2} win probability: {self.p2_win_prob:6.2%}  (fair odds {1/max(self.p2_win_prob,1e-9):.2f})",
            "",
            "Most likely scorelines:",
        ]
        for score, prob in self.most_likely_scorelines():
            lines.append(f"  {score:>7}: {prob:6.2%}")
        lines += [
            "",
            f"Expected total legs: {self.expected_total_legs():.1f}",
            f"Simulated averages : {self.player_1} {self.p1_avg:.2f}   {self.player_2} {self.p2_avg:.2f}",
            f"Simulated 180s/match: {self.player_1} {self.p1_180s:.1f}   {self.player_2} {self.p2_180s:.1f}",
            f"Simulated doubles %: {self.player_1} {self.p1_doubles_pct:.1f}%   {self.player_2} {self.p2_doubles_pct:.1f}%",
        ]
        return "\n".join(lines)


def run_simulation(
    player_1: DartsPlayer,
    player_2: DartsPlayer,
    fmt: Format,
    n: int = 10_000,
    first_thrower_p1: bool = True,
    state: Optional[LiveState] = None,
    seed: Optional[int] = None,
) -> SimulationResult:
    """Run ``n`` Monte Carlo simulations of the match and aggregate the results."""
    rng = random.Random(seed)

    p1_wins = 0
    set_scorelines: Counter = Counter()
    leg_scorelines: Counter = Counter()
    total_legs: List[int] = []
    sum_darts = {1: 0, 2: 0}
    sum_points = {1: 0, 2: 0}
    sum_180s = {1: 0, 2: 0}
    sum_dbl_att = {1: 0, 2: 0}
    sum_dbl_hit = {1: 0, 2: 0}

    for _ in range(n):
        result: MatchResult = simulate_match(
            player_1, player_2, fmt, rng,
            first_thrower_p1=first_thrower_p1, state=state,
        )
        if result.winner == 1:
            p1_wins += 1
        set_scorelines[f"{result.sets[1]}-{result.sets[2]}"] += 1
        leg_scorelines[f"{result.legs[1]}-{result.legs[2]}"] += 1
        total_legs.append(result.legs_played)
        for pid in (1, 2):
            sum_darts[pid] += result.darts[pid]
            sum_points[pid] += result.points[pid]
            sum_180s[pid] += result.one_eighties[pid]
            sum_dbl_att[pid] += result.double_attempts[pid]
            sum_dbl_hit[pid] += result.double_hits[pid]

    def avg(pid: int) -> float:
        return sum_points[pid] / sum_darts[pid] * 3.0 if sum_darts[pid] else 0.0

    def dbl_pct(pid: int) -> float:
        return sum_dbl_hit[pid] / sum_dbl_att[pid] * 100.0 if sum_dbl_att[pid] else 0.0

    return SimulationResult(
        player_1=player_1.name,
        player_2=player_2.name,
        fmt=fmt,
        n=n,
        p1_wins=p1_wins,
        p2_wins=n - p1_wins,
        set_scorelines=set_scorelines,
        leg_scorelines=leg_scorelines,
        total_legs=total_legs,
        p1_avg=avg(1),
        p2_avg=avg(2),
        p1_180s=sum_180s[1] / n,
        p2_180s=sum_180s[2] / n,
        p1_doubles_pct=dbl_pct(1),
        p2_doubles_pct=dbl_pct(2),
    )
