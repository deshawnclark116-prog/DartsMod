"""Worked example: Luke Humphries vs Michael van Gerwen.

Run with::

    python examples/humphries_vs_mvg.py
"""

from dartsmod import DartsPlayer, LiveState, run_simulation
from dartsmod.formats import PREMIER_LEAGUE, WORLD_CHAMPIONSHIP_FINAL


def main() -> None:
    humphries = DartsPlayer(name="Luke Humphries", scoring_average=102.5, double_prob=0.42)
    mvg = DartsPlayer(name="Michael van Gerwen", scoring_average=99.8, double_prob=0.40)

    print("Short format (higher variance):")
    result = run_simulation(humphries, mvg, PREMIER_LEAGUE, n=20_000, seed=1)
    print(result.summary())

    print("\nLong set-play format (variance suppressed, edges compound):")
    result = run_simulation(humphries, mvg, WORLD_CHAMPIONSHIP_FINAL, n=20_000, seed=1)
    print(result.summary())

    # In-play: MVG leads the World Championship final 5 sets to 3, but Humphries
    # is throwing first in the current leg with both players on 501.
    print("\nIn-play update (MVG leads 5-3 in sets, Humphries to throw):")
    state = LiveState(
        sets={1: 3, 2: 5},
        legs_in_set={1: 0, 2: 0},
        leg_scores={1: 501, 2: 501},
        p1_to_throw=True,
        set_starter_p1=True,
        leg_starter_p1=True,
    )
    result = run_simulation(
        humphries, mvg, WORLD_CHAMPIONSHIP_FINAL, n=20_000, state=state, seed=1,
    )
    print(f"  Humphries comeback probability: {result.p1_win_prob:.2%}")
    print(f"  Van Gerwen close-out probability: {result.p2_win_prob:.2%}")


if __name__ == "__main__":
    main()
