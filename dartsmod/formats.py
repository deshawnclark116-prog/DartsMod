"""Match format definitions.

Darts is played in two broad structures:

* **Leg play** -- first to *N* legs (e.g. a Premier League night is first to 6).
* **Set play** -- a set is first to *L* legs, and the match is first to *S* sets
  (e.g. a World Championship final is first to 7 sets, each first to 3 legs).

Both are expressed by the same :class:`Format`: leg-play is simply set-play with a
single set to win.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Format:
    """A match format.

    ``legs_to_win_set`` legs win a set; ``sets_to_win`` sets win the match.
    For a pure leg-play format, ``sets_to_win`` is 1.

    Tie-break rules (applied to the *decider* -- the deciding set in set-play, or
    the whole match in leg-play):

    * ``win_by_two`` -- the decider must be won by two clear legs.
    * ``sudden_death_at`` -- legs-each in the decider at which a single sudden-death
      leg settles it (e.g. World Championship deciding set: 5, so 5-5 -> one leg;
      World Matchplay first-to-10: 12, so 12-12 -> one leg).
    """

    name: str
    legs_to_win_set: int
    sets_to_win: int = 1
    win_by_two: bool = False
    sudden_death_at: Optional[int] = None

    @property
    def is_set_play(self) -> bool:
        return self.sets_to_win > 1

    @property
    def max_legs_per_set(self) -> int:
        return 2 * self.legs_to_win_set - 1

    @property
    def max_sets(self) -> int:
        return 2 * self.sets_to_win - 1


def first_to_legs(n: int) -> Format:
    """A leg-play race to ``n`` legs (best of ``2n - 1``)."""
    return Format(name=f"First to {n} legs", legs_to_win_set=n, sets_to_win=1)


def best_of_legs(n: int) -> Format:
    """A best-of-``n``-legs match (``n`` should be odd)."""
    return Format(name=f"Best of {n} legs", legs_to_win_set=(n + 1) // 2, sets_to_win=1)


def set_play(legs_per_set: int, sets_to_win: int) -> Format:
    """A set-play match: first to ``sets_to_win`` sets, each first to ``legs_per_set``."""
    return Format(
        name=f"First to {sets_to_win} sets (first to {legs_per_set} legs)",
        legs_to_win_set=legs_per_set,
        sets_to_win=sets_to_win,
    )


# --- Common real-world presets ----------------------------------------------

PREMIER_LEAGUE = Format(name="Premier League (first to 6 legs)", legs_to_win_set=6)
PLAYERS_CHAMPIONSHIP = Format(name="Players Championship (first to 6 legs)", legs_to_win_set=6)
WORLD_MATCHPLAY_EARLY = Format(name="World Matchplay R1 (first to 10 legs)", legs_to_win_set=10,
                               win_by_two=True, sudden_death_at=12)
UK_OPEN_FINAL = Format(name="UK Open final (first to 11 legs)", legs_to_win_set=11)
# World Championship: deciding set is win-by-two, sudden death at 5-5.
WORLD_CHAMPIONSHIP_R1 = Format(name="First to 3 sets (first to 3 legs)", legs_to_win_set=3,
                               sets_to_win=3, win_by_two=True, sudden_death_at=5)
WORLD_CHAMPIONSHIP_SEMI = Format(name="First to 6 sets (first to 3 legs)", legs_to_win_set=3,
                                 sets_to_win=6, win_by_two=True, sudden_death_at=5)
WORLD_CHAMPIONSHIP_FINAL = Format(name="First to 7 sets (first to 3 legs)", legs_to_win_set=3,
                                  sets_to_win=7, win_by_two=True, sudden_death_at=5)

PRESETS = {
    "premier_league": PREMIER_LEAGUE,
    "players_championship": PLAYERS_CHAMPIONSHIP,
    "world_matchplay_r1": WORLD_MATCHPLAY_EARLY,
    "uk_open_final": UK_OPEN_FINAL,
    "world_championship_r1": WORLD_CHAMPIONSHIP_R1,
    "world_championship_semi": WORLD_CHAMPIONSHIP_SEMI,
    "world_championship_final": WORLD_CHAMPIONSHIP_FINAL,
}


def resolve_format(name: str) -> Format:
    """Resolve a format from a preset name, ``bestofN`` or ``firsttoN``.

    Raises ``KeyError`` if the name is not recognised.
    """
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    if key in PRESETS:
        return PRESETS[key]
    if key.startswith("bestof"):
        return best_of_legs(int(key[len("bestof"):]))
    if key.startswith("firstto"):
        return first_to_legs(int(key[len("firstto"):]))
    raise KeyError(name)
