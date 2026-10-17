"""Match-intelligence MCP server.

Agents never touch files or the hidden answer key: they see the league only
through these tools. Every number comes from the deterministic analytics
package, with event references a Verifier agent can check.

Run locally (stdio, for agents started on the same machine):
    uv run python -m mcp_server.server

Run over HTTP (e.g. on Azure Container Apps):
    uv run python -m mcp_server.server --http --port 8000

Live-clock guard: if data/runtime/live_clock.json exists ({"clock_s": 2700}),
live tools never return anything after that point of the match, whatever an
agent asks for. The feed replayer writes this file as the match "plays".
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from analytics.api import Analyst, NotFound

DATA_DIR = os.environ.get("MATCH_DATA_DIR", "data")

INSTRUCTIONS = """\
Match intelligence for a fictional football league (Crown League). Seasons: 2025-26 (complete) and 2026-27
(10 rounds played). Round 11's showcase fixture is the live match.

Rules for agents:
- Never invent numbers. Every number you state must come from a tool result.
- Cite evidence: keep match_id/event_id references from tool results so a verifier can check them.
- Respect confidence: 'high' findings can be stated as fact; 'medium' are things to watch; never state 'low' as fact.
- Clubs and players can be given by id (C02, P00032) or by name.
- Live tools take clock_s (seconds of play since kick-off) and only see events up to that moment.
Typical flow: overview -> matchup_report(home, away) -> scout_findings / goals_breakdown / player_profile for detail
-> during the match live_state, live_key_moments, live_predictions -> get_events to verify claims.
"""

mcp = MCPServer("match-intelligence", instructions=INSTRUCTIONS)
_analyst: Analyst | None = None


def analyst() -> Analyst:
    global _analyst
    if _analyst is None:
        _analyst = Analyst(DATA_DIR)
    return _analyst


def live_cap(clock_s: float) -> float:
    """Clamp a requested match clock to the live feed's current clock, if a feed is running."""
    path = Path(DATA_DIR) / "runtime" / "live_clock.json"
    if path.exists():
        try:
            cap = float(json.loads(path.read_text(encoding="utf-8"))["clock_s"])
            return min(float(clock_s), cap)
        except (ValueError, KeyError, json.JSONDecodeError):
            pass
    return float(clock_s)


def _call(fn, *args, **kwargs) -> Any:
    a = analyst()
    try:
        with a.lock:
            return fn(*args, **kwargs)
    except (NotFound, ValueError) as e:
        raise ToolError(str(e)) from e


# ---------------------------------------------------------------- league
@mcp.tool()
def overview() -> dict:
    """Start here. League structure, current table top and bottom, last summer's promotions, relegations,
    manager changes and European places, and the showcase (live) fixture."""
    return _call(analyst().overview)


@mcp.tool()
def league_table(season: str = "current", division: int = 1, after_round: int | None = None) -> dict:
    """League table with zones (Champions League, Europa League, relegation / promotion, playoffs).
    season: '2025-26', '2026-27', 'current' or 'previous'. division: 1 (Crown League) or 2 (Crown League Two)."""
    return _call(analyst().league_table, season, division, after_round)


@mcp.tool()
def search(query: str) -> dict:
    """Find clubs and players by (part of) their name. Returns ids."""
    return _call(analyst().search, query)


@mcp.tool()
def upcoming_fixtures() -> dict:
    """The next round's fixtures. The one marked showcase is the live match."""
    return {"fixtures": _call(analyst().upcoming_fixtures)}


# ---------------------------------------------------------------- clubs and players
@mcp.tool()
def club_profile(club: str, season: str = "current", venue: str = "all", last_n: int | None = None) -> dict:
    """A club's season: manager, formation, record, home/away splits, attack, defence, style
    (possession, pressing, directness, flanks), discipline, formations used and results, recent form.
    Every metric has a league percentile. venue: 'all', 'home' or 'away'. last_n: only the last N matches."""
    return _call(analyst().club_profile, club, season, venue, last_n)


@mcp.tool()
def goals_breakdown(club: str, side: str = "conceded", season: str = "current", venue: str = "all") -> dict:
    """How a club concedes (side='conceded') or scores (side='scored'): by phase (open play, counter, corner,
    free kick, penalty, throw-in, own goal) vs the league share, by 15-minute period, by game state and zone,
    plus the list of goals with scorer, assist and event references."""
    return _call(analyst().goals_breakdown, club, side, season, venue)


