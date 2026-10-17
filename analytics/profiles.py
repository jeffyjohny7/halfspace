"""Club and player profiles, goal breakdowns, tables, form and head-to-head."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .build import TIME_BUCKETS, zone
from .metrics import PLAYER_METRICS, TEAM_METRICS, team_season_table, team_values
from .store import Store
from .util import clean, pct_rank

PHASE_LABELS = {
    "open_play": "Open play", "counter": "Counter-attack", "corner": "Corner", "free_kick": "Free kick (delivery)",
    "direct_free_kick": "Direct free kick", "penalty": "Penalty", "throw_in": "Throw-in", "own_goal": "Own goal",
}

# Which player metrics to show for each position in squad reports.
POSITION_KEY_METRICS = {
    "GK": ["gk_goals_prevented", "gk_claim_rate", "pass_completion"],
    "CB": ["aerial_win_rate", "completion_over_expected", "dispossessed_per_pressed", "tackles_interceptions_p90"],
    "RB": ["cross_completion", "dispossessed_per_pressed", "progressive_passes_p90", "tackles_interceptions_p90"],
    "LB": ["cross_completion", "dispossessed_per_pressed", "progressive_passes_p90", "tackles_interceptions_p90"],
    "DM": ["completion_over_expected", "dispossessed_per_pressed", "tackles_interceptions_p90", "progressive_passes_p90"],
    "CM": ["xt_p90", "progressive_passes_p90", "dispossessed_per_pressed", "completion_over_expected"],
    "AM": ["xt_p90", "xa_p90", "npxg_p90", "take_on_success"],
    "RW": ["xt_p90", "npxg_p90", "take_on_success", "cross_completion"],
    "LW": ["xt_p90", "npxg_p90", "take_on_success", "cross_completion"],
    "ST": ["npxg_p90", "goals_p90", "finishing_over_xg", "aerial_win_rate"],
}


def league_matches(store: Store, season: str, division: int | None = None) -> pd.DataFrame:
    m = store.matches
    m = m[(m.season == season) & (m.stage == "league")]
    return m if division is None else m[m.division == division]


def league_table(store: Store, season: str, division: int = 1, after_round: int | None = None) -> dict:
    m = league_matches(store, season, division)
    if after_round:
        m = m[m["round"] <= after_round]
    clubs = sorted(set(m.home_id) | set(m.away_id))
    rows = {c: {"club_id": c, "club": store.club_name(c), "played": 0, "won": 0, "drawn": 0, "lost": 0,
                "gf": 0, "ga": 0, "points": 0} for c in clubs}
    for r in m.itertuples():
        for c, gf, ga in ((r.home_id, r.home_goals, r.away_goals), (r.away_id, r.away_goals, r.home_goals)):
            x = rows[c]
            x["played"] += 1
            x["gf"] += gf
            x["ga"] += ga
            x["points"] += 3 if gf > ga else (1 if gf == ga else 0)
            x["won" if gf > ga else ("drawn" if gf == ga else "lost")] += 1
    table = sorted(rows.values(), key=lambda r: (-r["points"], -(r["gf"] - r["ga"]), -r["gf"], r["club"]))
    rules = store.league["rules"]
    n = len(table)
    for i, r in enumerate(table, 1):
        r["position"] = i
        r["gd"] = r["gf"] - r["ga"]
        zone_ = None
        if division == 1:
            if i <= rules["champions_league_spots"]:
                zone_ = "Champions League"
            elif i <= rules["champions_league_spots"] + rules["europa_league_spots"]:
                zone_ = "Europa League"
            elif i > n - rules["relegation_spots"]:
                zone_ = "Relegation"
        else:
            if i <= rules["automatic_promotion"]:
                zone_ = "Automatic promotion"
            elif rules["playoff_places"][0] <= i <= rules["playoff_places"][1]:
                zone_ = "Playoffs"
            elif i > n - rules["relegation_spots"]:
                zone_ = "Relegation"
        r["zone"] = zone_
    rounds = int(m["round"].max()) if len(m) else 0
    return {"season": season, "division": division, "after_round": after_round or rounds, "table": table}


def form(store: Store, club_id: str, season: str, n: int = 5, venue: str = "all") -> list[dict]:
    tm = store.table("team_match")
    tm = tm[(tm.team_id == club_id) & (tm.season == season) & (tm.stage == "league")]
    if venue == "home":
        tm = tm[tm.is_home]
    elif venue == "away":
        tm = tm[~tm.is_home]
    tm = tm.sort_values("date").tail(n)
    return [{"match_id": r.match_id, "date": r.date, "round": int(r.round), "opponent": store.club_name(r.opponent_id),
             "venue": "H" if r.is_home else "A", "score": f"{int(r.goals_for)}-{int(r.goals_against)}",
             "result": r.result, "xg": round(r.xg, 2), "xga": round(r.opp_xg, 2)} for r in tm.itertuples()]


def head_to_head(store: Store, a: str, b: str) -> dict:
    m = store.matches
    m = m[((m.home_id == a) & (m.away_id == b)) | ((m.home_id == b) & (m.away_id == a))]
    tm = store.table("team_match").set_index(["match_id", "team_id"])
    rows = []
    for r in m.sort_values("date").itertuples():
        xg_h = tm.loc[(r.match_id, r.home_id)].xg if (r.match_id, r.home_id) in tm.index else None
        xg_a = tm.loc[(r.match_id, r.away_id)].xg if (r.match_id, r.away_id) in tm.index else None
        rows.append({"match_id": r.match_id, "season": r.season, "date": r.date, "competition": r.competition,
                     "home": store.club_name(r.home_id), "away": store.club_name(r.away_id),
                     "score": f"{r.home_goals}-{r.away_goals}", "xg": f"{xg_h:.2f}-{xg_a:.2f}" if xg_h is not None else None,
                     "formations": f"{r.home_formation} v {r.away_formation}"})
    return {"club_a": store.club_name(a), "club_b": store.club_name(b), "meetings": rows}


def _metric_block(values: dict, table: pd.DataFrame, names: list[str]) -> list[dict]:
    out = []
    for name in names:
        label, better, _kind = TEAM_METRICS[name]
        v = values.get(name)
        out.append({"metric": name, "label": label, "value": v,
                    "league_median": float(table[name].median()) if name in table else None,
                    "percentile": pct_rank(v, table[name]) if name in table else None,
                    "better": better})
    return out


def club_profile(store: Store, club_id: str, season: str | None = None, venue: str = "all",
                 last_n: int | None = None) -> dict:
    season = season or store.current_season
    cs = store.club_season(club_id, season)
    if cs is None:
        raise ValueError(f"{club_id} has no data for {season}")
    division = int(cs["division"])
    tm = store.table("team_match")
    mine = tm[(tm.team_id == club_id) & (tm.season == season) & (tm.stage == "league")].sort_values("date")
    if venue == "home":
        mine = mine[mine.is_home]
    elif venue == "away":
        mine = mine[~mine.is_home]
    if last_n:
        mine = mine.tail(last_n)
    vals = team_values(mine)
    league = team_season_table(store, season, division, venue=venue, last_n=last_n)
    table = league_table(store, season, division)
    pos = next((r for r in table["table"] if r["club_id"] == club_id), None)
    off = store.offseason
    promoted = any(p["club_id"] == club_id for p in off.get("promoted", [])) and season == store.current_season
    splits = {}
    for v in ("home", "away"):
        sub = tm[(tm.team_id == club_id) & (tm.season == season) & (tm.stage == "league") & (tm.is_home == (v == "home"))]
        splits[v] = {"matches": len(sub), "points_per_match": sub.points.mean(), "goals_for": sub.goals_for.mean(),
                     "goals_against": sub.goals_against.mean(), "xg": sub.xg.mean(), "xga": sub.opp_xg.mean()}
    forms = []
    for f, g in tm[(tm.team_id == club_id) & (tm.stage == "league")].groupby(["season", "formation"]):
        forms.append({"season": f[0], "formation": f[1], "matches": len(g), "won": int((g.result == "W").sum()),
                      "drawn": int((g.result == "D").sum()), "lost": int((g.result == "L").sum()),
                      "points_per_match": g.points.mean(), "xgd_per_match": g.xgd.mean()})
    opp_forms = []
    sub = tm[(tm.team_id == club_id) & (tm.season == season) & (tm.stage == "league")]
    for f, g in sub.groupby("opp_formation"):
        opp_forms.append({"opponent_formation": f, "matches": len(g), "points_per_match": g.points.mean(),
                          "xgd_per_match": g.xgd.mean()})
    prev_cs = None
    if store.seasons.index(season) > 0:
        prev_cs = store.club_season(club_id, store.seasons[store.seasons.index(season) - 1])
    return clean({
        "club_id": club_id, "club": store.club_name(club_id), "season": season, "division": division,
        "competition": cs["competition"], "manager": cs["manager"], "philosophy": cs["manager_philosophy"],
        "formation": cs["formation"], "new_manager_this_season": store.manager_changed(club_id, season),
        "previous_manager": prev_cs["manager"] if prev_cs and store.manager_changed(club_id, season) else None,
        "promoted_this_season": promoted,
        "filter": {"venue": venue, "last_n": last_n, "matches": len(mine)},
        "table_position": pos,
        "record": {"played": len(mine), "won": int((mine.result == "W").sum()), "drawn": int((mine.result == "D").sum()),
                   "lost": int((mine.result == "L").sum()), "goals_for": int(mine.goals_for.sum()),
                   "goals_against": int(mine.goals_against.sum()), "points": int(mine.points.sum())},
        "home_away": splits,
        "attack": _metric_block(vals, league, ["goals_for", "xg", "shots", "sp_xg", "counter_xg", "corners"]),
        "defence": _metric_block(vals, league, ["goals_against", "opp_xg", "opp_shots", "opp_sp_xg",
                                                "opp_counter_xg", "opp_cross_xg", "late_xga_ratio"]),
        "style": _metric_block(vals, league, ["possession", "field_tilt", "ppda", "pressures_per_opp_pass",
                                              "long_pass_share", "crosses", "left_entry_share", "right_entry_share",
                                              "opp_offsides"]),
        "discipline": _metric_block(vals, league, ["fouls", "cards", "turnovers_own_third"]),
        "formations_used": forms,
        "results_by_opponent_formation": opp_forms,
        "recent_form": form(store, club_id, season, 5),
    })


def goals_breakdown(store: Store, club_id: str, side: str = "conceded", season: str | None = None,
                    venue: str = "all", include_chances: bool = True) -> dict:
    """How a club scores or concedes: phase, time, game state, zone, with every goal listed."""
    season = season or store.current_season
    if side not in ("conceded", "scored"):
        raise ValueError("side must be 'conceded' or 'scored'")
    m = store.matches
    league_ids = set(m.loc[(m.season == season) & (m.stage == "league"), "match_id"])
    sh = store.table("shots")
    sh = sh[(sh.season == season) & sh.match_id.isin(league_ids)].copy()
    inverse = {"leading": "trailing", "trailing": "leading", "level": "level"}
    og = sh.kind == "own_goal"
    if side == "conceded":
        goals_mask = sh.is_goal & (np.where(og, sh.team_id, sh.opponent_id) == club_id)
        sh["opp"] = np.where(og, sh.opponent_id, sh.team_id)
        sh["club_home"] = np.where(og, sh.is_home, ~sh.is_home)
        sh["club_state"] = np.where(og, sh.game_state, sh.game_state.map(inverse))
        chances = sh[(sh.kind == "shot") & (sh.opponent_id == club_id)]
    else:
        goals_mask = sh.is_goal & (sh.scoring_team_id == club_id)
        sh["opp"] = np.where(og, sh.team_id, sh.opponent_id)
        sh["club_home"] = np.where(og, ~sh.is_home, sh.is_home)
        sh["club_state"] = np.where(og, sh.game_state.map(inverse), sh.game_state)
        chances = sh[(sh.kind == "shot") & (sh.team_id == club_id)]
    goals = sh[goals_mask]
    if venue in ("home", "away"):
        want = venue == "home"
        goals = goals[goals.club_home == want]
        chances = chances[chances.club_home == want]
    tm = store.table("team_match")
    mine = tm[(tm.team_id == club_id) & (tm.season == season) & (tm.stage == "league")]
    if venue in ("home", "away"):
        mine = mine[mine.is_home == (venue == "home")]
    n_matches = len(mine)
    div = store.division_of(club_id, season)
    div_ids = set(m.loc[(m.season == season) & (m.stage == "league") & (m.division == div), "match_id"])
    lg_share = sh[sh.is_goal & sh.match_id.isin(div_ids)].phase.value_counts(normalize=True)
    by_phase = [{"phase": ph, "label": PHASE_LABELS.get(ph, ph), "goals": int(cnt),
                 "share": cnt / max(1, len(goals)), "league_share": float(lg_share.get(ph, 0.0)),
                 "xg_of_chances": None if ph == "own_goal" else float(chances[chances.phase == ph].xg.sum())}
                for ph, cnt in goals.phase.value_counts().items()]
    by_time = [{"bucket": b, "goals": int((goals.time_bucket == b).sum()),
                "xg_of_chances": float(chances[chances.time_bucket == b].xg.sum())} for b in TIME_BUCKETS]
    goals_list = [{
        "match_id": g.match_id, "event_id": int(g.event_id), "minute": int(g.minute),
        "opponent": store.club_name(g.opp), "venue": "H" if g.club_home else "A", "phase": g.phase,
        "scorer": (store.player_name(g.player_id) or "?") + (" (own goal)" if g.kind == "own_goal" else ""),
        "assist": store.player_name(g.assist_player_id), "assist_type": g.assist_type, "xg": g.xg,
        "body_part": g.body_part, "zone": g.zone, "club_state_before": g.club_state,
    } for g in goals.sort_values(["match_id", "clock_s"]).itertuples()]
    out = {
        "club_id": club_id, "club": store.club_name(club_id), "season": season, "side": side, "venue": venue,
        "matches": n_matches, "goals": len(goals), "goals_per_match": len(goals) / max(1, n_matches),
        "set_piece_share": float(goals.is_set_piece.mean()) if len(goals) else None,
        "league_set_piece_share": float(sh[sh.is_goal & sh.match_id.isin(div_ids)].is_set_piece.mean()),
        "by_phase": sorted(by_phase, key=lambda r: -r["goals"]),
        "by_time": by_time,
        "by_game_state": goals.club_state.value_counts().to_dict(),
        "by_zone": goals[goals.kind == "shot"].zone.value_counts().to_dict(),
        "goals_list": goals_list,
        "zone_note": "Zones are from the shooter's attacking direction.",
    }
    if include_chances:
        big = chances[chances.xg >= 0.3]
        out["chances"] = {"shots": len(chances), "xg": float(chances.xg.sum()), "big_chances": len(big),
                          "xg_by_phase": chances.groupby("phase").xg.sum().to_dict()}
    return clean(out)


def player_profile(store: Store, analyst_cmp, player_id: str, season: str | None = None) -> dict:
    """analyst_cmp(metric) -> comparison table indexed by (season, player_id)."""
    season = season or store.current_season
    pl = store.players[store.players.player_id == player_id]
    if pl.empty:
        raise ValueError(f"Unknown player {player_id}")
    pl = pl.iloc[0]
    club_id = store.player_club(player_id, season)
    year = int(season[:4])
    seasons_out = {}
    for s in store.seasons:
        rows = {}
        for name, metric in PLAYER_METRICS.items():
            if metric.positions and pl.position not in metric.positions:
                continue
            cmp_ = analyst_cmp(name)
            if (s, player_id) not in cmp_.index:
                continue
            r = cmp_.loc[(s, player_id)]
            rows[name] = {"label": metric.label, "value": r.raw, "adjusted_for_team": bool(metric.team_adjust),
                          "position_median": r.peer_median, "percentile": r.percentile, "sample": r.n * (90 if metric.den == "minutes" else 1)}
        if rows:
            ps_row = analyst_cmp("passes_p90").loc[(s, player_id)] if (s, player_id) in analyst_cmp("passes_p90").index else None
            seasons_out[s] = {
                "club": store.club_name(ps_row.team_id) if ps_row is not None else None,
                "division": int(ps_row.division) if ps_row is not None else None,
                "minutes": ps_row.minutes if ps_row is not None else None,
                "matches": ps_row.matches if ps_row is not None else None,
                "starts": ps_row.starts if ps_row is not None else None,
                "goals": ps_row.goals if ps_row is not None else None,
                "assists": ps_row.assists if ps_row is not None else None,
                "metrics": rows,
            }
    return clean({
        "player_id": player_id, "name": pl["name"], "position": pl.position, "age": year - int(pl.birth_year),
        "height_cm": int(pl.height_cm), "preferred_foot": pl.preferred_foot,
        "club_id": club_id, "club": store.club_name(club_id) if club_id else None,
        "seasons": seasons_out,
        "note": "Percentiles compare with players in the same position and division. Rates are shrunk toward the "
                "position median for small samples; some are adjusted for the team's style.",
    })


def player_event_map(store: Store, player_id: str, season: str, kinds: tuple[str, ...] = ("dispossessed",)) -> dict:
    """Where and when a player's chosen events happen (zones and time buckets)."""
    ev = store.events(season, columns=["match_id", "event_id", "period", "minute", "player_id", "type", "outcome",
                                       "x", "y", "under_pressure", "set_piece"])
    ev = ev[ev.player_id.astype(object) == player_id]
    out = {}
    for kind in kinds:
        if kind == "turnover":
            t = ev["type"].astype(str)
            o = ev.outcome.astype(str)
            sub = ev[(t == "dispossessed") | ((t == "pass") & o.isin(["incomplete", "out"]) & ev.set_piece.isna())
                     | ((t == "take_on") & (o == "fail"))]
        else:
            sub = ev[ev["type"].astype(str) == kind]
        mins = sub.minute.to_numpy()
        per = sub.period.to_numpy()
        bucket = np.where(per == 1, np.where(mins < 15, 0, np.where(mins < 30, 1, 2)),
                          np.where(mins < 60, 3, np.where(mins < 75, 4, 5)))
        out[kind] = {"count": len(sub),
                     "by_zone": zone(sub.x, sub.y).value_counts().to_dict() if len(sub) else {},
                     "by_time": {TIME_BUCKETS[i]: int((bucket == i).sum()) for i in range(6)},
                     "under_pressure_share": float(sub.under_pressure.mean()) if len(sub) else None}
    return clean({"player_id": player_id, "player": store.player_name(player_id), "season": season, "maps": out,
                  "zone_note": "Zones are in the player's attacking direction: left/right are his team's left/right."})
