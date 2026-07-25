# AI Studio "Build" prompt

Paste the text below into Google AI Studio's **Build** tab (build an app), after
replacing `https://YOUR-DARTSMOD-URL` with your deployed API URL. AI Studio
generates the React frontend; it fetches live predictions from your DartsMod API.

> The frontend calls your **deployed API URL**, not GitHub. Deploy the repo first
> (the included `Dockerfile` works on Render/Railway/Fly/Cloud Run) to get a URL.

---

Build a single-page "Darts Match Predictor" web app.

The app collects stats for two darts players and a match format, then calls an
external prediction API and displays the results. Do NOT compute anything
locally — get all numbers from the API.

INPUTS (a form):
- Player 1: name (text), scoring average (number, default 98), checkout %
  (number 0–100, default 40)
- Player 2: name (text), scoring average (number, default 98), checkout %
  (number 0–100, default 40)
- Format: a dropdown with these values (label → value):
  Premier League → premier_league
  Players Championship → players_championship
  World Matchplay R1 → world_matchplay_r1
  UK Open Final → uk_open_final
  World Championship R1 → world_championship_r1
  World Championship Semi → world_championship_semi
  World Championship Final → world_championship_final
- Simulations: number, default 10000
- Over/Under legs line: number, default 10.5
- A "Predict" button.

WHEN "Predict" IS CLICKED, send:
  POST https://YOUR-DARTSMOD-URL/simulate
  Header: Content-Type: application/json
  Body (JSON):
  {
    "player_1": { "name": <p1 name>, "scoring_average": <p1 avg>, "checkout_percentage": <p1 checkout %> },
    "player_2": { "name": <p2 name>, "scoring_average": <p2 avg>, "checkout_percentage": <p2 checkout %> },
    "format": <selected format value>,
    "sims": <simulations>,
    "over_under_line": <over/under line>
  }

THE RESPONSE JSON looks like:
  {
    "player_1": "Luke Humphries",
    "player_2": "Michael van Gerwen",
    "format": "First to 7 sets (first to 3 legs)",
    "win_prob": { "player_1": 0.72, "player_2": 0.28 },
    "fair_odds": { "player_1": 1.39, "player_2": 3.54 },
    "scorelines": [ { "score": "7-4", "prob": 0.15 }, ... ],
    "expected_total_legs": 45.2,
    "over_under": { "line": 10.5, "over": 0.62, "under": 0.38 },
    "averages": { "player_1": 94.7, "player_2": 93.1 },
    "one_eighties": { "player_1": 14.5, "player_2": 13.0 },
    "doubles_pct": { "player_1": 41.4, "player_2": 39.3 }
  }

DISPLAY THE RESULTS:
- A big head-to-head win-probability bar (player 1 vs player 2) showing each
  percentage and the fair decimal odds underneath.
- A "Most likely scorelines" list: each scoreline with its probability as a small
  bar (top 5).
- Cards for: expected total legs; over/under (show over % and under % for the
  line); each player's simulated 3-dart average, 180s per match, and doubles %.
- Show a loading state while the request is in flight, and a clear error message
  if the request fails.

STYLE: clean, dark, sporty; large readable numbers; responsive on mobile. Use the
players' names as labels everywhere (from the response).
