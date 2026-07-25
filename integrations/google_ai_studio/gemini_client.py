"""Connect Google Gemini (AI Studio) to the DartsMod API via function calling.

Gemini decides *when* to predict a darts match and with what arguments; this
script executes the actual call against the running DartsMod API and feeds the
result back so Gemini can answer in natural language. This uses the Gemini SDK's
*automatic function calling*: the tool declaration is built from the Python
function's signature and docstring, and the SDK runs the call loop for you.

Setup
-----
    pip install -r integrations/google_ai_studio/requirements.txt
    export GEMINI_API_KEY="...your AI Studio key..."      # aistudio.google.com -> Get API key
    export DARTSMOD_API_URL="http://localhost:8000"       # or your deployed URL

    # In another terminal, run the API:
    uvicorn dartsmod.api:api --port 8000

    python integrations/google_ai_studio/gemini_client.py
"""

from __future__ import annotations

import os

import requests

try:
    from google import genai
    from google.genai import types
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Install the Gemini SDK first:\n"
        "  pip install -r integrations/google_ai_studio/requirements.txt"
    ) from exc

DARTSMOD_API_URL = os.environ.get("DARTSMOD_API_URL", "http://localhost:8000")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def simulate_darts_match(
    player_1_name: str,
    player_2_name: str,
    player_1_scoring_average: float = 98.0,
    player_2_scoring_average: float = 98.0,
    player_1_double_prob: float = 0.40,
    player_2_double_prob: float = 0.40,
    match_format: str = "premier_league",
    sims: int = 10000,
) -> dict:
    """Simulate a professional darts match and return win probabilities and markets.

    Use this whenever the user asks who would win a darts match, for match odds, a
    likely scoreline, or an over/under on total legs.

    Args:
        player_1_name: Name of the first player.
        player_2_name: Name of the second player.
        player_1_scoring_average: Player 1's three-dart scoring average (e.g. 102.5).
        player_2_scoring_average: Player 2's three-dart scoring average (e.g. 99.8).
        player_1_double_prob: Player 1's per-dart double probability, 0-1 (e.g. 0.42).
        player_2_double_prob: Player 2's per-dart double probability, 0-1 (e.g. 0.40).
        match_format: Format preset (e.g. world_championship_final) or bestofN.
        sims: Number of Monte Carlo simulations.

    Returns:
        A dict with win_probability, fair_odds, most_likely_scorelines and
        expected_total_legs.
    """
    payload = {
        "player_1": {
            "name": player_1_name,
            "scoring_average": player_1_scoring_average,
            "double_prob": player_1_double_prob,
        },
        "player_2": {
            "name": player_2_name,
            "scoring_average": player_2_scoring_average,
            "double_prob": player_2_double_prob,
        },
        "format": match_format,
        "sims": sims,
    }
    resp = requests.post(f"{DARTSMOD_API_URL}/simulate", json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return {
        "win_probability": data["win_prob"],
        "fair_odds": data["fair_odds"],
        "most_likely_scorelines": data["scorelines"][:5],
        "expected_total_legs": data["expected_total_legs"],
        "player_averages": data["averages"],
    }


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (get one at https://aistudio.google.com).")

    client = genai.Client(api_key=api_key)

    prompt = (
        "Luke Humphries averages about 102.5 with a 42% checkout; Michael van "
        "Gerwen averages 99.8 with 40%. Who is more likely to win a World "
        "Championship final, and what's the most likely scoreline?"
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[simulate_darts_match],  # automatic function calling
        ),
    )
    print(response.text)


if __name__ == "__main__":
    main()
