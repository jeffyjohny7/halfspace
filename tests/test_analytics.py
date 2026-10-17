"""Tests for the stats engine, live layer and MCP server on a small generated league.

Run with:  uv run pytest -q
"""

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


def test_mcp_server_tools_and_live_clock(data_dir, monkeypatch):
    from mcp import Client
    import mcp_server.server as srv
    monkeypatch.setattr(srv, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(srv, "_analyst", None)
    runtime = Path(data_dir) / "runtime"
    runtime.mkdir(exist_ok=True)
    (runtime / "live_clock.json").write_text(json.dumps({"clock_s": 900}), encoding="utf-8")

    async def run():
        async with Client(srv.mcp, raise_exceptions=True) as c:
            tools = {t.name for t in (await c.list_tools()).tools}
            assert {"overview", "matchup_report", "live_state", "get_events", "scout_findings"} <= tools
            ov = json.loads((await c.call_tool("overview", {})).content[0].text)
            fx = ov["showcase_fixture"]
            rep = json.loads((await c.call_tool("matchup_report", {"home": fx["home"], "away": fx["away"]})).content[0].text)
            assert "edges" in rep
            st = json.loads((await c.call_tool("live_state", {"clock_s": 99999})).content[0].text)
            assert st["clock_s"] <= 900, "live tools must not see past the feed clock"
            bad = await c.call_tool("club_profile", {"club": "No Such Club FC"})
            assert bad.is_error

    try:
        asyncio.run(run())
    finally:
        (runtime / "live_clock.json").unlink(missing_ok=True)
