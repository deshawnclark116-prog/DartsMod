# DartsMod

A world-class darts match prediction engine built on **visit-level Monte Carlo
simulation**.

Rather than training a black-box classifier on historical match wins — which
falls apart the moment the format changes from a best-of-11-leg night to a
best-of-13-set World Championship final — DartsMod simulates the *physical
reality* of a darts match, one three-dart visit (and one dart) at a time. Every
throw of a match is played out thousands of times, so you don't just get a winner
probability: you get the full distribution of scorelines, total legs, 180 counts,
checkout percentages and player averages.

## Why this approach

Format changes constantly in professional darts, and variance scales with format
length. A model that only outputs "Player A wins 60%" cannot tell you that the
same edge is worth 63% over a Premier League night but 72% over a set-play final.
Because DartsMod simulates the game itself, format is just a parameter and the
right variance falls out automatically.

The engine models the three phases of a leg exactly as they play out on the oche:

1. **Scoring** — while far from a finish, the player throws at the treble-20 bed.
   The treble-hit rate is derived from the player's scoring (First-9-style)
   average, so the emergent three-dart average matches the input.
2. **Setup & finishing** — once a checkout is on, the engine plans the *standard
   checkout route* for the remaining score (e.g. `170 → T20, T20, Bull`) and
   throws it dart-by-dart, with the finishing double landing at the player's
   per-dart double probability. Bogey numbers (169, 168, 166, …) and busts are
   handled correctly.
3. **Advantage of throw** — the player who starts a leg has a real statistical
   edge, and the simulation tracks exactly whose throw it is in every leg and set.

## Install

```bash
pip install -e .          # editable install
pip install -e ".[dev]"   # with pytest for the test suite
```

Zero runtime dependencies — pure Python standard library.

## Quick start

```python
from dartsmod import DartsPlayer, run_simulation
from dartsmod.formats import PREMIER_LEAGUE, WORLD_CHAMPIONSHIP_FINAL

humphries = DartsPlayer("Luke Humphries", scoring_average=102.5, double_prob=0.42)
mvg       = DartsPlayer("Michael van Gerwen", scoring_average=99.8, double_prob=0.40)

result = run_simulation(humphries, mvg, PREMIER_LEAGUE, n=20_000, seed=1)
print(result.summary())

print("Set-play win prob:", run_simulation(
    humphries, mvg, WORLD_CHAMPIONSHIP_FINAL, n=20_000, seed=1).p1_win_prob)
```

### Command line

```bash
python -m dartsmod \
  --p1 "Luke Humphries" --p1-avg 102.5 --p1-co 42 \
  --p2 "Michael van Gerwen" --p2-avg 99.8 --p2-co 40 \
  --format world_championship_final --sims 20000 --seed 1
```

Format presets: `premier_league`, `players_championship`, `world_matchplay_r1`,
`uk_open_final`, `world_championship_r1`, `world_championship_semi`,
`world_championship_final`, or `bestofN` (e.g. `bestof11`).

## Player inputs

A player is described by interpretable, scrapeable statistics:

| Field             | Meaning                                                        | Typical pro |
|-------------------|---------------------------------------------------------------|-------------|
| `scoring_average` | three-dart average *while scoring* (≈ First 9 average)         | 95 – 105    |
| `double_prob`     | per-dart probability of hitting a targeted double (= doubles %)| 0.35 – 0.45 |

Everything else (treble-hit rate, bull rate) is derived. You can also build a
player straight from broadcast stats:

```python
DartsPlayer.from_stats("Player", three_dart_average=99.5, checkout_percentage=41)
```

## Turning history into world-class inputs (`dartsmod.adjustments`)

Lifetime averages are a trap. The `adjustments` module converts recent history
into engine inputs the way sharp modellers do:

- **Recency decay** — `exponential_moving_average(values, half_life=5)` weights the
  last handful of matches far more heavily than the rest of the season.
- **Stage vs floor** — `stage_adjust(player, on_stage=True, ...)` applies a
  penalty for players who historically fade under the lights of a televised major.
- **Travel / fatigue** — `fatigue_adjust(player, scoring_penalty=1.5)` docks a
  heavily-travelled player.
- `build_player(...)` blends all of the above in one call.

## Live / in-play prediction

Feed the engine the current match state and it re-simulates from exactly there:

```python
from dartsmod import LiveState, run_simulation
from dartsmod.formats import WORLD_CHAMPIONSHIP_FINAL

state = LiveState(sets={1: 3, 2: 5}, leg_scores={1: 501, 2: 501}, p1_to_throw=True)
result = run_simulation(humphries, mvg, WORLD_CHAMPIONSHIP_FINAL, n=20_000, state=state)
print("Comeback probability:", result.p1_win_prob)
```

## What you get back (`SimulationResult`)

- `p1_win_prob` / `p2_win_prob` and `fair_odds()`
- `most_likely_scorelines(k)` — correct-score market
- `over_under(line)` and `expected_total_legs()` — totals markets
- Simulated `p1_avg`, `p1_180s`, `p1_doubles_pct` (calibration / props)
- `summary()` — a formatted report

## Package layout

| Module                   | Responsibility                                          |
|--------------------------|---------------------------------------------------------|
| `dartsmod/checkout.py`   | Standard checkout-route planning (2–170, bogeys)        |
| `dartsmod/player.py`     | `DartsPlayer` and stat → parameter derivation           |
| `dartsmod/engine.py`     | Dart-, visit- and leg-level simulation                  |
| `dartsmod/formats.py`    | Leg- and set-play formats + real-world presets          |
| `dartsmod/match.py`      | Full-match simulation, throw alternation, live resume   |
| `dartsmod/simulation.py` | Monte Carlo driver and market aggregation               |
| `dartsmod/adjustments.py`| Form (EMA), stage/floor and fatigue coefficients        |
| `dartsmod/cli.py`        | Command-line interface                                   |

## Tests

```bash
pytest
```

The suite covers checkout-route correctness (every finish ends on a double, sums
match, bogeys are unfinishable), engine legality (no illegal scores, no sub-9-dart
legs), the throw advantage, calibration (simulated averages and doubles %% track
the inputs), format variance behaviour, determinism under a fixed seed, and the
form/stage/fatigue adjustments.

## Modelling notes & limitations

- Scoring is modelled as aiming at the treble-20 bed with a realistic miss
  profile; it captures the mean and variance of visit scores rather than every
  multi-modal spike. This is what drives leg outcomes.
- Checkout routes are computed by shortest-path search preferring favourable
  finishing doubles; setup darts succeed at the relevant treble/single rate and
  the finishing double at `double_prob`, so doubles %% is interpretable and
  directly calibratable.
- The engine is deterministic given a seed, making results reproducible.
