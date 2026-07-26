"""HTTP/JSON API around the DartsMod simulation engine.

This exposes the Python engine as a REST service so an external frontend -- an AI
Studio app, a function-calling tool, a web page, anything that speaks HTTP -- can
run predictions without embedding the engine.

Run locally::

    pip install -e ".[api]"
    uvicorn dartsmod.api:api --reload --port 8000

Then open http://localhost:8000/docs for interactive docs, or import
http://localhost:8000/openapi.json into your frontend/tool builder.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - import guard
    raise ImportError(
        "The API requires FastAPI and Uvicorn. Install with: pip install -e '.[api]'"
    ) from exc

from . import data
from .data import find_players, get_players, get_upcoming_matches, infer_match_format
from .formats import PRESETS, Format, resolve_format
from .match import LiveState
from .player import DartsPlayer
from .simulation import run_simulation

api = FastAPI(
    title="DartsMod API",
    version="0.1.0",
    description="Visit-level Monte Carlo darts match prediction engine.",
)

# CORS: open by default so a browser-based frontend can call the API during
# development. Restrict `allow_origins` to your frontend's domain in production.
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_SIMS = 200_000


# --- Request models ----------------------------------------------------------

class PlayerIn(BaseModel):
    name: str = Field(..., examples=["Luke Humphries"])
    scoring_average: float = Field(98.0, description="Three-dart scoring (First-9) average", ge=1, le=180)
    double_prob: Optional[float] = Field(None, description="Per-dart double probability, 0-1", ge=0, le=1)
    checkout_percentage: Optional[float] = Field(None, description="Checkout %% (alternative to double_prob)", ge=0, le=100)
    with_throw_average: Optional[float] = Field(None, description="Scoring average in legs the player starts")
    against_throw_average: Optional[float] = Field(None, description="Scoring average in legs the opponent starts")
    form_std: Optional[float] = Field(None, description="Match-to-match scoring volatility (points)")

    def to_player(self) -> DartsPlayer:
        if self.double_prob is not None:
            dp = self.double_prob
        elif self.checkout_percentage is not None:
            dp = self.checkout_percentage / 100.0
        else:
            dp = 0.40
        return DartsPlayer(
            name=self.name,
            scoring_average=self.scoring_average,
            double_prob=dp,
            with_throw_average=self.with_throw_average,
            against_throw_average=self.against_throw_average,
            form_std=self.form_std if self.form_std is not None else 0.0,
        )


class LiveStateIn(BaseModel):
    sets_p1: int = 0
    sets_p2: int = 0
    legs_p1: int = 0
    legs_p2: int = 0
    score_p1: int = Field(501, ge=0, le=501)
    score_p2: int = Field(501, ge=0, le=501)
    p1_to_throw: bool = True
    set_starter_p1: bool = True
    leg_starter_p1: bool = True

    def to_state(self) -> LiveState:
        return LiveState(
            sets={1: self.sets_p1, 2: self.sets_p2},
            legs_in_set={1: self.legs_p1, 2: self.legs_p2},
            leg_scores={1: self.score_p1, 2: self.score_p2},
            p1_to_throw=self.p1_to_throw,
            set_starter_p1=self.set_starter_p1,
            leg_starter_p1=self.leg_starter_p1,
        )


class SimulateRequest(BaseModel):
    player_1: PlayerIn
    player_2: PlayerIn
    format: str = Field("premier_league", description="Preset name, 'bestofN', or 'firsttoN'")
    legs_to_win_set: Optional[int] = Field(None, description="Custom format: legs to win a set", ge=1)
    sets_to_win: Optional[int] = Field(None, description="Custom format: sets to win the match", ge=1)
    sims: int = Field(10_000, ge=1, le=MAX_SIMS)
    seed: Optional[int] = None
    first_thrower_p1: bool = True
    over_under_line: Optional[float] = Field(None, description="Total-legs line, e.g. 10.5")
    state: Optional[LiveStateIn] = None

    def to_format(self) -> Format:
        if self.legs_to_win_set is not None or self.sets_to_win is not None:
            legs = self.legs_to_win_set or 1
            sets = self.sets_to_win or 1
            name = (
                f"First to {sets} sets (first to {legs} legs)"
                if sets > 1 else f"First to {legs} legs"
            )
            return Format(name=name, legs_to_win_set=legs, sets_to_win=sets)
        try:
            return resolve_format(self.format)
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=422,
                detail=f"Unknown format '{self.format}'. See GET /formats.",
            )


# --- Response models ---------------------------------------------------------

class Scoreline(BaseModel):
    score: str
    prob: float


class SimulateResponse(BaseModel):
    player_1: str
    player_2: str
    format: str
    sims: int
    win_prob: Dict[str, float]
    fair_odds: Dict[str, float]
    scorelines: List[Scoreline]
    expected_total_legs: float
    over_under: Optional[Dict[str, float]] = None
    averages: Dict[str, float]
    one_eighties: Dict[str, float]
    doubles_pct: Dict[str, float]


# --- Endpoints ---------------------------------------------------------------

class PlayerOut(BaseModel):
    key: int
    name: str
    country: str
    scoring_average: float
    three_dart_average: float
    checkout_percentage: float
    with_throw_average: float
    against_throw_average: float
    form_std: float


_INDEX_HTML = (pathlib.Path(__file__).parent / "static" / "index.html")


_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


@api.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the built-in web UI from the same origin as the API."""
    return HTMLResponse(_INDEX_HTML.read_text(encoding="utf-8"), headers=_NO_CACHE)


