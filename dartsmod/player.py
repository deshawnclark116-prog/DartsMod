"""Player model.

A player is described by a handful of *interpretable* real-world statistics that
a data pipeline can scrape and update:

* ``scoring_average`` -- the three-dart average a player posts **while scoring**
  (i.e. not on a finish). This is essentially the "First 9" average, which is the
  single most stable indicator of raw scoring power.
* ``double_prob``     -- the probability of hitting a *targeted* double with a
  single dart. Because every attempt on a double succeeds with this probability,
  it is numerically equal to the player's long-run "doubles percentage".

Everything the engine needs (the treble-hit rate that drives scoring visits, the
bull success rate, etc.) is derived from those inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Expected value of a non-treble dart when aiming at the treble-20 bed, using the
# miss profile in :mod:`dartsmod.engine`. Derived once here so the mapping from a
# target scoring average to a treble-hit rate is exact.
#   miss outcomes when aiming T20: S20 (0.60), S5 (0.25), S1 (0.10), miss (0.05)
_NON_TREBLE_EV = 20 * 0.60 + 5 * 0.25 + 1 * 0.10 + 0 * 0.05  # == 13.35
_TREBLE_VALUE = 60.0


@dataclass
class DartsPlayer:
    """A darts player parameterised for visit-level simulation."""

    name: str
    scoring_average: float = 95.0
    double_prob: float = 0.40
    bull_prob: float = None  # type: ignore[assignment]
    single_prob: float = 0.90
    single_on_miss: float = 0.45

    # Derived, not set by the caller.
    treble_prob: float = field(init=False)

    def __post_init__(self) -> None:
        per_dart_mean = self.scoring_average / 3.0
        raw = (per_dart_mean - _NON_TREBLE_EV) / (_TREBLE_VALUE - _NON_TREBLE_EV)
        self.treble_prob = min(0.95, max(0.02, raw))
        if self.bull_prob is None:
            # The bull is a smaller target than a double bed; scale accordingly.
            self.bull_prob = round(self.double_prob * 0.75, 4)

    def double_prob_for(self, number: int) -> float:
        """Success probability for the double on ``number`` (25 == bullseye)."""
        return self.bull_prob if number == 25 else self.double_prob

    @classmethod
    def from_stats(
        cls,
        name: str,
        three_dart_average: float,
        checkout_percentage: float,
        first_nine_average: float = None,  # type: ignore[assignment]
    ) -> "DartsPlayer":
        """Build a player from broadcast-style statistics.

        ``checkout_percentage`` is given as a percentage (e.g. ``40`` for 40%) and
        maps directly onto the per-dart double probability. ``first_nine_average``
        is used as the scoring average when supplied, otherwise the overall
        three-dart average is used as a proxy.
        """
        scoring = first_nine_average if first_nine_average is not None else three_dart_average
        return cls(
            name=name,
            scoring_average=scoring,
            double_prob=max(0.05, min(0.95, checkout_percentage / 100.0)),
        )
