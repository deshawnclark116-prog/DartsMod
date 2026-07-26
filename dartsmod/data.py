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
import threading
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
        "with_throw_average": _coerce_float(player.get("with_throw_average"), scoring),
        "against_throw_average": _coerce_float(player.get("against_throw_average"), scoring),
        "form_std": _coerce_float(player.get("form_std"), 6.0),
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


# Additional stat feeds used by the richer model.
RANK_KEYS.update({
    "with_throw": 1031,      # three-dart average in legs the player starts
    "against_throw": 1032,   # three-dart average in legs the opponent starts
    "pct_100": 10006,        # matches with a 100+ average (as "count/total")
    "pct_105": 10005,
    "pct_110": 10012,
})


def _fetch_fraction_map(rank_key: int, date_from: str, date_to: str, min_matches: int) -> Dict[int, dict]:
    """Return ``{player_key: {frac, total}}`` for a "count/total" stat."""
    payload = _fetch_json(rank_key, date_from, date_to, min_matches)
    result: Dict[int, dict] = {}
    for row in payload.get("data", []):
        key = row.get("player_key")
        raw = str(row.get("stat") or "")
        if key is None or "/" not in raw:
            continue
        num, _, den = raw.partition("/")
        try:
            n, d = float(num), float(den)
        except ValueError:
            continue
        if d > 0:
            result[key] = {"frac": n / d, "total": d}
    return result


