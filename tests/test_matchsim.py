"""Fast checks for the synthetic league generator. Run with:  uv run pytest -q"""

from __future__ import annotations

import datetime as dt
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchsim.config import PITCH_LENGTH, PITCH_WIDTH, SimConfig  # noqa: E402
from matchsim.engine import MatchEngine, xg_model  # noqa: E402
from matchsim.schema import EVENT_TYPES, to_absolute  # noqa: E402
from matchsim.season import double_round_robin, league_calendar, standings  # noqa: E402
from matchsim.universe import best_xi, build_universe, plant_traits  # noqa: E402


def _match(seed: int = 3):
    u = build_universe(1)
    home, away = u.division(1)[0], u.division(1)[5]
    return home, away, MatchEngine("T1", home, away, seed=seed).simulate()


def test_universe_is_deterministic():
    a, b = build_universe(9), build_universe(9)
    assert [c.name for c in a.clubs] == [c.name for c in b.clubs]
    assert a.clubs[3].squad[5].attrs == b.clubs[3].squad[5].attrs


def test_match_is_deterministic():
    _, _, r1 = _match(11)
    _, _, r2 = _match(11)
    assert r1.events == r2.events


def test_score_matches_goal_events():
    home, away, r = _match()
    goals = Counter()
    for e in r.events:
        if e["type"] == "shot" and e["outcome"] == "goal":
            goals[e["team_id"]] += 1
        if e["type"] == "own_goal":
            other = away.club_id if e["team_id"] == home.club_id else home.club_id
            goals[other] += 1
    assert goals[home.club_id] == r.home_goals
    assert goals[away.club_id] == r.away_goals


def test_events_are_well_formed():
    home, away, r = _match()
    clock = [e["clock_s"] for e in r.events]
    assert clock == sorted(clock), "events must be in time order"
    for e in r.events:
        assert e["type"] in EVENT_TYPES
        assert e["team_id"] in (home.club_id, away.club_id)
        assert 0 <= e["x"] <= PITCH_LENGTH and 0 <= e["y"] <= PITCH_WIDTH
        if e["end_x"] is not None:
            assert 0 <= e["end_x"] <= PITCH_LENGTH and 0 <= e["end_y"] <= PITCH_WIDTH
        if e["type"] == "shot":
            assert 0 < e["xg"] < 1
    assert r.events[-1]["minute"] <= 105
    assert 600 < len(r.events) < 4000


def test_xg_model_is_sensible():
    assert xg_model(94, 34) > xg_model(80, 34) > xg_model(70, 34)
    assert xg_model(99, 34) > 0.4
    assert xg_model(94, 34, header=True) < xg_model(94, 34)


def test_double_round_robin():
    ids = [f"C{i}" for i in range(20)]
    rounds = double_round_robin(ids, random.Random(1))
    assert len(rounds) == 38
    for rnd in rounds:
        teams = [t for pair in rnd for t in pair]
        assert len(teams) == len(set(teams)) == 20
    pairs = Counter((h, a) for rnd in rounds for h, a in rnd)
    assert all(v == 1 for v in pairs.values())
    assert len(pairs) == 20 * 19  # everyone hosts everyone once


def _venues(rounds, ids):
    seq = {c: [] for c in ids}
    for rnd in rounds:
        for h, a in rnd:
            seq[h].append("H")
            seq[a].append("A")
    return seq


def _longest_run(s):
    best = run = 1
    for i in range(1, len(s)):
        run = run + 1 if s[i] == s[i - 1] else 1
        best = max(best, run)
    return best


def test_home_and_away_alternate():
    for n in (20, 24):
        ids = [f"C{i:02d}" for i in range(n)]
        for seed in range(20):
            seq = _venues(double_round_robin(ids, random.Random(seed)), ids)
            for s in seq.values():
                assert s.count("H") == s.count("A") == n - 1
                assert 4 <= s[:10].count("H") <= 6        # balanced early on, not 10 home games in a row
                assert _longest_run(s) <= 3


def test_featured_fixture_lands_in_its_round():
    ids = [f"C{i:02d}" for i in range(1, 21)]
    for seed in range(10):
        rounds = double_round_robin(ids, random.Random(seed), feature=("C01", "C20", 11))
        assert ("C01", "C20") in rounds[10]
        assert sum(("C01", "C20") in r for r in rounds) == 1
        assert ("C20", "C01") in rounds[29]                # the return fixture in the second half
        for s in _venues(rounds, ids).values():
            assert s.count("H") == 19


def test_calendar():
    dates = league_calendar(46, 2025, random.Random(2))
    assert len(dates) == 46
    assert dates == sorted(dates) and len(set(dates)) == 46
    assert dates[0] >= dt.date(2025, 8, 15) and dates[-1] <= dt.date(2026, 5, 31)


def test_standings_points():
    rows = [{"stage": "league", "round": 1, "home_id": "A", "away_id": "B", "home_goals": 2, "away_goals": 0},
            {"stage": "league", "round": 2, "home_id": "B", "away_id": "A", "home_goals": 1, "away_goals": 1}]
    t = standings(rows, ["A", "B"], {"A": "A", "B": "B"})
    assert t[0]["club_id"] == "A" and t[0]["points"] == 4 and t[1]["points"] == 1


def test_planted_players_stay_in_the_team():
    u = build_universe(4)
    truths = plant_traits(u.clubs, 1, "2025-26", random.Random(5))
    xi = {p.player_id for c in u.division(1) for _s, p in best_xi(c)}
    planted = [t for t in truths if t.scope == "player"]
    assert planted
    assert all(t.player_id in xi for t in planted)


def test_to_absolute():
    assert to_absolute(10, 5, True, 1) == (10, 5)
    assert to_absolute(10, 5, False, 1) == (95, 63)
    assert to_absolute(10, 5, True, 2) == (95, 63)


def test_mini_pipeline(tmp_path):
    from matchsim.pipeline import generate
    cfg = SimConfig(seed=3, top_division_size=8, second_division_size=8, current_rounds_played=2,
                    showcase_round=3, showcase_variants=2, workers=1, out_dir=str(tmp_path),
                    transfers_per_summer=3, manager_changes=1, champions_league_spots=2,
                    europa_league_spots=1)
    summary = generate(cfg)
    assert summary["matches"] > 0
    pub = tmp_path / "public"
    for f in ("clubs.csv", "matches.csv", "lineups.csv", "standings.csv", "offseason.json",
              "showcase/showcase_match.json", "events/events_2025-26.parquet"):
        assert (pub / f).exists(), f
    key = json.loads((tmp_path / "hidden" / "answer_key.json").read_text())
    assert key["seasons"]["2025-26"]
    assert (tmp_path / "reports" / "realism_report.md").exists()
