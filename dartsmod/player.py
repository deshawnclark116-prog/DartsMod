"""Player model.

A player is described by interpretable statistics a data pipeline can scrape and
keep current. The core two are scoring power and finishing, but the model also
captures the effects that genuinely move darts matches:

* ``scoring_average``        -- baseline three-dart scoring (First-9) average.
* ``with_throw_average``     -- scoring average in legs the player *starts* (throw
  advantage is real and player-specific).
* ``against_throw_average``  -- scoring average in legs the opponent starts.
* ``double_prob``            -- per-dart probability of hitting a targeted double.
* ``form_std``               -- how much the player's level swings match-to-match
  (their consistency). Larger => more volatile => more upsets.

Everything the engine needs (treble-hit rates for each throw role, bull rate) is
derived from those. All of the extra fields are optional and default to the
plain single-average behaviour, so simpler callers still work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Expected value of a non-treble dart aimed at treble-20 (see engine miss profile):
# S20 (0.60), S5 (0.25), S1 (0.10), miss (0.05).
_NON_TREBLE_EV = 20 * 0.60 + 5 * 0.25 + 1 * 0.10 + 0 * 0.05  # == 13.35
_TREBLE_VALUE = 60.0


def treble_rate_for_average(scoring_average: float) -> float:
    """Per-dart treble-20 hit rate implied by a three-dart scoring average."""
    per_dart_mean = scoring_average / 3.0
    raw = (per_dart_mean - _NON_TREBLE_EV) / (_TREBLE_VALUE - _NON_TREBLE_EV)
    return min(0.95, max(0.02, raw))


@dataclass
class DartsPlayer:
    """A darts player parameterised for visit-level simulation."""

    name: str
    scoring_average: float = 95.0
    double_prob: float = 0.40
    bull_prob: Optional[float] = None
    single_prob: float = 0.90
    single_on_miss: float = 0.45
    with_throw_average: Optional[float] = None
    against_throw_average: Optional[float] = None
    form_std: float = 0.0

    # Derived, not set by the caller.
    treble_prob: float = field(init=False)
    with_throw_treble: float = field(init=False)
    against_throw_treble: float = field(init=False)

    def __post_init__(self) -> None:
        self.treble_prob = treble_rate_for_average(self.scoring_average)
        wt = self.with_throw_average if self.with_throw_average is not None else self.scoring_average
        at = self.against_throw_average if self.against_throw_average is not None else self.scoring_average
        self.with_throw_treble = treble_rate_for_average(wt)
        self.against_throw_treble = treble_rate_for_average(at)
        if self.bull_prob is None:
            self.bull_prob = round(self.double_prob * 0.75, 4)

    def double_prob_for(self, number: int) -> float:
        """Success probability for the double on ``number`` (25 == bullseye)."""
        return self.bull_prob if number == 25 else self.double_prob

    def treble_for(self, throwing_first: bool, form_delta: float = 0.0) -> float:
        """Treble-hit rate for the role in a leg, shifted by a match form offset.

        ``throwing_first`` selects the with-throw or against-throw average;
        ``form_delta`` is a per-match points swing applied to that average.
        """
        base = self.with_throw_average if throwing_first else self.against_throw_average
        if base is None:
            base = self.scoring_average
        return treble_rate_for_average(base + form_delta)

    @classmethod
    def from_stats(
        cls,
        name: str,
        three_dart_average: float,
        checkout_percentage: float,
        first_nine_average: Optional[float] = None,
    ) -> "DartsPlayer":
        """Build a player from broadcast-style statistics."""
        scoring = first_nine_average if first_nine_average is not None else three_dart_average
        return cls(
            name=name,
            scoring_average=scoring,
            double_prob=max(0.05, min(0.95, checkout_percentage / 100.0)),
        )