def _inv_norm(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's approximation)."""
    import math
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def _estimate_form_std(mean: float, buckets: List[tuple]) -> float:
    """Estimate a player's match-to-match scoring std from consistency buckets.

    Each bucket is ``(threshold, fraction_of_matches_at_or_above)``. Fitting a
    normal N(mean, std) to each gives std = (threshold - mean) / z, z = invΦ(1-p);
    we average the valid estimates and clamp to a sane band.
    """
    estimates = []
    for threshold, frac in buckets:
        if frac is None or not (0.02 < frac < 0.98):
            continue
        z = _inv_norm(1 - frac)
        if abs(z) < 0.25:
            continue
        std = (threshold - mean) / z
        if std > 0:
            estimates.append(std)
    if not estimates:
        return 6.0
    return round(min(12.0, max(3.0, sum(estimates) / len(estimates))), 1)


def _blend(long_map, recent_map, key, weight_recent=0.6):
    """Recency-weighted blend of a stat, falling back to whichever exists."""
    lv = long_map.get(key, {}).get("stat")
    rv = recent_map.get(key, {}).get("stat")
    if lv is not None and rv is not None:
        return weight_recent * rv + (1 - weight_recent) * lv
    return rv if rv is not None else lv


def build_player_database(
    top_n: int = 150,
    months: int = 12,
    recent_days: int = 90,
    min_matches: int = 20,
    recent_min_matches: int = 5,
) -> List[dict]:
    """Build a roster of current professionals with the full model inputs.

    Combines, per player (joined by key):
    * scoring average (First-9), three-dart average, checkout %
    * with-throw / against-throw scoring (applied as a split around First-9)
    * a match-to-match form std fitted from the 100+/105+/110+ consistency buckets
    * recency weighting: recent form blended over the trailing 12 months

    Raises on network failure -- callers should use :func:`get_players`.
    """
    today = date.today()
    date_to = today.isoformat()
    long_from = (today - timedelta(days=int(months * 30.5))).isoformat()
    recent_from = (today - timedelta(days=recent_days)).isoformat()

    def stat(rk, dfrom, mm):
        return _fetch_stat_map(RANK_KEYS[rk], dfrom, date_to, mm)

    # Long window (the roster + stable signals).
    avg_l = stat("average", long_from, min_matches)
    first9_l = stat("first9", long_from, min_matches)
    checkout_l = stat("checkout", long_from, min_matches)
    wt_l = stat("with_throw", long_from, min_matches)
    at_l = stat("against_throw", long_from, min_matches)
    # Recent window (form).
    avg_r = stat("average", recent_from, recent_min_matches)
    first9_r = stat("first9", recent_from, recent_min_matches)
    checkout_r = stat("checkout", recent_from, recent_min_matches)
    wt_r = stat("with_throw", recent_from, recent_min_matches)
    at_r = stat("against_throw", recent_from, recent_min_matches)
    # Consistency buckets (variance).
    c100 = _fetch_fraction_map(RANK_KEYS["pct_100"], long_from, date_to, min_matches)
    c105 = _fetch_fraction_map(RANK_KEYS["pct_105"], long_from, date_to, min_matches)
    c110 = _fetch_fraction_map(RANK_KEYS["pct_110"], long_from, date_to, min_matches)

    ranked = sorted(avg_l.items(), key=lambda kv: kv[1]["stat"], reverse=True)[:top_n]

    players: List[dict] = []
    for key, avg_row in ranked:
        three_dart = _blend(avg_l, avg_r, key) or avg_row["stat"]
        scoring = _blend(first9_l, first9_r, key) or three_dart
        checkout_raw = _blend(checkout_l, checkout_r, key)
        checkout_pct = round(checkout_raw, 1) if (checkout_raw and _CHECKOUT_MIN <= checkout_raw <= _CHECKOUT_MAX) else _DEFAULT_CHECKOUT

        # Throw split: apply half the with/against gap around the scoring average.
        wt = _blend(wt_l, wt_r, key)
        at = _blend(at_l, at_r, key)
        if wt is not None and at is not None:
            gap = wt - at
            with_avg = round(scoring + gap / 2, 1)
            against_avg = round(scoring - gap / 2, 1)
        else:
            with_avg = against_avg = round(scoring, 1)

        form_std = _estimate_form_std(three_dart, [
            (100.0, c100.get(key, {}).get("frac")),
            (105.0, c105.get(key, {}).get("frac")),
            (110.0, c110.get(key, {}).get("frac")),
        ])

        players.append({
            "key": key,
            "name": avg_row["name"],
            "country": avg_row["country"],
            "scoring_average": round(scoring, 1),
            "three_dart_average": round(three_dart, 1),
            "checkout_percentage": checkout_pct,
            "with_throw_average": with_avg,
            "against_throw_average": against_avg,
            "form_std": form_std,
        })
    return players


_refreshing = {"flag": False}


def _do_build() -> List[dict]:
    players = build_player_database()
    return [_normalize(p) for p in players] if players else []


def _background_refresh() -> None:
    """Kick off a roster rebuild in a daemon thread (at most one at a time)."""
    if _refreshing["flag"]:
        return
    _refreshing["flag"] = True

    def run() -> None:
        try:
            built = _do_build()
            if built:
                _cache["players"] = built
                _cache["ts"] = time.time()
        except Exception:
            pass
        finally:
            _refreshing["flag"] = False

    threading.Thread(target=run, daemon=True).start()


def get_players(force_refresh: bool = False) -> List[dict]:
    """Return the cached player roster; refresh in the background when stale.

    Never blocks a caller on the (~30s, 13-request) rebuild: a fresh cache is
    returned immediately, a stale/empty cache triggers a background refresh and
    serves the current cache (or the built-in fallback) meanwhile. Never raises.
    ``force_refresh`` rebuilds synchronously (used by tests / explicit warmups).
    """
    now = time.time()
    cached = _cache.get("players")

    if force_refresh:
        try:
            built = _do_build()
            if built:
                _cache["players"] = built
                _cache["ts"] = now
                return built
        except Exception:
            pass
        return cached if cached else [_normalize(p) for p in _FALLBACK_PLAYERS]  # type: ignore[return-value]

    if cached and (now - float(_cache["ts"])) < _CACHE_TTL_SECONDS:
        return cached  # type: ignore[return-value]

    _background_refresh()
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


# --- Format inference --------------------------------------------------------

def infer_match_format(event_title: str, round_name: str) -> dict:
    """Best-effort match format from the event and round.

    The upcoming feed carries no format, so we map the major PDC events and their
    rounds to the real leg/set structure. Returns ``{label, legs_to_win_set,
    sets_to_win}``; leg-play formats have ``sets_to_win == 1``. Unknown events
    default to a first-to-6 leg match. Heuristic and user-overridable.
    """
    e = (event_title or "").lower()
    r = (round_name or "").lower()

    def leg(n: int, win_by_two: bool = False) -> dict:
        return {"label": f"First to {n} legs", "legs_to_win_set": n, "sets_to_win": 1,
                "win_by_two": win_by_two, "sudden_death_at": (n + 2) if win_by_two else None}

    def setp(legs: int, sets: int, win_by_two: bool = False) -> dict:
        return {"label": f"First to {sets} sets (first to {legs} legs)",
                "legs_to_win_set": legs, "sets_to_win": sets,
                "win_by_two": win_by_two, "sudden_death_at": 5 if win_by_two else None}

    is_final = "final" in r and "semi" not in r and "quarter" not in r
    is_semi = "semi" in r
    is_quarter = "quarter" in r
    women = "women" in e or "ladies" in e

    # World Championship (PDC) -- set play, deciding set win-by-two (5-5 sudden death).
    if "world championship" in e and not women:
        if is_final: return setp(3, 7, win_by_two=True)
        if is_semi: return setp(3, 6, win_by_two=True)
        if is_quarter: return setp(3, 5, win_by_two=True)
        if "round 4" in r or "fourth" in r: return setp(3, 5, win_by_two=True)
        if "round 3" in r or "third" in r: return setp(3, 4, win_by_two=True)
        if "round 2" in r or "second" in r: return setp(3, 4, win_by_two=True)
        return setp(3, 3, win_by_two=True)

    # World Grand Prix -- set play, double-start.
    if "grand prix" in e:
        if is_final: return setp(3, 5, win_by_two=True)
        if is_semi or is_quarter: return setp(3, 3, win_by_two=True)
        if "round 2" in r or "second" in r: return setp(3, 3, win_by_two=True)
        return setp(2, 2, win_by_two=True)

    # World Matchplay -- leg play by round, win-by-two tie-break.
    if "matchplay" in e and not women:
        if is_final: return leg(18, win_by_two=True)
        if is_semi: return leg(17, win_by_two=True)
        if is_quarter: return leg(16, win_by_two=True)
        if "round 2" in r or "second" in r or "16" in r: return leg(11, win_by_two=True)
        return leg(10, win_by_two=True)
    if "matchplay" in e and women:
        return leg(8, win_by_two=True) if is_final else leg(6, win_by_two=True)

    # Grand Slam of Darts -- leg play.
    if "grand slam" in e:
        if is_final: return leg(16)
        if is_semi or is_quarter: return leg(16)
        if "group" in r: return leg(5)
        return leg(10)

    # UK Open -- leg play.
    if "uk open" in e:
        if is_final or is_semi: return leg(11)
        if is_quarter: return leg(10)
        return leg(9)

    # Premier League.
    if "premier league" in e:
        if is_final: return leg(11)
        if is_semi: return leg(10)
        return leg(6)

    # Pro Tour / European Tour / Players Championship / anything else.
    return leg(6)


# --- Upcoming fixtures -------------------------------------------------------

_UPCOMING_URL = "https://dartsorakel.com/api/match/upcoming-matches-datatable"
_UPCOMING_TTL_SECONDS = 3600
_upcoming_cache: Dict[str, object] = {"matches": None, "ts": 0.0}


def _fetch_upcoming() -> list:
    """Fetch the raw upcoming-matches rows from DartsOrakel (with retries)."""
    params = urllib.parse.urlencode({"draw": 1, "start": 0, "length": 200})
    url = f"{_UPCOMING_URL}?{params}"
    last_err: Optional[Exception] = None
    for _ in range(3):
        try:
            request = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8")).get("data", [])
        except Exception as err:  # noqa: BLE001
            last_err = err
            time.sleep(1.5)
    raise last_err  # type: ignore[misc]


def get_upcoming_matches(force_refresh: bool = False) -> List[dict]:
    """Return upcoming pro matches (both players, event, round, date).

    Cached for an hour; never raises (serves cache, then an empty list). Player
    keys are DartsOrakel keys, so they join directly onto :func:`get_players`.
    """
    now = time.time()
    cached = _upcoming_cache.get("matches")
    if not force_refresh and cached is not None and (now - float(_upcoming_cache["ts"])) < _UPCOMING_TTL_SECONDS:
        return cached  # type: ignore[return-value]

    try:
        matches: List[dict] = []
        for row in _fetch_upcoming():
            p1k, p2k = row.get("first_player_key"), row.get("second_player_key")
            if p1k is None or p2k is None:
                continue
            matches.append({
                "event": str(row.get("event_title") or row.get("event_name") or "").strip(),
                "round": str(row.get("round_name") or "").strip(),
                "date": str(row.get("match_date") or ""),
                "p1_key": int(p1k),
                "p1_name": str(row.get("first_player_name") or "").strip(),
                "p2_key": int(p2k),
                "p2_name": str(row.get("second_player_name") or "").strip(),
            })
        _upcoming_cache["matches"] = matches
        _upcoming_cache["ts"] = now
        return matches
    except Exception:
        if cached is not None:
            return cached  # type: ignore[return-value]
        return []
