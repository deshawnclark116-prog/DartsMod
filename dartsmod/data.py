"""Live player-stats pipeline.

The engine needs each player's scoring average and double probability. Rather than
make the user type those, this module pulls **current** professional stats from
DartsOrakel's public stats feed and turns them into ready-to-simulate players.

Source
------
DartsOrakel exposes the data behind its Player Stats table as JSON at
``https://dartsorakel.com/api/stats/player``. The ``rankKey`` query parameter
selects which statistic is returned:

* ``25``   -> three-dart average
* ``1029`` -> First-9 average (our scoring average)
* ``1053`` -> checkout percentage (our double probability)

We rank players by three-dart average over a trailing window (recent form), then
join First-9 and checkout onto that roster by ``player_key``. Results are cached
in memory so we hit the source at most once every few hours.

This is a best-effort scrape of a third-party site: if it is unreachable we fall
back to the last good cache, then to a small built-in roster, so the API never
hard-fails.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Dict, List, Optional

_BASE_URL = "https://dartsorakel.com/api/stats/player"

RANK_KEYS = {
    "average": 25,
    "first9": 1029,
    "checkout": 1053,
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

# Plausible bounds used to reject tiny-sample outliers from the checkout feed.
_CHECKOUT_MIN, _CHECKOUT_MAX = 15.0, 55.0
_DEFAULT_CHECKOUT = 38.0

_CACHE_TTL_SECONDS = 6 * 3600
_cache: Dict[str, object] = {"players": None, "ts": 0.0}

# Minimal offline roster so the product still works if the source is unreachable
# and nothing has been cached yet. Stats are representative recent values.
_FALLBACK_PLAYERS = [
    {"key": 5403, "name": "Luke Littler", "country": "ENG", "scoring_average": 105.0, "three_dart_average": 101.0, "checkout_percentage": 43.0},
    {"key": 34, "name": "Luke Humphries", "country": "ENG", "scoring_average": 103.5, "three_dart_average": 99.5, "checkout_percentage": 43.0},
    {"key": 1, "name": "Michael van Gerwen", "country": "NED", "scoring_average": 101.0, "three_dart_average": 97.0, "checkout_percentage": 40.0},
    {"key": 2, "name": "Gerwyn Price", "country": "WAL", "scoring_average": 99.5, "three_dart_average": 96.5, "checkout_percentage": 39.0},
    {"key": 3, "name": "Gary Anderson", "country": "SCO", "scoring_average": 99.0, "three_dart_average": 96.0, "checkout_percentage": 38.0},
    {"key": 4, "name": "Rob Cross", "country": "ENG", "scoring_average": 98.5, "three_dart_average": 95.5, "checkout_percentage": 39.0},
    {"key": 5, "name": "Michael Smith", "country": "ENG", "scoring_average": 98.0, "three_dart_average": 95.0, "checkout_percentage": 37.0},
    {"key": 6, "name": "Nathan Aspinall", "country": "ENG", "scoring_average": 97.5, "three_dart_average": 94.5, "checkout_percentage": 40.0},
    {"key": 7, "name": "Stephen Bunting", "country": "ENG", "scoring_average": 97.5, "three_dart_average": 94.5, "checkout_percentage": 41.0},
    {"key": 8, "name": "Chris Dobey", "country": "ENG", "scoring_average": 97.0, "three_dart_average": 94.0, "checkout_percentage": 40.0},
    {"key": 9, "name": "Jonny Clayton", "country": "WAL", "scoring_average": 97.0, "three_dart_average": 94.0, "checkout_percentage": 39.0},
    {"key": 10, "name": "Danny Noppert", "country": "NED", "scoring_average": 96.5, "three_dart_average": 93.5, "checkout_percentage": 40.0},
]


def _parse_stat(value: object) -> Optional[float]:
    """Parse a stat cell such as ``"101.47"`` or ``"43.5%"`` into a float."""
    if value is None:
        return None
    text = str(value).replace("%", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _fetch_json(rank_key: int, date_from: str, date_to: str, min_matches: int) -> dict:
    """Fetch one statistic table from DartsOrakel and return the parsed JSON.

    Retries a couple of times because the upstream (behind Cloudflare) can be
    briefly flaky from datacenter IPs.
    """
    params = urllib.parse.urlencode({
        "rankKey": rank_key,
        "dateFrom": date_from,
        "dateTo": date_to,
        "minMatches": min_matches,
    })
    url = f"{_BASE_URL}?{params}"
    last_err: Optional[Exception] = None
    for _ in range(3):
        try:
            request = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as err:  # noqa: BLE001 - retried, then re-raised
            last_err = err
            time.sleep(1.5)
    raise last_err  # type: ignore[misc]


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _normalize(player: dict) -> dict:
    """Return a record with the full field set and correct types.

    Hardened against *null* or malformed values (not just missing keys): the live
    feed occasionally has a player with a null country or a non-numeric stat, and
    a single bad record must not 500 the whole ``/players`` response.
    """
    scoring = _coerce_float(player.get("scoring_average"), 95.0)
    try:
        key = int(player.get("key") or 0)
    except (TypeError, ValueError):
        key = 0
    name = str(player.get("name") or "Unknown").strip() or "Unknown"
    return {
        "key": key,
        "name": name,
        "country": str(player.get("country") or ""),
        "scoring_average": scoring,
        "three_dart_average": _coerce_float(player.get("three_dart_average"), scoring),
        "checkout_percentage": _coerce_float(player.get("checkout_percentage"), _DEFAULT_CHECKOUT),
    }


def _fetch_stat_map(rank_key: int, date_from: str, date_to: str, min_matches: int) -> Dict[int, dict]:
    """Return ``{player_key: {name, country, stat}}`` for one statistic."""
    payload = _fetch_json(rank_key, date_from, date_to, min_matches)
    result: Dict[int, dict] = {}
    for row in payload.get("data", []):
        key = row.get("player_key")
        stat = _parse_stat(row.get("stat"))
        if key is None or stat is None:
            continue
        result[key] = {
            "name": (row.get("player_name") or "").strip(),
            "country": row.get("country") or "",
            "stat": stat,
        }
    return result


def build_player_database(
    top_n: int = 150,
    months: int = 12,
    min_matches: int = 20,
) -> List[dict]:
    """Build a roster of current professionals with simulation-ready stats.

    Players are ranked by recent three-dart average; First-9 average (used as the
    scoring average) and checkout percentage (used as the double probability) are
    joined on by player key. Raises on network failure -- callers should use
    :func:`get_players`, which handles caching and fallback.
    """
    today = date.today()
    date_to = today.isoformat()
    date_from = (today - timedelta(days=int(months * 30.5))).isoformat()

    averages = _fetch_stat_map(RANK_KEYS["average"], date_from, date_to, min_matches)
    first9 = _fetch_stat_map(RANK_KEYS["first9"], date_from, date_to, min_matches)
    checkout = _fetch_stat_map(RANK_KEYS["checkout"], date_from, date_to, min_matches)

    # Rank by three-dart average, highest first.
    ranked = sorted(averages.items(), key=lambda kv: kv[1]["stat"], reverse=True)[:top_n]

    players: List[dict] = []
    for key, avg_row in ranked:
        three_dart = avg_row["stat"]
        scoring = first9.get(key, {}).get("stat") or three_dart
        checkout_raw = checkout.get(key, {}).get("stat")
        if checkout_raw is not None and _CHECKOUT_MIN <= checkout_raw <= _CHECKOUT_MAX:
            checkout_pct = round(checkout_raw, 1)
        else:
            checkout_pct = _DEFAULT_CHECKOUT
        players.append({
            "key": key,
            "name": avg_row["name"],
            "country": avg_row["country"],
            "scoring_average": round(scoring, 1),
            "three_dart_average": round(three_dart, 1),
            "checkout_percentage": checkout_pct,
        })
    return players


def get_players(force_refresh: bool = False) -> List[dict]:
    """Return the cached player roster, refreshing from the source when stale.

    Never raises: on failure it serves the last good cache, or the built-in
    fallback roster.
    """
    now = time.time()
    cached = _cache.get("players")
    if not force_refresh and cached and (now - float(_cache["ts"])) < _CACHE_TTL_SECONDS:
        return cached  # type: ignore[return-value]

    try:
        players = build_player_database()
        if players:
            players = [_normalize(p) for p in players]
            _cache["players"] = players
            _cache["ts"] = now
            return players
    except Exception:
        pass  # fall through to cache / fallback

    if cached:
        return cached  # type: ignore[return-value]
    return [_normalize(p) for p in _FALLBACK_PLAYERS]


def find_players(query: str = "", limit: int = 50) -> List[dict]:
    """Search the roster by name (case-insensitive substring)."""
    players = get_players()
    if query:
        needle = query.lower()
        players = [p for p in players if needle in p["name"].lower()]
    return players[:limit]
