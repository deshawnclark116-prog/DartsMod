"""Turning raw history into world-class model inputs.

The Monte Carlo engine is only as good as the parameters fed into it. Lifetime
averages are a trap: darts form swings violently, the stage plays nothing like the
practice floor, and a brutal travel schedule quietly drains a player. These
helpers convert a match history into the ``scoring_average`` / ``double_prob``
inputs the engine consumes.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from .player import DartsPlayer


def exponential_moving_average(values: Sequence[float], half_life: float = 5.0) -> float:
    """Recency-weighted average of ``values`` (most recent **first**).

    A ``half_life`` of 5 means a match five games ago carries half the weight of
    the most recent one -- the right order of magnitude for darts form, where the
    last handful of matches dominate.
    """
    if not values:
        raise ValueError("values must be non-empty")
    decay = 0.5 ** (1.0 / half_life)
    weighted_sum = 0.0
    weight_total = 0.0
    weight = 1.0
    for value in values:
        weighted_sum += weight * value
        weight_total += weight
        weight *= decay
    return weighted_sum / weight_total


def stage_adjust(
    player: DartsPlayer,
    on_stage: bool,
    scoring_penalty_pct: float = 5.0,
    double_penalty_pct: float = 5.0,
) -> DartsPlayer:
    """Apply a stage/floor coefficient.

    Many players average several points lower under the lights of a televised
    major than in a quiet floor event. Pass ``on_stage=True`` with each player's
    historically observed drop-off.
    """
    if not on_stage:
        return player
    return replace(
        player,
        scoring_average=player.scoring_average * (1 - scoring_penalty_pct / 100.0),
        double_prob=player.double_prob * (1 - double_penalty_pct / 100.0),
        bull_prob=None,  # recomputed from the new double_prob
    )


def fatigue_adjust(player: DartsPlayer, scoring_penalty: float = 1.5) -> DartsPlayer:
    """Subtract a flat scoring penalty for a fatigued/heavily-travelled player."""
    return replace(
        player,
        scoring_average=max(1.0, player.scoring_average - scoring_penalty),
    )


def build_player(
    name: str,
    scoring_history: Sequence[float],
    checkout_history: Sequence[float],
    half_life: float = 5.0,
    on_stage: bool = False,
    stage_penalty_pct: float = 5.0,
    fatigued: bool = False,
    fatigue_penalty: float = 1.5,
) -> DartsPlayer:
    """Build a fully-adjusted player from recent history.

    ``scoring_history`` and ``checkout_history`` are recent-first sequences of
    per-match three-dart (scoring) averages and checkout percentages. Form is
    blended with an EMA, then stage and fatigue coefficients are applied.
    """
    scoring = exponential_moving_average(scoring_history, half_life)
    checkout = exponential_moving_average(checkout_history, half_life)
    player = DartsPlayer.from_stats(name, three_dart_average=scoring, checkout_percentage=checkout)
    player = stage_adjust(player, on_stage, stage_penalty_pct, stage_penalty_pct)
    if fatigued:
        player = fatigue_adjust(player, fatigue_penalty)
    return player
