"""Command-line interface for running a match prediction.

Examples
--------
Run a preset matchup::

    python -m dartsmod --p1 "Luke Humphries" --p1-avg 102.5 --p1-co 42 \\
                       --p2 "Michael van Gerwen" --p2-avg 99.8 --p2-co 40 \\
                       --format world_championship_final --sims 20000

Or from a JSON file describing both players and the format.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .formats import PRESETS, best_of_legs
from .player import DartsPlayer
from .simulation import run_simulation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dartsmod",
        description="Predict a darts match with visit-level Monte Carlo simulation.",
    )
    parser.add_argument("--p1", default="Player 1", help="Player 1 name")
    parser.add_argument("--p1-avg", type=float, default=98.0, help="Player 1 scoring average")
    parser.add_argument("--p1-co", type=float, default=40.0, help="Player 1 checkout %%")
    parser.add_argument("--p2", default="Player 2", help="Player 2 name")
    parser.add_argument("--p2-avg", type=float, default=98.0, help="Player 2 scoring average")
    parser.add_argument("--p2-co", type=float, default=40.0, help="Player 2 checkout %%")
    parser.add_argument(
        "--format",
        default="premier_league",
        help="Format preset name, or 'bestofN' (e.g. bestof11)",
    )
    parser.add_argument("--sims", type=int, default=10_000, help="Number of simulations")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--config", type=str, default=None, help="Path to a JSON config file")
    parser.add_argument(
        "--p2-throws-first",
        action="store_true",
        help="Player 2 throws first in the match (default: Player 1)",
    )
    return parser


def _resolve_format(name: str):
    name = name.lower()
    if name in PRESETS:
        return PRESETS[name]
    if name.startswith("bestof"):
        return best_of_legs(int(name[len("bestof"):]))
    raise SystemExit(
        f"Unknown format '{name}'. Choose one of: {', '.join(sorted(PRESETS))}, or bestofN."
    )


def _from_config(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    p1 = DartsPlayer(**cfg["player_1"])
    p2 = DartsPlayer(**cfg["player_2"])
    fmt = _resolve_format(cfg.get("format", "premier_league"))
    return p1, p2, fmt, cfg


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.config:
        p1, p2, fmt, cfg = _from_config(args.config)
        sims = cfg.get("sims", args.sims)
        seed = cfg.get("seed", args.seed)
        first_thrower_p1 = cfg.get("first_thrower_p1", True)
    else:
        p1 = DartsPlayer(name=args.p1, scoring_average=args.p1_avg, double_prob=args.p1_co / 100.0)
        p2 = DartsPlayer(name=args.p2, scoring_average=args.p2_avg, double_prob=args.p2_co / 100.0)
        fmt = _resolve_format(args.format)
        sims = args.sims
        seed = args.seed
        first_thrower_p1 = not args.p2_throws_first

    result = run_simulation(
        p1, p2, fmt, n=sims, first_thrower_p1=first_thrower_p1, seed=seed,
    )
    print(result.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
