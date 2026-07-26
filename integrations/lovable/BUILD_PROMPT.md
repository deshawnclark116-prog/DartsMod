# Lovable build prompt (auto-stats version)

Paste this into Lovable. The app lets the user pick two real players from live,
auto-fetched stats — no typing numbers — and predicts the match. It calls the
live API at https://dartsmod.onrender.com. No backend code needed on Lovable's
side.

---

Build a "Darts Match Predictor" web app. It should feel effortless: the user picks
two professional darts players and a format, and the app predicts the match. The
app fetches the player list and their stats automatically from an API — the user
never types any statistics. All numbers come from the API; never compute or invent
values on the client.

## Data source: load the player list on startup

On page load, GET https://dartsmod.onrender.com/players

It returns an array of players, already sorted best-first:
```json
[
  { "key": 5403, "name": "Luke Littler", "country": "ENG", "scoring_average": 111.9, "three_dart_average": 101.5, "checkout_percentage": 43.7 },
  { "key": 34, "name": "Luke Humphries", "country": "ENG", "scoring_average": 109.3, "three_dart_average": 99.7, "checkout_percentage": 41.1 }
]
```

Use this to populate two **searchable dropdowns** (Player 1 and Player 2). Show
the player name and country flag/code; you may show their three-dart average as a
subtle subtitle. Do NOT show input boxes for averages or checkout % — those come
from the selected player automatically.

## Controls

- Player 1: searchable dropdown of players from /players (default: the first player)
- Player 2: searchable dropdown of players from /players (default: the second player)
- Format dropdown (label → value):
  - Premier League → `premier_league`
  - Players Championship → `players_championship`
  - World Matchplay R1 → `world_matchplay_r1`
  - UK Open Final → `uk_open_final`
  - World Championship R1 → `world_championship_r1`
  - World Championship Semi → `world_championship_semi`
  - World Championship Final → `world_championship_final`
- Simulations: default 10000 (can be a hidden/advanced setting)
- Over/Under legs line: number, default 10.5
- "Predict" button

## Predict: call the simulation API

When "Predict" is clicked, take the two SELECTED player objects and POST:

- URL: https://dartsmod.onrender.com/simulate
- Header: Content-Type: application/json
- Body:
```json
{
  "player_1": { "name": <p1.name>, "scoring_average": <p1.scoring_average>, "checkout_percentage": <p1.checkout_percentage> },
  "player_2": { "name": <p2.name>, "scoring_average": <p2.scoring_average>, "checkout_percentage": <p2.checkout_percentage> },
  "format": <selected format value>,
  "sims": <simulations>,
  "over_under_line": <over/under line>
}
```

Response:
```json
{
  "player_1": "Luke Littler",
  "player_2": "Luke Humphries",
  "format": "First to 7 sets (first to 3 legs)",
  "win_prob": { "player_1": 0.55, "player_2": 0.45 },
  "fair_odds": { "player_1": 1.82, "player_2": 2.22 },
  "scorelines": [ { "score": "7-5", "prob": 0.14 } ],
  "expected_total_legs": 45.2,
  "over_under": { "line": 10.5, "over": 0.62, "under": 0.38 },
  "averages": { "player_1": 96.1, "player_2": 95.4 },
  "one_eighties": { "player_1": 14.5, "player_2": 13.0 },
  "doubles_pct": { "player_1": 41.4, "player_2": 39.3 }
}
```

## Results display

- A large head-to-head win-probability bar (Player 1 vs Player 2) with each
  percentage and the fair decimal odds beneath each name.
- "Most likely scorelines": top 5 from `scorelines`, each a labelled bar with its
  probability.
- Stat cards: expected total legs; over/under (both over % and under % for the
  line); and per player their simulated 3-dart average, 180s per match, doubles %.
- Use the player names from the response as labels everywhere.

## Behaviour

- Fetch /players on load; show a spinner until it arrives. If it fails, show a
  friendly error and a retry button.
- The API sleeps when idle on its host, so the FIRST /players or /simulate call
  after a pause can take 30–60 seconds. Keep spinners up; use a 90s timeout; never
  fail early.
- Disable Predict until both players are selected and are different people.

## Design

Clean, dark, sporty look. Large readable numbers, country flags, good contrast,
fully responsive on mobile. A darts/oche accent colour is welcome.
