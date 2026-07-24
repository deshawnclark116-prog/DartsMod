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


@dataclass(frozen=True)
class Format:
    """A match format.

    ``legs_to_win_set`` legs win a set; ``sets_to_win`` sets win the match.
    For a pure leg-play format, ``sets_to_win`` is 1.
    """

    name: str
    legs_to_win_set: int
    sets_to_win: int = 1

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
WORLD_MATCHPLAY_EARLY = Format(name="World Matchplay R1 (first to 10 legs)", legs_to_win_set=10)
UK_OPEN_FINAL = Format(name="UK Open final (first to 11 legs)", legs_to_win_set=11)
WORLD_CHAMPIONSHIP_R1 = set_play(legs_per_set=3, sets_to_win=2)
WORLD_CHAMPIONSHIP_SEMI = set_play(legs_per_set=3, sets_to_win=6)
WORLD_CHAMPIONSHIP_FINAL = set_play(legs_per_set=3, sets_to_win=7)

PRESETS = {
    "premier_league": PREMIER_LEAGUE,
    "players_championship": PLAYERS_CHAMPIONSHIP,
    "world_matchplay_r1": WORLD_MATCHPLAY_EARLY,
    "uk_open_final": UK_OPEN_FINAL,
    "world_championship_r1": WORLD_CHAMPIONSHIP_R1,
    "world_championship_semi": WORLD_CHAMPIONSHIP_SEMI,
    "world_championship_final": WORLD_CHAMPIONSHIP_FINAL,
}