@api.on_event("startup")
def _warm_roster() -> None:
    """Kick off the first roster build in the background as the server boots."""
    data._background_refresh()


@api.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@api.get("/players", response_model=List[PlayerOut])
def players(response: Response, q: str = "", limit: int = 200) -> List[dict]:
    """Current professional players with auto-fetched stats (search with ``q``).

    Feed a player's ``scoring_average`` and ``checkout_percentage`` straight into
    ``POST /simulate`` -- no manual stat entry needed.
    """
    response.headers.update(_NO_CACHE)
    return find_players(query=q, limit=limit)


class FixturePlayer(BaseModel):
    key: int
    name: str
    scoring_average: float
    checkout_percentage: float
    with_throw_average: float
    against_throw_average: float
    form_std: float
    known: bool  # True if we have real stats; False = using defaults


class FixtureFormat(BaseModel):
    label: str
    legs_to_win_set: int
    sets_to_win: int


class FixtureOut(BaseModel):
    event: str
    round: str
    date: str
    format: FixtureFormat
    player_1: FixturePlayer
    player_2: FixturePlayer


@api.get("/fixtures", response_model=List[FixtureOut])
def fixtures(response: Response) -> List[dict]:
    """Upcoming professional matches, auto-discovered, with stats attached.

    Each match's players are joined to the live roster by key, so the frontend can
    predict a fixture in one tap. Empty when no matches are currently scheduled.
    """
    response.headers.update(_NO_CACHE)
    roster = {p["key"]: p for p in get_players()}

    def to_player(key: int, name: str) -> dict:
        r = roster.get(key)
        if r:
            return {"key": key, "name": r["name"], "scoring_average": r["scoring_average"],
                    "checkout_percentage": r["checkout_percentage"],
                    "with_throw_average": r["with_throw_average"],
                    "against_throw_average": r["against_throw_average"],
                    "form_std": r["form_std"], "known": True}
        return {"key": key, "name": name or "Unknown", "scoring_average": 95.0,
                "checkout_percentage": 38.0, "with_throw_average": 95.0,
                "against_throw_average": 95.0, "form_std": 6.0, "known": False}

    return [
        {
            "event": m["event"], "round": m["round"], "date": m["date"],
            "format": infer_match_format(m["event"], m["round"]),
            "player_1": to_player(m["p1_key"], m["p1_name"]),
            "player_2": to_player(m["p2_key"], m["p2_name"]),
        }
        for m in get_upcoming_matches()
    ]


@api.get("/formats")
def formats() -> Dict[str, object]:
    """List the built-in format presets (plus the dynamic 'bestofN'/'firsttoN')."""
    return {
        "presets": {
            key: {
                "name": fmt.name,
                "legs_to_win_set": fmt.legs_to_win_set,
                "sets_to_win": fmt.sets_to_win,
            }
            for key, fmt in PRESETS.items()
        },
        "dynamic": ["bestofN (e.g. bestof11)", "firsttoN (e.g. firstto6)"],
    }


@api.post("/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest) -> SimulateResponse:
    """Run a Monte Carlo simulation of the match and return the aggregated markets."""
    p1 = request.player_1.to_player()
    p2 = request.player_2.to_player()
    fmt = request.to_format()
    state = request.state.to_state() if request.state else None

    result = run_simulation(
        p1, p2, fmt,
        n=request.sims,
        first_thrower_p1=request.first_thrower_p1,
        state=state,
        seed=request.seed,
    )

    odds_p1, odds_p2 = result.fair_odds()
    response = SimulateResponse(
        player_1=result.player_1,
        player_2=result.player_2,
        format=fmt.name,
        sims=result.n,
        win_prob={"player_1": result.p1_win_prob, "player_2": result.p2_win_prob},
        fair_odds={"player_1": odds_p1, "player_2": odds_p2},
        scorelines=[Scoreline(score=s, prob=p) for s, p in result.most_likely_scorelines(8)],
        expected_total_legs=result.expected_total_legs(),
        averages={"player_1": result.p1_avg, "player_2": result.p2_avg},
        one_eighties={"player_1": result.p1_180s, "player_2": result.p2_180s},
        doubles_pct={"player_1": result.p1_doubles_pct, "player_2": result.p2_doubles_pct},
    )
    if request.over_under_line is not None:
        over, under = result.over_under(request.over_under_line)
        response.over_under = {"line": request.over_under_line, "over": over, "under": under}
    return response
