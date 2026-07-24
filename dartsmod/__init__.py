"""DartsMod -- a visit-level Monte Carlo darts match prediction engine."""

from __future__ import annotations

from .adjustments import (
    build_player,
    exponential_moving_average,
    fatigue_adjust,
    stage_adjust,
)
from .checkout import BOGEY_NUMBERS, is_finishable, plan_route
from .engine import LegResult, VisitResult, play_visit, simulate_leg
from .formats import (
    PRESETS,
    Format,
    best_of_legs,
    first_to_legs,
    set_play,
)
from .match import LiveState, MatchResult, simulate_match
from .player import DartsPlayer
from .simulation import SimulationResult, run_simulation

__version__ = "0.1.0"

__all__ = [
    "DartsPlayer",
    "Format",
    "first_to_legs",
    "best_of_legs",
    "set_play",
    "PRESETS",
    "LiveState",
    "MatchResult",
    "simulate_match",
    "SimulationResult",
    "run_simulation",
    "LegResult",
    "VisitResult",
    "play_visit",
    "simulate_leg",
    "plan_route",
    "is_finishable",
    "BOGEY_NUMBERS",
    "build_player",
    "exponential_moving_average",
    "stage_adjust",
    "fatigue_adjust",
    "__version__",
]
