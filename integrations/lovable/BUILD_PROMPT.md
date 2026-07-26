# Lovable build prompt

Paste this into Lovable to generate the DartsMod frontend. It calls the live API
at https://dartsmod.onrender.com — no backend code needed on Lovable's side.

---

Build a "Darts Match Predictor" web app.

It collects stats for two darts players and a match format, calls an existing
prediction API, and displays the results. All numbers come from the API — do not
compute or invent any values on the client.

## API integration

When the user clicks "Predict", send:

- Method: POST
- URL: https://dartsmod.onrender.com/simulate
- Header: Content-Type: application/json
- Body:
```json
{
  "player_1": { "name": "P1 NAME", "scoring_average": 98, "checkout_percentage": 40 },
  "player_2": { "name": "P2 NAME", "scoring_average": 98, "checkout_percentage": 40 },
  "format": "premier_league",
  "sims": 10000,
  "over_under_line": 10.5
}
```

The response looks like:
```json
{
  "player_1": "Luke Humphries",
  "player_2": "Michael van Gerwen",
  "format": "First to 7 sets (first to 3 legs)",
  "win_prob": { "player_1": 0.72, "player_2": 0.28 },
  "fair_odds": { "player_1": 1.39, "player_2": 3.54 },
  "scorelines": [ { "score": "7-4", "prob": 0.15 } ],
  "expected_total_legs": 45.2,
  "over_under": { "line": 10.5, "over": 0.62, "under": 0.38 },
  "averages": { "player_1": 94.7, "player_2": 93.1 },
  "one_eighties": { "player_1": 14.5, "player_2": 13.0 },
  "doubles_pct": { "player_1": 41.4, "player_2": 39.3 }
}
```

## Form inputs

- Player 1: name (text), scoring average (number, default 98), checkout %
  (number 0–100, default 40)
- Player 2: name (text), scoring average (number, default 98), checkout %
  (number 0–100, default 40)
- Format dropdown (label → value sent to the API):
  - Premier League → `premier_league`
  - Players Championship → `players_championship`
  - World Matchplay R1 → `world_matchplay_r1`
  - UK Open Final → `uk_open_final`
  - World Championship R1 → `world_championship_r1`
  - World Championship Semi → `world_championship_semi`
  - World Championship Final → `world_championship_final`
- Simulations (number, default 10000)
- Over/Under legs line (number, default 10.5)
- "Predict" button

## Results display

- A large head-to-head win-probability bar (Player 1 vs Player 2) showing each
  percentage and the fair decimal odds beneath each name.
- "Most likely scorelines": the top 5 from `scorelines`, each as a labelled bar
  with its probability.
- Stat cards: expected total legs; over/under (show both over % and under % for
  the line); and per player their simulated 3-dart average, 180s per match, and
  doubles %.
- Use the player names from the response as labels everywhere.

## Behaviour

- Show a loading spinner while the request is in flight. The API is on a free host
  and the FIRST request after it has been idle can take 30–60 seconds to wake up —
  keep the spinner up and do not time out early (use a 90s timeout).
- Show a clear, friendly error message if the request fails.

## Design

Clean, dark, sporty look. Large readable numbers, good contrast, fully responsive
on mobile. A darts/oche accent colour is welcome.
