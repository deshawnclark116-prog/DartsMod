"""Backtesting: measure the model's accuracy against completed matches.

Accuracy claims mean nothing without evidence, so this scores the engine's
predictions against real results scraped from DartsOrakel event pages. It also
compares the full model (throw-split + form + recency-quality inputs) against the
plain two-stat model, so we can see whether the extra signal actually helps.

Metrics
-------
* **accuracy**  -- fraction of matches where the model made the actual winner the
  favourite (>50%).
* **Brier**     -- mean squared error of the predicted win probability (lower is
  better; 0.25 == a coin flip).
* **log loss**  -- penalises confident wrong calls (lower is better).
* **calibration** -- do matches predicted at ~70% actually happen ~70% of the time.
"""

from __future__ import annotations

import math
import random
import re
import urllib.request
from datetime import date, timedelta
from typing import Dict, List, Optional

from . import data
from .formats import first_to_legs
from .player import DartsPlayer
from .simulation import run_simulation

_ROW_RE = re.compile(
    r'/player/details/(\d+)/[^"]*">([^<]+)</a>\s*</td>\s*'
    r'<td>\s*(\d+)\s*[Vv]\s*(\d+)\s*</td>\s*'
    r'<td>\s*<a href="[^"]*?/player/details/(\d+)/[^"]*">([^<]+)</a>',
    re.DOTALL,
)


def build_stats_index(months: int = 12, min_matches: int = 8) -> Dict[int, dict]:
    """Build a stats record for *every* player (not just the top roster)."""
    today = date.today()
    dto = today.isoformat()
    dfrom = (today - timedelta(days=int(months * 30.5))).isoformat()
    S = data._fetch_stat_map

    avg = S(data.RANK_KEYS["average"], dfrom, dto, min_matches)
    first9 = S(data.RANK_KEYS["first9"], dfrom, dto, min_matches)
    checkout = S(data.RANK_KEYS["checkout"], dfrom, dto, min_matches)
    wt = S(data.RANK_KEYS["with_throw"], dfrom, dto, min_matches)
    at = S(data.RANK_KEYS["against_throw"], dfrom, dto, min_matches)
    c100 = data._fetch_fraction_map(data.RANK_KEYS["pct_100"], dfrom, dto, min_matches)
    c105 = data._fetch_fraction_map(data.RANK_KEYS["pct_105"], dfrom, dto, min_matches)
    c110 = data._fetch_fraction_map(data.RANK_KEYS["pct_110"], dfrom, dto, min_matches)

    index: Dict[int, dict] = {}
    for key, row in avg.items():
        three = row["stat"]
        scoring = first9.get(key, {}).get("stat") or three
        cov = checkout.get(key, {}).get("stat")
        cov = round(cov, 1) if (cov and data._CHECKOUT_MIN <= cov <= data._CHECKOUT_MAX) else data._DEFAULT_CHECKOUT
        w, a = wt.get(key, {}).get("stat"), at.get(key, {}).get("stat")
        if w and a:
            gap = w - a
            wavg, aavg = scoring + gap / 2, scoring - gap / 2
        else:
            wavg = aavg = scoring
        fstd = data._estimate_form_std(three, [
            (100.0, c100.get(key, {}).get("frac")),
            (105.0, c105.get(key, {}).get("frac")),
            (110.0, c110.get(key, {}).get("frac")),
        ])
        index[key] = {
            "name": row["name"], "scoring_average": scoring, "checkout_percentage": cov,
            "with_throw_average": wavg, "against_throw_average": aavg, "form_std": fstd,
        }
    return index


def parse_event_results(event_id: int) -> List[dict]:
    """Scrape completed matches from a DartsOrakel event page.

    Returns winner/loser keys and the leg score (winner listed first when they
    scored higher).
    """
    url = f"https://dartsorakel.com/events/result/{event_id}"
    request = urllib.request.Request(url, headers=data._HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "ignore")

    matches: List[dict] = []
    for m in _ROW_RE.finditer(html):
        k1, n1, s1, s2, k2, n2 = m.groups()
        s1, s2 = int(s1), int(s2)
        if s1 == s2:
            continue
        if s1 > s2:
            wk, wn, ws, lk, ln, ls = int(k1), n1, s1, int(k2), n2, s2
        else:
            wk, wn, ws, lk, ln, ls = int(k2), n2, s2, int(k1), n1, s1
        matches.append({
            "winner_key": wk, "winner_name": wn.strip(), "w_score": ws,
            "loser_key": lk, "loser_name": ln.strip(), "l_score": ls,
        })
    return matches


def _make_player(key: int, name: str, index: Dict[int, dict], rich: bool) -> DartsPlayer:
    s = index.get(key)
    if not s:
        return DartsPlayer(name=name, scoring_average=95.0, double_prob=0.38)
    kwargs = dict(name=s["name"], scoring_average=s["scoring_average"],
                  double_prob=s["checkout_percentage"] / 100.0)
    if rich:
        kwargs.update(with_throw_average=s["with_throw_average"],
                      against_throw_average=s["against_throw_average"],
                      form_std=s["form_std"])
    return DartsPlayer(**kwargs)


def run_backtest(
    matches: List[dict],
    index: Dict[int, dict],
    n: int = 1500,
    rich: bool = True,
    seed: int = 0,
) -> dict:
    """Score the model on ``matches``. The actual winner is outcome = 1."""
    rng = random.Random(seed)
    probs: List[float] = []
    for i, mm in enumerate(matches):
        winner = _make_player(mm["winner_key"], mm["winner_name"], index, rich)
        loser = _make_player(mm["loser_key"], mm["loser_name"], index, rich)
        fmt = first_to_legs(max(mm["w_score"], 2))  # winner's legs == first-to target
        first_thrower_p1 = rng.random() < 0.5       # throw decided ~50/50 by bull-up
        res = run_simulation(winner, loser, fmt, n=n, first_thrower_p1=first_thrower_p1, seed=seed + i)
        probs.append(res.p1_win_prob)  # p1 == actual winner

    k = len(probs)
    if k == 0:
        return {"n_matches": 0}
    accuracy = sum(1 for p in probs if p > 0.5) / k
    brier = sum((1 - p) ** 2 for p in probs) / k
    logloss = sum(-math.log(max(p, 1e-9)) for p in probs) / k
    # Calibration: bucket predicted prob, compare to actual hit-rate (all outcomes==1).
    bins: Dict[int, List[float]] = {}
    for p in probs:
        bins.setdefault(min(9, int(p * 10)), []).append(p)
    calibration = {f"{b*10}-{b*10+10}%": {"n": len(v), "predicted": round(sum(v)/len(v), 3), "actual": 1.0}
                   for b, v in sorted(bins.items())}
    return {
        "n_matches": k,
        "accuracy": round(accuracy, 3),
        "brier": round(brier, 4),
        "logloss": round(logloss, 4),
        "mean_winner_prob": round(sum(probs) / k, 3),
        "calibration": calibration,
    }
