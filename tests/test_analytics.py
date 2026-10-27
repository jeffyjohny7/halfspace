"""Tests for the stats engine, live layer and MCP server on a small generated league."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics.api import Analyst  # noqa: E402
from analytics.build import build_all  # noqa: E402
from analytics.store import HiddenDataError, Store  # noqa: E402
from analytics import xt  # noqa: E402
from matchsim.config import SimConfig  # noqa: E402
from matchsim.pipeline import generate  # noqa: E402


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("league")
    cfg = SimConfig(seed=5, top_division_size=8, second_division_size=8, current_rounds_played=4,
                    showcase_round=5, showcase_variants=2, workers=1, out_dir=str(out),
                    transfers_per_summer=3, manager_changes=1, champions_league_spots=2, europa_league_spots=1)
    generate(cfg)
    build_all(str(out), verbose=False)
    return out


@pytest.fixture(scope="module")
def analyst(data_dir) -> Analyst:
    return Analyst(str(data_dir))


def test_hidden_folder_is_blocked(data_dir):
    s = Store(data_dir)
    with pytest.raises(HiddenDataError):
        s.public_path("..", "hidden", "answer_key.json")
    with pytest.raises(HiddenDataError):
        s.derived_path("..", "hidden", "player_attributes.csv")


def test_runtime_code_never_imports_evaluation():
    for folder in ("analytics", "mcp_server"):
        for f in (ROOT / folder).glob("*.py"):
            src = f.read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import)\s+evaluation", src, re.M), f"{f} imports evaluation"
            assert "answer_key" not in src, f"{f} mentions the answer key file"


def test_goals_reconcile(analyst):
    s = analyst.store
    shots, tm = s.table("shots"), s.table("team_match")
    assert shots.is_goal.sum() == tm.goals_for.sum() == tm.goals_against.sum()
    m = s.matches
    assert (m.home_goals.sum() + m.away_goals.sum()) == tm.goals_for.sum()


def test_xt_rises_toward_goal(analyst):
    grid = xt.from_json(analyst.store.xt_grid)
    near = xt.lookup(grid, [100.0], [34.0])[0]
    mid = xt.lookup(grid, [50.0], [34.0])[0]
    assert near > mid > 0


def test_profiles_and_breakdowns(analyst):
    club = analyst.store.upcoming.iloc[0].home_id
    prof = analyst.club_profile(club)
    assert prof["record"]["played"] > 0 and prof["style"]
    for side in ("conceded", "scored"):
        gb = analyst.goals_breakdown(club, side)
        assert gb["goals"] == sum(r["goals"] for r in gb["by_phase"])
        assert gb["goals"] == sum(b["goals"] for b in gb["by_time"])
    pid = analyst.squad_report(club)["players"][0]["player_id"]
    pp = analyst.player_profile(pid)
    assert pp["seasons"]


def test_findings_are_well_formed(analyst):
    for club in analyst.store.club_seasons.query("division == 1").club_id.unique()[:4]:
        res = analyst.scout_findings(club, min_confidence="low")
        for f in res["findings"]:
            assert f["confidence"] in ("high", "medium", "low")
            assert f["summary"] and f["category"]
            assert isinstance(f["evidence"], list)


def test_matchup_and_live(analyst):
    rep = analyst.showcase_report()
    assert "edges" in rep and "predictions_to_track" in rep
    live = analyst.live
    end = analyst.live_state(1e9)
    goals = live.shots[live.shots.is_goal]
    assert end["score"]["home"] + end["score"]["away"] == len(goals)
    early = analyst.live_state(600)
    assert early["clock_s"] <= 600
    moments = analyst.live_key_moments(1e9, min_importance=0.0)
    assert [m["clock_s"] for m in moments] == sorted(m["clock_s"] for m in moments)
    assert sum(m["type"] == "goal" for m in moments) == len(goals)
    for p in analyst.live_predictions(1e9):
        assert p["status"] in ("confirmed", "did not happen", "not happening", "waiting for a sample", "not yet")
    shooter = live.shots[live.shots.kind == "shot"].player_id.iloc[0]       # live line for a player who shot
    line = analyst.live_player(shooter, 1e9)
    assert line["shots"] >= 1 and line["fastest_shot_kmh"] and line["fastest_shot_kmh"] > 0


def test_mcp_server_tools_and_live_clock(data_dir, monkeypatch):
    from mcp_server.compat import connect, is_error
    import mcp_server.server as srv
    monkeypatch.setattr(srv, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(srv, "_analyst", None)
    runtime = Path(data_dir) / "runtime"
    runtime.mkdir(exist_ok=True)
    (runtime / "live_clock.json").write_text(json.dumps({"clock_s": 900}), encoding="utf-8")

    async def run():
        async with connect(srv.mcp) as c:
            tools = {t.name for t in (await c.list_tools()).tools}
            assert {"overview", "matchup_report", "live_state", "get_events", "scout_findings", "team_news",
                    "injuries", "match_lineup"} <= tools
            ov = json.loads((await c.call_tool("overview", {})).content[0].text)
            fx = ov["showcase_fixture"]
            rep = json.loads((await c.call_tool("matchup_report", {"home": fx["home"], "away": fx["away"]})).content[0].text)
            assert "edges" in rep
            st = json.loads((await c.call_tool("live_state", {"clock_s": 99999})).content[0].text)
            assert st["clock_s"] <= 900, "live tools must not see past the feed clock"
            news = json.loads((await c.call_tool("team_news", {"club": fx["home"]})).content[0].text)
            assert "unavailable" in news and "doubtful" in news
            xi = json.loads((await c.call_tool("match_lineup", {"club": fx["home"]})).content[0].text)
            assert len(xi["starting_xi"]) == 11
            assert all(p["rating"] is not None for p in xi["starting_xi"])
            rt = json.loads((await c.call_tool("live_ratings", {"clock_s": 99999})).content[0].text)
            assert rt["minute"] <= 16 and rt["highest"]["rating"] >= 6.0     # capped at the feed clock too
            bad = await c.call_tool("club_profile", {"club": "No Such Club FC"})
            assert is_error(bad)

    try:
        asyncio.run(run())
    finally:
        (runtime / "live_clock.json").unlink(missing_ok=True)


def test_injured_and_suspended_players_do_not_play(analyst):
    s = analyst.store
    news = s.team_news
    assert len(news) and len(s.injuries) and set(news.status) <= {"injured", "suspended", "doubtful"}
    out = news[news.status.isin(["injured", "suspended"])][["match_id", "player_id"]]
    lu = s.lineups[s.lineups.minutes.fillna(0) > 0][["match_id", "player_id"]]
    clash = out.merge(lu, on=["match_id", "player_id"])
    assert clash.empty, f"{len(clash)} unavailable players appeared in a match"
    # A straight red card means the player misses his club's next league match.
    sus = s.suspensions
    if len(sus):
        r = sus.iloc[0]
        nxt = news[(news.player_id == r.player_id) & (news.date > r.date)]
        assert len(nxt) and nxt.sort_values("date").iloc[0].status == "suspended"


def test_public_injuries_do_not_leak_future_returns(analyst):
    s = analyst.store
    cutoff = s.showcase_meta["date"]
    inj = s.injuries
    assert (inj.return_date.dropna() <= cutoff).all()
    assert (inj.date <= cutoff).all()


# Match ratings

def test_ratings_are_explained_and_realistic(analyst):
    """Every rating is 6.0 plus the listed actions; a goal is worth +1.0 at that moment; future substitutes
    are not rated; season ratings sit where fans expect them."""
    from analytics import rating
    live = analyst.live
    end = live.end_clock
    acts = live.rating_actions
    for team_rows in analyst.live_ratings(end)["by_team"].values():
        for row in team_rows:
            pid = analyst.player_id(row["player"])
            total = acts[acts.player_id == pid].delta.sum()
            assert row["rating"] == pytest.approx(float(rating.clamp(rating.BASE + total)), abs=0.051)
    goal = live.shots[live.shots.is_goal & (live.shots.kind == "shot")].iloc[0]
    before = live.rating(goal.player_id, goal.clock_s - 0.05)["rating"]
    after = live.rating(goal.player_id, goal.clock_s)["rating"]
    assert after - before >= 0.65                       # +1.0 (or +0.7 for a penalty), less a rounding step
    subs = live.lineups[live.lineups.started == False]  # noqa: E712
    late = subs[subs.minute_on.notna()]
    if len(late):
        assert live.rating(str(late.player_id.iloc[0]), 60)["rating"] is None
    r = analyst.store.player_ratings
    assert 6.2 <= r.rating.median() <= 7.3 and r.rating.between(rating.LOW, rating.HIGH).all()
