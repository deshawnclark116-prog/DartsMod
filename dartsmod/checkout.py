"""Checkout-route planning for 501 darts.

The heart of a faithful darts model is *how* a leg is finished. A player who is
"on a finish" (a remaining score that can be closed out) does not roll a single
opaque "checkout probability" die — they throw a sequence of darts along a
standard route that ends on a double (or the bullseye). This module computes the
canonical route for any finishable score so the simulation engine can throw it
dart-by-dart.

Conventions
-----------
A dart target is represented as a 3-tuple ``(kind, number, value)``:

* ``kind`` is one of ``'S'`` (single), ``'D'`` (double), ``'T'`` (treble).
* ``number`` is the board number (1..20, or 25 for the bull).
* ``value`` is the points scored (e.g. ``('T', 20, 60)``, ``('D', 25, 50)`` for
  the bullseye).

A *route* is a list of targets whose values sum to the score, whose final target
is always a double (or the bull, modelled as ``('D', 25, 50)``), and whose length
is at most the number of darts available.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Tuple

Target = Tuple[str, int, int]
Route = List[Target]

# Scores from which no 3-dart checkout exists (you cannot leave yourself a double).
BOGEY_NUMBERS = frozenset({169, 168, 166, 165, 163, 162, 159})

# The maximum score that can ever be checked out with three darts.
MAX_CHECKOUT = 170

# --- Board target catalogues -------------------------------------------------

_SINGLES: List[Target] = [("S", n, n) for n in list(range(1, 21)) + [25]]
_TREBLES: List[Target] = [("T", n, 3 * n) for n in range(1, 21)]
_DOUBLES: List[Target] = [("D", n, 2 * n) for n in range(1, 21)] + [("D", 25, 50)]

# Non-final ("setup") darts: any single or treble.
_SETUP_TARGETS: List[Target] = sorted(_SINGLES + _TREBLES, key=lambda t: -t[2])

# Map a score to the double that finishes it in one dart, if any.
_DOUBLE_BY_VALUE = {v: (k, n, v) for (k, n, v) in _DOUBLES}

# Preference ordering for the *finishing* double. Pros steer towards doubles that
# leave a clean follow-up if missed (D20, D16, D8 ...). Lower rank == preferred.
_DOUBLE_PREFERENCE = {
    20: 0, 16: 1, 8: 2, 4: 3, 2: 4, 10: 5, 12: 6, 18: 7,
    14: 8, 6: 9, 40: 10, 25: 11,  # 40 == D20 already; 25 == bull, least preferred
}


def _double_rank(number: int) -> int:
    return _DOUBLE_PREFERENCE.get(number, 50)


def is_finishable(score: int, darts_left: int = 3) -> bool:
    """Return ``True`` if ``score`` can be checked out with ``darts_left`` darts."""
    return plan_route(score, darts_left) is not None


@lru_cache(maxsize=None)
def plan_route(score: int, darts_left: int = 3) -> Optional[Route]:
    """Return the preferred checkout route for ``score`` within ``darts_left`` darts.

    Returns ``None`` when the score cannot be finished in the darts available
    (too high, a bogey number, or simply not enough darts). The route minimises
    the number of darts, then prefers a favourable finishing double, then prefers
    bigger setup darts (fewer, cleaner visits).
    """
    if score < 2 or score > MAX_CHECKOUT or darts_left < 1:
        return None

    best: Optional[Route] = None
    best_key: Optional[Tuple] = None
    for length in range(1, darts_left + 1):
        for route in _routes_of_length(score, length):
            key = _route_key(route)
            if best_key is None or key < best_key:
                best, best_key = route, key
        if best is not None:
            # Shortest route wins outright; no need to look at longer ones.
            break
    return best


def _route_key(route: Route) -> Tuple:
    """Sort key: prefer a good finishing double, then bigger setup darts."""
    final = route[-1]
    setup_value = sum(t[2] for t in route[:-1])
    return (_double_rank(final[1]), -setup_value)


def _routes_of_length(score: int, length: int) -> List[Route]:
    """All routes of exactly ``length`` darts finishing ``score`` on a double."""
    if length == 1:
        target = _DOUBLE_BY_VALUE.get(score)
        return [[target]] if target else []

    routes: List[Route] = []
    for setup in _SETUP_TARGETS:
        remaining = score - setup[2]
        if remaining < 2:
            continue
        for tail in _routes_of_length(remaining, length - 1):
            routes.append([setup] + tail)
    return routes
