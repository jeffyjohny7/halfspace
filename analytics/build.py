"""Batch layer: turn raw events into compact, query-ready tables.

Outputs (data/derived/):
  xt_grid.json        expected-threat grid learned from the previous season
  shots.parquet       every shot and own goal with phase, assist, venue, game state
  player_match.parquet  one row per player per match (counts; per-90s derived later)
  team_match.parquet    one row per team per match
  refs.parquet        example event references per subject and kind (evidence)
  player_ratings.parquet  every player's match rating in every match (rating.py)

Everything here reads data/public only.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import rating, xt
from .store import Store

FINAL_THIRD_X = 70.0
OWN_THIRD_X = 35.0
SET_PIECE_PHASES = ("corner", "free_kick", "direct_free_kick", "penalty", "throw_in")
DELIVERY_PHASES = ("corner", "free_kick")          # set-piece deliveries into the box
TIME_BUCKETS = ["0-15", "16-30", "31-45+", "46-60", "61-75", "76-90+"]


def _s(col: pd.Series) -> pd.Series:
    """Categorical -> plain string series (None stays None)."""
    return col.astype(object).where(col.notna(), None)


def time_bucket(minute: pd.Series, period: pd.Series) -> pd.Series:
    m = minute.to_numpy()
    p = period.to_numpy()
    out = np.where(p == 1, np.where(m < 15, 0, np.where(m < 30, 1, 2)),
                   np.where(m < 60, 3, np.where(m < 75, 4, 5)))
    return pd.Series(np.array(TIME_BUCKETS)[out], index=minute.index)


def shot_phase(ev: pd.DataFrame) -> pd.Series:
    sp = ev.set_piece.astype(str)
    pp = ev.play_pattern.astype(str)
    spp = ev.set_piece_phase.fillna(False).astype(bool)
    return pd.Series(np.select(
        [sp == "penalty", sp == "free_kick", (pp == "from_corner") & spp,
         (pp == "from_free_kick") & spp, (pp == "from_throw_in") & spp, pp == "counter"],
        ["penalty", "direct_free_kick", "corner", "free_kick", "throw_in", "counter"],
        default="open_play"), index=ev.index)


def zone(x: pd.Series, y: pd.Series) -> pd.Series:
    third = np.where(x < OWN_THIRD_X, "defensive_third", np.where(x < FINAL_THIRD_X, "middle_third", "final_third"))
    # y runs from the team's right touchline (0) to its left (68).
    chan = np.where(y < 22.67, "right", np.where(y > 45.33, "left", "centre"))
    return pd.Series(np.char.add(np.char.add(third.astype(str), ":"), chan.astype(str)), index=x.index)


# ---------------------------------------------------------------------------
# Per-event enrichment
# ---------------------------------------------------------------------------

def enrich(ev: pd.DataFrame, grid: np.ndarray, matches: pd.DataFrame) -> pd.DataFrame:
    ev = ev.sort_values(["match_id", "event_id"], kind="stable").reset_index(drop=True)
    t = ev["type"].astype(str)
    out = ev.outcome.astype(str)
    ev["t"] = t
    ev["o"] = out
    ok_move = ((t == "pass") & (out == "complete")) | ((t == "carry") & (out == "complete")) | \
              ((t == "take_on") & (out == "success") & ev.end_x.notna())
    ev["xt_added"] = 0.0
    idx = ok_move & ev.end_x.notna()
    ev.loc[idx, "xt_added"] = (xt.lookup(grid, ev.loc[idx, "end_x"], ev.loc[idx, "end_y"])
                               - xt.lookup(grid, ev.loc[idx, "x"], ev.loc[idx, "y"]))
    # Progressive: moves the ball at least 10 m toward goal (8 m for carries) from outside the
    # defending 40% of the pitch, or completes into the penalty box.
    gain = ev.end_x - ev.x
    into_box_now = (ev.end_x >= 88.5) & ((ev.end_y - 34).abs() <= 20.16) & ~((ev.x >= 88.5) & ((ev.y - 34).abs() <= 20.16))
    ev["progressive"] = ok_move & (t != "take_on") & (ev.x >= 42.0) & (
        ((t == "pass") & (gain >= 10.0)) | ((t == "carry") & (gain >= 8.0)) | into_box_now)
    ev["into_final_third"] = ok_move & (ev.x < FINAL_THIRD_X) & (ev.end_x >= FINAL_THIRD_X)
    ev["into_box"] = ok_move & (ev.end_x >= 88.5) & ((ev.end_y - 34).abs() <= 20.16) & \
        ~((ev.x >= 88.5) & ((ev.y - 34).abs() <= 20.16))
    ev["turnover"] = (t == "dispossessed") | ((t == "pass") & out.isin(["incomplete", "out"])) | \
                     ((t == "take_on") & (out == "fail"))
    ev["open_play_cross"] = (ev.pass_type.astype(str) == "cross") & ev.set_piece.isna()
    m = matches[["match_id", "home_id", "away_id"]]
    ev = ev.merge(m, on="match_id", how="left")
    ev["is_home"] = _s(ev.team_id) == ev.home_id
    ev["opponent_id"] = np.where(ev.is_home, ev.away_id, ev.home_id)
    return ev


# ---------------------------------------------------------------------------
# Shots, goals and assists
# ---------------------------------------------------------------------------

def build_shots(ev: pd.DataFrame, season: str, matches: pd.DataFrame) -> pd.DataFrame:
    t = ev.t
    sel = ev[((t == "pass") & (ev.o == "complete")) | (t == "shot") | (t == "own_goal")].copy()
    is_pass = sel.t == "pass"
    sel["lp_player"] = _s(sel.player_id).where(is_pass)
    sel["lp_receiver"] = _s(sel.receiver_id).where(is_pass)
    sel["lp_team"] = _s(sel.team_id).where(is_pass)
    sel["lp_event"] = sel.event_id.where(is_pass)
    sel["lp_type"] = _s(sel.pass_type).where(is_pass)
    sel["lp_end_x"] = sel.end_x.where(is_pass)
    sel["lp_end_y"] = sel.end_y.where(is_pass)
    keys = [_s(sel.match_id), sel.possession_id]
    ffill_cols = ["lp_player", "lp_receiver", "lp_team", "lp_event", "lp_type", "lp_end_x", "lp_end_y"]
    sel[ffill_cols] = sel.groupby(keys, sort=False)[ffill_cols].ffill()
    sh = sel[sel.t.isin(["shot", "own_goal"])].copy()
    pid = _s(sh.player_id)
    team = _s(sh.team_id)
    assisted = (sh.t == "shot") & (sh.lp_receiver == pid) & (sh.lp_team == team) & sh.lp_player.notna()
    out = pd.DataFrame({
        "season": season,
        "match_id": _s(sh.match_id),
        "event_id": sh.event_id,
        "possession_id": sh.possession_id,
        "period": sh.period,
        "minute": sh.minute,
        "clock_s": sh.clock_s,
        "time_bucket": time_bucket(sh.minute, sh.period),
        "team_id": team,
        "player_id": pid,
        "kind": sh.t,
        "outcome": _s(sh.outcome),
        "x": sh.x, "y": sh.y,
        "xg": sh.xg.fillna(0.0),
        "body_part": _s(sh.body_part),
        "under_pressure": sh.under_pressure.fillna(False),
        "phase": shot_phase(sh),
        "play_pattern": _s(sh.play_pattern),
        "zone": zone(sh.x, sh.y),
        "goalkeeper_id": _s(sh.related_player_id).where(sh.outcome.astype(str).isin(["goal", "saved"])),
        "assist_player_id": sh.lp_player.where(assisted),
        "assist_event_id": sh.lp_event.where(assisted),
        "assist_type": sh.lp_type.where(assisted),
        "score_home_before": sh.score_home, "score_away_before": sh.score_away,
        "is_home": sh.is_home, "opponent_id": sh.opponent_id,
    })
    # Own goals: credit to the other team.
    og = out.kind == "own_goal"
    out["scoring_team_id"] = np.where(og, out.opponent_id, out.team_id)
    out["is_goal"] = (out.outcome == "goal")
    out.loc[og, "phase"] = "own_goal"
    out.loc[og, "xg"] = 0.0
    # Game state from the shooting team's point of view.
    own = np.where(out.is_home, out.score_home_before, out.score_away_before)
    opp = np.where(out.is_home, out.score_away_before, out.score_home_before)
    out["game_state"] = np.select([own > opp, own < opp], ["leading", "trailing"], default="level")
    out["is_set_piece"] = out.phase.isin(SET_PIECE_PHASES)
    out["is_late"] = (out.period == 2) & (out.minute >= 75)
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Player-match table
# ---------------------------------------------------------------------------

def build_player_match(ev: pd.DataFrame, shots: pd.DataFrame, lineups: pd.DataFrame, season: str,
                       matches: pd.DataFrame) -> pd.DataFrame:
    t, o = ev.t, ev.o
    pid = _s(ev.player_id)
    key = [_s(ev.match_id), pid]
    passes = t == "pass"
    has_diff = passes & ev.difficulty.notna() & (ev.pass_type.astype(str) != "cross") & ev.set_piece.isna()
    up = ev.under_pressure.fillna(False).astype(bool)
    pt = ev.pass_type.astype(str)
    cols = {
        "passes": passes,
        "passes_completed": passes & (o == "complete"),
        "passes_xp_n": has_diff,
        "passes_xp_completed": has_diff & (o == "complete"),
        "passes_xp_expected": np.where(has_diff, 1.0 - ev.difficulty.fillna(0.0), 0.0),
        "passes_under_pressure": passes & up,
        "passes_under_pressure_completed": passes & up & (o == "complete"),
        "long_passes": passes & (pt == "long"),
        "long_passes_completed": passes & (pt == "long") & (o == "complete"),
        "progressive_passes": passes & ev.progressive,
        "passes_into_final_third": passes & ev.into_final_third,
        "passes_into_box": passes & ev.into_box,
        "crosses": ev.open_play_cross,
        "crosses_completed": ev.open_play_cross & (o == "complete"),
        "set_piece_deliveries": passes & ev.set_piece.astype(str).isin(["corner", "free_kick"]) & (pt == "cross"),
        "carries": t == "carry",
        "progressive_carries": (t == "carry") & ev.progressive,
        "take_ons": t == "take_on",
        "take_ons_won": (t == "take_on") & (o == "success"),
        "xt_added": np.where(t.isin(["pass", "carry", "take_on"]), ev.xt_added, 0.0),
        "dispossessed": t == "dispossessed",
        "turnovers": ev.turnover,
        "turnovers_under_pressure": ev.turnover & (up | (t == "dispossessed")),
        "turnovers_own_third": ev.turnover & (ev.x < OWN_THIRD_X),
        "pressures": t == "pressure",
        "tackles": (t == "tackle") & (o == "won"),
        "interceptions": t == "interception",
        "blocks": t == "block",
        "clearances": t == "clearance",
        "ball_recoveries": t == "ball_recovery",
        "aerials": t == "aerial_duel",
        "aerials_won": (t == "aerial_duel") & (o == "won"),
        "fouls": t == "foul",
        "fouls_won": t == "foul_won",
        "offsides": t == "offside",
        "saves": t == "gk_save",
        "claims": t == "gk_claim",
    }
    df = pd.DataFrame({k: np.asarray(v, dtype=float) for k, v in cols.items()})
    df["match_id"] = key[0].to_numpy()
    df["player_id"] = key[1].to_numpy()
    df = df[df.player_id.notna()]
    agg = df.groupby(["match_id", "player_id"], sort=False).sum().reset_index()

    # Times pressed (pressure events point at the ball carrier).
    pr = ev[t == "pressure"]
    pressed = pr.groupby([_s(pr.match_id), _s(pr.related_player_id)], sort=False).size().rename("times_pressed")
    pressed.index.names = ["match_id", "player_id"]
    # Take-ons faced by each defender (take_on events point at the defender).
    to = ev[t == "take_on"]
    faced = to.groupby([_s(to.match_id), _s(to.related_player_id)], sort=False).size().rename("take_ons_faced")
    faced.index.names = ["match_id", "player_id"]

    # Shooting and chance creation from the shots table.
    s = shots[shots.kind == "shot"]
    shoot = s.groupby(["match_id", "player_id"]).agg(
        shots=("xg", "size"), xg=("xg", "sum"),
        npxg=("xg", lambda v: v[s.loc[v.index, "phase"] != "penalty"].sum()),
        goals=("is_goal", "sum"),
        np_goals=("is_goal", lambda v: v[s.loc[v.index, "phase"] != "penalty"].sum()),
        np_shots=("phase", lambda v: (v != "penalty").sum()),
        shots_on_target=("outcome", lambda v: v.isin(["goal", "saved"]).sum()),
        headers=("body_part", lambda v: (v == "head").sum()))
    a = s[s.assist_player_id.notna()]
    create = a.groupby(["match_id", "assist_player_id"]).agg(
        key_passes=("xg", "size"), xa=("xg", "sum"), assists=("is_goal", "sum"))
    create.index.names = ["match_id", "player_id"]
    og = shots[shots.kind == "own_goal"].groupby(["match_id", "player_id"]).size().rename("own_goals")

    # Goalkeeping: shots on target faced, modelled save difficulty.
    ot = shots[(shots.kind == "shot") & shots.outcome.isin(["goal", "saved"]) & shots.goalkeeper_id.notna()].copy()
    if len(ot):
        bins = np.quantile(ot.xg, np.linspace(0, 1, 11))
        bins = np.unique(bins)
        b = np.clip(np.searchsorted(bins, ot.xg, side="right") - 1, 0, max(0, len(bins) - 2))
        rate = ot.groupby(b).is_goal.mean()
        ot["exp_goal_on_target"] = rate.reindex(b).to_numpy()
    else:
        ot["exp_goal_on_target"] = []
    gk = ot.groupby(["match_id", "goalkeeper_id"]).agg(
        shots_on_target_faced=("xg", "size"), goals_conceded_on_target=("is_goal", "sum"),
        expected_goals_on_target=("exp_goal_on_target", "sum"))
    gk.index.names = ["match_id", "player_id"]

    agg = agg.set_index(["match_id", "player_id"])
    for extra in (pressed, faced, shoot, create, og, gk):
        agg = agg.join(extra, how="outer")
    agg = agg.fillna(0.0).reset_index()

    lu = lineups[(lineups.season == season)].copy()
    lu = lu[lu.player_id.notna() & ~lu.get("rested", pd.Series(False, index=lu.index)).astype(bool)]
    lu = lu[["match_id", "team_id", "player_id", "position", "slot", "started", "minutes", "yellow", "red"]]
    out = lu.merge(agg, on=["match_id", "player_id"], how="left").fillna(
        {c: 0.0 for c in agg.columns if c not in ("match_id", "player_id")})
    out = out[out.minutes > 0]
    # Crosses faced by goalkeepers (opponent crosses scaled by minutes on the pitch).
    cf = ev[ev.pass_type.astype(str) == "cross"]
    crosses_by_team = cf.groupby([_s(cf.match_id), _s(cf.team_id)]).size().rename("crosses").reset_index()
    mm = matches[["match_id", "home_id", "away_id", "added_time_2h"]]
    out = out.merge(mm, on="match_id", how="left")
    out["opponent_id"] = np.where(out.team_id == out.home_id, out.away_id, out.home_id)
    out["is_home"] = out.team_id == out.home_id
    out = out.merge(crosses_by_team.rename(columns={"team_id": "opponent_id", "crosses": "opp_crosses"}),
                    on=["match_id", "opponent_id"], how="left")
    full = 90 + out.added_time_2h.fillna(4)
    out["crosses_faced"] = np.where(out.position == "GK", out.opp_crosses.fillna(0) * (out.minutes / full).clip(0, 1), 0.0)
    out["season"] = season
    out["cards"] = out.yellow + out.red
    out = out.drop(columns=["home_id", "away_id", "added_time_2h", "opp_crosses"])
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Team-match table
# ---------------------------------------------------------------------------

def build_team_match(ev: pd.DataFrame, shots: pd.DataFrame, matches: pd.DataFrame, season: str) -> pd.DataFrame:
    mm = matches[matches.season == season]
    rows = []
    for side in ("home", "away"):
        other = "away" if side == "home" else "home"
        r = pd.DataFrame({
            "season": season, "match_id": mm.match_id, "division": mm.division, "stage": mm.stage,
            "round": mm["round"], "date": mm.date,
            "team_id": mm[f"{side}_id"], "opponent_id": mm[f"{other}_id"], "is_home": side == "home",
            "neutral": mm.neutral.fillna(False).astype(bool),
            "goals_for": mm[f"{side}_goals"], "goals_against": mm[f"{other}_goals"],
            "formation": mm[f"{side}_formation"], "opp_formation": mm[f"{other}_formation"],
            "days_rest": mm[f"{side}_days_rest"], "midweek_europe": mm[f"{side}_midweek_europe"].fillna(False),
            "rotated": mm[f"{side}_rotation"],
        })
        rows.append(r)
    tm = pd.concat(rows, ignore_index=True)
    tm["points"] = np.select([tm.goals_for > tm.goals_against, tm.goals_for == tm.goals_against], [3, 1], 0)
    tm["result"] = np.select([tm.goals_for > tm.goals_against, tm.goals_for == tm.goals_against], ["W", "D"], "L")

    team = _s(ev.team_id)
    mid = _s(ev.match_id)
    t, o = ev.t, ev.o
    def count(mask, name):
        sub = pd.DataFrame({"match_id": mid[mask], "team_id": team[mask]})
        return sub.groupby(["match_id", "team_id"]).size().rename(name)

    passes = t == "pass"
    feats = [
        count(passes, "passes"),
        count(passes & (o == "complete"), "passes_completed"),
        count(passes & (ev.x >= FINAL_THIRD_X), "final_third_passes"),
        count(passes & (ev.pass_type.astype(str) == "long"), "long_passes"),
        count(ev.open_play_cross, "crosses"),
        count(passes & (ev.set_piece.astype(str) == "corner"), "corners"),
        count(t == "pressure", "pressures"),
        count((t == "foul"), "fouls"),
        count((t == "card") & (ev.card.astype(str) == "yellow"), "yellows"),
        count((t == "card") & ev.card.astype(str).isin(["red", "second_yellow"]), "reds"),
        count(t == "offside", "offsides"),
        count(ev.turnover & (ev.x < OWN_THIRD_X), "turnovers_own_third"),
        count(ev.into_final_third & (ev.end_y < 22.67), "entries_right"),
        count(ev.into_final_third & (ev.end_y >= 22.67) & (ev.end_y <= 45.33), "entries_centre"),
        count(ev.into_final_third & (ev.end_y > 45.33), "entries_left"),
        count(ev.into_box, "box_entries"),
        count((t == "aerial_duel"), "aerials"),
        count((t == "aerial_duel") & (o == "won"), "aerials_won"),
        # PPDA pieces: our defensive actions in the opponent's 60% (our frame x >= 42) ...
        count(t.isin(["tackle", "interception", "foul"]) & (ev.x >= 42.0), "def_actions_high"),
        # ... and our passes in our own 60% (used as the opponent's denominator).
        count(passes & (ev.x <= 63.0), "passes_own_60"),
    ]
    xt_sum = pd.DataFrame({"match_id": mid, "team_id": team, "xt": ev.xt_added}).groupby(
        ["match_id", "team_id"]).xt.sum().rename("xt_for")
    feats.append(xt_sum)
    f = pd.concat(feats, axis=1).fillna(0.0).reset_index()
    tm = tm.merge(f, on=["match_id", "team_id"], how="left")

    s = shots[shots.kind == "shot"]
    def shot_agg(df: pd.DataFrame, prefix: str, team_col: str) -> pd.DataFrame:
        g = df.groupby(["match_id", team_col])
        out = pd.DataFrame({
            f"{prefix}shots": g.size(),
            f"{prefix}xg": g.xg.sum(),
            f"{prefix}npxg": g.apply(lambda d: d.loc[d.phase != "penalty", "xg"].sum(), include_groups=False),
            f"{prefix}shots_on_target": g.outcome.apply(lambda v: v.isin(["goal", "saved"]).sum()),
            f"{prefix}sp_xg": g.apply(lambda d: d.loc[d.phase.isin(DELIVERY_PHASES), "xg"].sum(), include_groups=False),
            f"{prefix}counter_xg": g.apply(lambda d: d.loc[d.phase == "counter", "xg"].sum(), include_groups=False),
            f"{prefix}late_xg": g.apply(lambda d: d.loc[d.is_late, "xg"].sum(), include_groups=False),
            f"{prefix}cross_xg": g.apply(lambda d: d.loc[d.assist_type == "cross", "xg"].sum(), include_groups=False),
            f"{prefix}through_xg": g.apply(lambda d: d.loc[d.assist_type == "through", "xg"].sum(), include_groups=False),
        })
        out.index.names = ["match_id", "team_id"]
        return out
    tm = tm.merge(shot_agg(s, "", "team_id").reset_index(), on=["match_id", "team_id"], how="left")
    s_against = s.rename(columns={"team_id": "shooter_team", "opponent_id": "def_team"})
    tm = tm.merge(shot_agg(s_against, "opp_", "def_team").reset_index(), on=["match_id", "team_id"], how="left")
    # Goals by phase and time bucket, for and against (own goals count for the scoring team).
    goals = shots[shots.is_goal]
    for who, col in (("for", "scoring_team_id"), ("against", None)):
        g = goals.copy()
        if who == "against":
            g["club"] = np.where(g.scoring_team_id == g.team_id, g.opponent_id, g.team_id)
        else:
            g["club"] = g[col]
        ph = g.pivot_table(index=["match_id", "club"], columns="phase", values="xg", aggfunc="size", fill_value=0)
        ph.columns = [f"goals_{who}_{c}" for c in ph.columns]
        tb = g.pivot_table(index=["match_id", "club"], columns="time_bucket", values="xg", aggfunc="size", fill_value=0)
        tb.columns = [f"goals_{who}_t{c}" for c in tb.columns]
        both = ph.join(tb, how="outer").reset_index().rename(columns={"club": "team_id"})
        tm = tm.merge(both, on=["match_id", "team_id"], how="left")
    # Opponent-side features for convenience.
    opp = tm[["match_id", "team_id", "passes", "passes_own_60", "offsides", "final_third_passes", "corners",
              "crosses"]].rename(columns={"team_id": "opponent_id", "passes": "opp_passes",
                                          "passes_own_60": "opp_passes_own_60", "offsides": "opp_offsides",
                                          "final_third_passes": "opp_final_third_passes",
                                          "corners": "opp_corners", "crosses": "crosses_faced"})
    tm = tm.merge(opp, on=["match_id", "opponent_id"], how="left")
    tm = tm.fillna({c: 0.0 for c in tm.columns if tm[c].dtype.kind in "fi"})
    tm["possession"] = tm.passes / (tm.passes + tm.opp_passes).replace(0, np.nan)
    tm["field_tilt"] = tm.final_third_passes / (tm.final_third_passes + tm.opp_final_third_passes).replace(0, np.nan)
    tm["ppda"] = tm.opp_passes_own_60 / tm.def_actions_high.replace(0, np.nan)
    tm["pressures_per_opp_pass"] = tm.pressures / tm.opp_passes.replace(0, np.nan)
    tm["long_pass_share"] = tm.long_passes / tm.passes.replace(0, np.nan)
    tm["xgd"] = tm.xg - tm.opp_xg
    goal_cols = [c for c in tm.columns if c.startswith("goals_for_") or c.startswith("goals_against_")]
    tm[goal_cols] = tm[goal_cols].fillna(0).astype(int)
    return tm


# ---------------------------------------------------------------------------
# Evidence references
# ---------------------------------------------------------------------------

def build_refs(ev: pd.DataFrame, shots: pd.DataFrame, season: str, per_kind: int = 6) -> pd.DataFrame:
    t, o = ev.t, ev.o
    player_kinds = {
        "dispossessed": t == "dispossessed",
        "aerial_lost": (t == "aerial_duel") & (o == "lost"),
        "aerial_won": (t == "aerial_duel") & (o == "won"),
        "pass_incomplete": (t == "pass") & o.isin(["incomplete", "out"]) & ev.set_piece.isna(),
        "foul": t == "foul",
        "card": t == "card",
        "cross_complete": ev.open_play_cross & (o == "complete"),
        "gk_claim": t == "gk_claim",
        "turnover_own_third": ev.turnover & (ev.x < OWN_THIRD_X),
        "progressive_pass": ev.progressive & (t == "pass"),
        "take_on_won": (t == "take_on") & (o == "success"),
    }
    parts = []
    for kind, mask in player_kinds.items():
        sub = ev.loc[mask, ["match_id", "event_id", "minute", "player_id"]]
        parts.append(pd.DataFrame({"subject_type": "player", "subject_id": _s(sub.player_id),
                                   "kind": kind, "match_id": _s(sub.match_id),
                                   "event_id": sub.event_id, "minute": sub.minute}))
    sh = shots
    conceding = np.where(sh.scoring_team_id == sh.team_id, sh.opponent_id, sh.team_id)
    team_kinds = {
        "goal_conceded": (sh.is_goal, conceding),
        "goal_scored": (sh.is_goal, sh.scoring_team_id),
        "set_piece_shot_conceded": (sh.phase.isin(DELIVERY_PHASES) & (sh.kind == "shot"), sh.opponent_id),
        "set_piece_shot_for": (sh.phase.isin(DELIVERY_PHASES) & (sh.kind == "shot"), sh.team_id),
        "late_shot_conceded": (sh.is_late & (sh.kind == "shot"), sh.opponent_id),
        "counter_shot_conceded": ((sh.phase == "counter") & (sh.kind == "shot"), sh.opponent_id),
        "cross_shot_conceded": ((sh.assist_type == "cross") & (sh.kind == "shot"), sh.opponent_id),
    }
    for kind, (mask, club) in team_kinds.items():
        mask = np.asarray(mask, dtype=bool)
        parts.append(pd.DataFrame({"subject_type": "team", "subject_id": np.asarray(club)[mask],
                                   "kind": kind, "match_id": sh.match_id[mask].to_numpy(),
                                   "event_id": sh.event_id[mask].to_numpy(), "minute": sh.minute[mask].to_numpy()}))
    for kind, mask in {"foul": t == "foul", "offside_won": t == "offside"}.items():
        sub = ev.loc[mask]
        subj = _s(sub.team_id) if kind == "foul" else sub.opponent_id
        parts.append(pd.DataFrame({"subject_type": "team", "subject_id": np.asarray(subj),
                                   "kind": kind, "match_id": _s(sub.match_id).to_numpy(),
                                   "event_id": sub.event_id.to_numpy(), "minute": sub.minute.to_numpy()}))
    refs = pd.concat(parts, ignore_index=True)
    refs = refs[refs.subject_id.notna()]
    refs = refs.sort_values(["subject_type", "subject_id", "kind", "match_id", "event_id"])
    refs = refs.groupby(["subject_type", "subject_id", "kind"], sort=False).tail(per_kind)
    refs["season"] = season
    return refs.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build_all(data_dir: str = "data", verbose: bool = True) -> dict:
    t0 = time.time()
    store = Store(data_dir)
    store.derived.mkdir(parents=True, exist_ok=True)
    seasons = store.seasons
    matches = store.matches
    log = (lambda *a: print(*a, flush=True)) if verbose else (lambda *a: None)

    log(f"Training expected-threat grid on {seasons[0]} events...")
    train_ev = store.events(seasons[0], columns=["type", "outcome", "x", "y", "end_x", "end_y", "set_piece"])
    grid = xt.train(train_ev)
    del train_ev
    store.derived_path("xt_grid.json").write_text(json.dumps(xt.to_json(grid, seasons[0]), indent=1),
                                                  encoding="utf-8")
    shots_all, pm_all, tm_all, refs_all, ratings_all = [], [], [], [], []
    for season in seasons:
        log(f"Building tables for {season}...")
        ev = enrich(store.events(season), grid, matches)
        shots = build_shots(ev, season, matches)
        shots_all.append(shots)
        pm_all.append(build_player_match(ev, shots, store.lineups, season, matches))
        tm_all.append(build_team_match(ev, shots, matches, season))
        refs_all.append(build_refs(ev, shots, season))
        lu = store.lineups[store.lineups.season == season]
        r = rating.match_ratings(rating.actions(ev, shots, lu), lu)
        r["season"] = season
        ratings_all.append(r)
        if season == seasons[0]:
            from .live import compute_window_reference
            top = ev[ev.match_id.astype(str).str.contains("-D1-")]
            ref = compute_window_reference(top)
            store.derived_path("window_reference.json").write_text(json.dumps(ref, indent=1), encoding="utf-8")
        del ev
    out = {
        "shots": pd.concat(shots_all, ignore_index=True),
        "player_match": pd.concat(pm_all, ignore_index=True),
        "team_match": pd.concat(tm_all, ignore_index=True),
        "refs": pd.concat(refs_all, ignore_index=True),
        "player_ratings": pd.concat(ratings_all, ignore_index=True),
    }
    for name, df in out.items():
        df.to_parquet(store.derived_path(f"{name}.parquet"), index=False)
    summary = {name: len(df) for name, df in out.items()}
    summary["elapsed_s"] = round(time.time() - t0, 1)
    log(json.dumps(summary))
    return summary