@mcp.tool()
def player_profile(player: str, season: str = "current") -> dict:
    """A player's per-90 numbers and rates for both seasons with percentiles vs the same position:
    passing (incl. completion above expected), progression, threat (xT), shooting (xG), ball security
    under pressure, duels, discipline, goalkeeping."""
    return _call(analyst().player_profile, player, season)


@mcp.tool()
def player_event_map(player: str, season: str = "current", kinds: list[str] | None = None) -> dict:
    """Where on the pitch and when in the match a player's events happen.
    kinds: any of 'dispossessed', 'turnover', 'foul', 'aerial_duel' (default: dispossessed and turnover)."""
    return _call(analyst().player_event_map, player, season, tuple(kinds or ("dispossessed", "turnover")))


@mcp.tool()
def squad_report(club: str, season: str = "current") -> dict:
    """Every player who has played for the club this season, with minutes and position-relevant metrics
    and percentiles."""
    return _call(analyst().squad_report, club, season)


@mcp.tool()
def scout_findings(club: str, season: str = "current", kind: str = "all", min_confidence: str = "medium") -> dict:
    """Statistically unusual weaknesses, strengths and tendencies of a club and its players, compared with
    peers, adjusted for team style and small samples, blending last season when this season is short.
    kind: 'all', 'weaknesses', 'strengths' or 'tendencies'. min_confidence: 'high', 'medium' or 'low'."""
    return _call(analyst().scout_findings, club, season, kind, min_confidence)


@mcp.tool()
def head_to_head(club_a: str, club_b: str) -> dict:
    """Previous meetings between two clubs (both seasons and divisions), with scores, xG and formations."""
    return _call(analyst().head_to_head, club_a, club_b)


@mcp.tool()
def matchup_report(home: str, away: str, season: str = "current", detail: str = "compact") -> dict:
    """Pre-match report: what's at stake, midweek European games, managers, form, head-to-head, style
    comparison, EDGES (one side's weakness vs the other's matching strength) and PREDICTIONS that can be
    checked live, key players and probable line-ups. detail: 'compact' (default) or 'full'."""
    return _call(analyst().matchup, home, away, season, None, detail != "full")


# ---------------------------------------------------------------- live match
@mcp.tool()
def live_state(clock_s: float) -> dict:
    """Live scoreboard of the showcase match at clock_s (seconds of play since kick-off): score, xG, shots,
    possession, field tilt, pressing, last-10-minute numbers, momentum by 5-minute block, control vs chaos."""
    return _call(analyst().live_state, live_cap(clock_s))


@mcp.tool()
def live_key_moments(clock_s: float, since_s: float = 0.0, min_importance: float = 0.3) -> dict:
    """Key moments up to clock_s (and after since_s): goals, big chances, penalties, cards, substitutions,
    momentum swings, pressure spells. Each has an importance score (0-1), facts and event references."""
    clock = live_cap(clock_s)
    return {"clock_s": clock, "moments": _call(analyst().live_key_moments, clock, since_s, min_importance)}


@mcp.tool()
def live_predictions(clock_s: float) -> dict:
    """Status of the pre-match predictions for the showcase match at clock_s: confirmed, on track, behind
    pace, too early, did not happen. This is how pre-match scouting is tested live."""
    clock = live_cap(clock_s)
    return {"clock_s": clock, "predictions": _call(analyst().live_predictions, clock)}


@mcp.tool()
def live_player(player: str, clock_s: float) -> dict:
    """One player's live line for player-focus mode: touches, passes, threat, shots, times pressed,
    dispossessions, duels, cards, fastest shot, hardest completed pass."""
    return _call(analyst().live_player, player, live_cap(clock_s))


# ---------------------------------------------------------------- evidence
@mcp.tool()
def get_events(match_id: str, event_ids: list[int], clock_s: float | None = None) -> dict:
    """Look up raw events by reference (match_id + event_ids) to verify a claim. For the live match pass
    clock_s; events after it are never returned."""
    return {"events": _call(analyst().get_events, match_id, event_ids, None if clock_s is None else live_cap(clock_s))}


@mcp.tool()
def glossary() -> dict:
    """Definitions of every metric, finding category, phase and term (xG, xT, PPDA, field tilt...)."""
    return _call(analyst().glossary)


def main() -> None:
    ap = argparse.ArgumentParser(description="Match-intelligence MCP server")
    ap.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if args.http:
        mcp.run(transport="streamable-http", host=args.host, port=args.port, json_response=True, stateless_http=True)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
