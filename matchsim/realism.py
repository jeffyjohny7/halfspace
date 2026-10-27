"""Realism report: are the synthetic matches football-realistic, and are the planted truths actually visible
in the data?"""

from __future__ import annotations

import json
import math
import os

import pandas as pd

# metric: (low, high, description)
REFERENCE = {
    "goals_per_match": (2.5, 3.2, "Goals per match"),
    "home_win_rate": (0.40, 0.49, "Home win rate"),
    "draw_rate": (0.20, 0.30, "Draw rate"),
    "away_win_rate": (0.26, 0.36, "Away win rate"),
    "shots_per_match": (22.0, 28.5, "Shots per match"),
    "on_target_share": (0.30, 0.38, "Share of shots on target"),
    "xg_per_shot": (0.09, 0.13, "xG per shot"),
    "goals_per_shot": (0.09, 0.13, "Goals per shot"),
    "outside_box_shot_share": (0.28, 0.45, "Share of shots from outside the box"),
    "passes_per_match": (850.0, 1100.0, "Passes per match"),
    "pass_completion": (0.78, 0.86, "Pass completion"),
    "corners_per_match": (8.5, 11.5, "Corners per match"),
    "fouls_per_match": (17.0, 24.0, "Fouls per match"),
    "yellows_per_match": (3.0, 4.8, "Yellow cards per match"),
    "reds_per_match": (0.04, 0.22, "Red cards per match"),
    "penalties_per_match": (0.18, 0.36, "Penalties per match"),
    "penalty_conversion": (0.68, 0.86, "Penalty conversion"),
    "offsides_per_match": (2.5, 5.0, "Offsides per match"),
    "set_piece_goal_share": (0.20, 0.34, "Share of goals from set pieces (incl. penalties)"),
    "late_goal_share": (0.17, 0.30, "Share of goals scored after the 75th minute"),
    "added_time_1h": (1.5, 6.0, "Added time, first half (min)"),
    "added_time_2h": (4.0, 10.0, "Added time, second half (min)"),
    "champion_points": (75.0, 100.0, "Champion's points (38 games)"),  # 38-game Premier League champions: 75-100
    "safety_points": (30.0, 42.0, "17th place points"),
    "bottom_points": (10.0, 35.0, "Bottom club's points"),
    "max_team_possession": (0.55, 0.67, "Highest season possession share"),
    "min_team_possession": (0.33, 0.45, "Lowest season possession share"),
}

# Players and squads (approximate top-flight figures; per 90 minutes unless stated).
SQUAD_REFERENCE = {
    "passes_p90_CB": (40.0, 75.0, "Passes per 90, centre-backs"),
    "passes_p90_FB": (32.0, 65.0, "Passes per 90, full-backs"),
    "passes_p90_MID": (42.0, 80.0, "Passes per 90, central and defensive midfielders"),
    "passes_p90_W": (22.0, 48.0, "Passes per 90, wingers"),
    "passes_p90_ST": (15.0, 36.0, "Passes per 90, strikers"),
    "passes_p90_GK": (16.0, 40.0, "Passes per 90, goalkeepers"),
    "injuries_per_club": (16.0, 45.0, "Injuries per club per season"),
    "days_out_per_injury": (10.0, 35.0, "Average days out per injury"),
    "unavailable_per_match": (1.0, 5.0, "Players injured or suspended per club per match"),
    "suspensions_per_club": (1.0, 8.0, "Suspensions per club per season"),
    # Leaderboards: what a fan sees first on a stats page.
    "top_scorer_goals": (20.0, 37.0, "Top scorer's league goals"),
    "top_assists": (10.0, 22.0, "Most league assists"),
    "top_goals_minus_xg": (0.0, 12.0, "Biggest finishing overperformance (goals minus xG)"),
    "shots_p90_ST": (1.8, 3.4, "Shots per 90, strikers"),
    "shots_p90_W": (1.2, 3.0, "Shots per 90, wingers"),
    "top_shots_p90": (3.0, 5.5, "Most shots per 90 (1,500+ minutes)"),
}
POSITION_GROUPS = {"CB": "CB", "RB": "FB", "LB": "FB", "DM": "MID", "CM": "MID", "RW": "W", "LW": "W",
                   "ST": "ST", "GK": "GK"}

EVENT_COLS = ["match_id", "event_id", "possession_id", "minute", "team_id", "player_id", "type",
              "outcome", "x", "y", "end_x", "end_y", "receiver_id", "under_pressure", "pass_type", "difficulty",
              "xg", "set_piece", "play_pattern", "set_piece_phase", "related_player_id", "card"]


def _in_box(x, y):
    return (x >= 88.5) & ((y - 34).abs() <= 20.16)


def league_metrics(ev: pd.DataFrame, matches: pd.DataFrame, table: pd.DataFrame | None) -> dict:
    n = len(matches)
    m = {}
    m["goals_per_match"] = (matches.home_goals + matches.away_goals).mean()
    m["home_win_rate"] = (matches.home_goals > matches.away_goals).mean()
    m["draw_rate"] = (matches.home_goals == matches.away_goals).mean()
    m["away_win_rate"] = (matches.home_goals < matches.away_goals).mean()
    shots = ev[ev.type == "shot"]
    m["shots_per_match"] = len(shots) / n
    m["on_target_share"] = shots.outcome.isin(["goal", "saved"]).mean()
    m["xg_per_shot"] = shots.xg.mean()
    m["goals_per_shot"] = (shots.outcome == "goal").mean()
    m["outside_box_shot_share"] = (~_in_box(shots.x, shots.y)).mean()
    passes = ev[ev.type == "pass"]
    m["passes_per_match"] = len(passes) / n
    m["pass_completion"] = (passes.outcome == "complete").mean()
    m["corners_per_match"] = ((passes.set_piece == "corner").sum()
                              + (shots.set_piece == "corner").sum()) / n
    m["fouls_per_match"] = (ev.type == "foul").sum() / n
    cards = ev[ev.type == "card"]
    m["yellows_per_match"] = (cards.card == "yellow").sum() / n
    m["reds_per_match"] = cards.card.isin(["red", "second_yellow"]).sum() / n
    pens = shots[shots.set_piece == "penalty"]
    m["penalties_per_match"] = len(pens) / n
    m["penalty_conversion"] = (pens.outcome == "goal").mean() if len(pens) else float("nan")
    m["offsides_per_match"] = (ev.type == "offside").sum() / n
    goals = ev[((ev.type == "shot") & (ev.outcome == "goal")) | (ev.type == "own_goal")]
    m["set_piece_goal_share"] = goals.set_piece_phase.mean()
    m["late_goal_share"] = (goals.minute >= 75).mean()
    m["added_time_1h"] = matches.added_time_1h.mean()
    m["added_time_2h"] = matches.added_time_2h.mean()
    # Possession by share of passes
    pc = passes.groupby(["match_id", "team_id"]).size().rename("p").reset_index()
    tot = pc.groupby("match_id").p.transform("sum")
    pc["share"] = pc.p / tot
    team_poss = pc.groupby("team_id").share.mean()
    m["max_team_possession"] = team_poss.max()
    m["min_team_possession"] = team_poss.min()
    if table is not None and len(table) >= 17:
        t = table.sort_values("position")
        m["champion_points"] = float(t.iloc[0].points)
        m["safety_points"] = float(t.iloc[16].points)
        m["bottom_points"] = float(t.iloc[-1].points)
    return {k: (float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else None)
            for k, v in m.items()}


def squad_metrics(ev: pd.DataFrame, lineups: pd.DataFrame, positions: dict, pub: str, season: str,
                  clubs: set) -> dict:
    m = {}
    lu = lineups[lineups.match_id.isin(set(ev.match_id))].copy()
    lu["group"] = lu.player_id.map(positions).map(POSITION_GROUPS)
    mins = lu.groupby("group").minutes.sum()
    passes = ev[ev.type == "pass"].copy()
    passes["group"] = passes.player_id.astype(str).map(positions).map(POSITION_GROUPS)
    cnt = passes.groupby("group").size()
    for g in ("CB", "FB", "MID", "W", "ST", "GK"):
        if mins.get(g):
            m[f"passes_p90_{g}"] = float(cnt.get(g, 0) / mins[g] * 90)
    m.update(leader_metrics(ev, lu))

    def _csv(name):
        path = os.path.join(pub, name)
        return pd.read_csv(path) if os.path.exists(path) and os.path.getsize(path) else pd.DataFrame()
    inj, sus, news = _csv("injuries.csv"), _csv("suspensions.csv"), _csv("team_news.csv")
    n = max(1, len(clubs))
    if len(inj):
        i = inj[(inj.season == season) & inj.club_id.isin(clubs)]
        m["injuries_per_club"] = len(i) / n
        m["days_out_per_injury"] = float(i.days_out.mean()) if len(i) else None
        m["match_injury_share"] = float(i.match_id.notna().mean()) if len(i) else None
    if len(sus):
        m["suspensions_per_club"] = len(sus[(sus.season == season) & sus.club_id.isin(clubs)]) / n
    if len(news):
        nn = news[(news.season == season) & news.club_id.isin(clubs) & news.status.isin(["injured", "suspended"])]
        games = len(set(ev.match_id)) * 2
        m["unavailable_per_match"] = len(nn) / max(1, games)
    return m


def leader_metrics(ev: pd.DataFrame, lu: pd.DataFrame) -> dict:
    """Goals, assists and shot volume of the leading players (lu carries a 'group' column)."""
    ev = ev.sort_values(["match_id", "event_id"])
    sel = ev[((ev.type == "pass") & (ev.outcome == "complete")) | (ev.type == "shot")].copy()
    for c in ("player_id", "receiver_id", "team_id"):
        sel[c] = sel[c].astype(object)
    is_pass = sel.type == "pass"
    sel["passer"] = sel.player_id.where(is_pass)
    sel["to"] = sel.receiver_id.where(is_pass)
    sel["pteam"] = sel.team_id.where(is_pass)
    sel[["passer", "to", "pteam"]] = sel.groupby(["match_id", "possession_id"])[["passer", "to", "pteam"]].ffill()
    shots = sel[sel.type == "shot"]
    goals = shots[shots.outcome == "goal"]
    assisted = goals[(goals.to == goals.player_id) & (goals.pteam == goals.team_id)]
    g = goals.groupby("player_id").size()
    a = assisted.groupby("passer").size()
    mins = lu.groupby("player_id").minutes.sum()
    n_shots = shots.groupby("player_id").size()
    xg = shots.groupby("player_id").xg.sum()
    regular = mins[mins >= 1500]
    sh90 = (n_shots.reindex(regular.index).fillna(0) / regular * 90)
    def p90(group):
        rows = lu[lu.group == group]
        n = shots.player_id.isin(set(rows.player_id)).sum()   # players rarely change position group
        return float(n / rows.minutes.sum() * 90) if rows.minutes.sum() else None
    return {
        "top_scorer_goals": float(g.max()) if len(g) else None,
        "top_assists": float(a.max()) if len(a) else None,
        "top_goals_minus_xg": float((g.reindex(xg.index).fillna(0) - xg).max()) if len(xg) else None,
        "shots_p90_ST": p90("ST"),
        "shots_p90_W": p90("W"),
        "top_shots_p90": float(sh90.max()) if len(sh90) else None,
    }


# Signal checks


def _z(value, peers):
    """Robust z-score: (value - median) / (1.4826 * MAD), so planted outliers in the peer group do not hide
    each other."""
    peers = pd.Series(peers).dropna()
    if len(peers) < 4 or value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    med = peers.median()
    mad = (peers - med).abs().median() * 1.4826
    if not mad:
        mad = peers.std()
    if not mad:
        return None
    return float((value - med) / mad)


def _player_minutes(lineups: pd.DataFrame) -> pd.Series:
    return lineups.groupby("player_id").minutes.sum()


def player_metrics(ev: pd.DataFrame, lineups: pd.DataFrame, positions: dict) -> pd.DataFrame:
    mins = _player_minutes(lineups)
    pressed = ev[ev.type == "pressure"].groupby("related_player_id").size()
    disp = ev[ev.type == "dispossessed"].groupby("player_id").size()
    aer = ev[ev.type == "aerial_duel"]
    aer_won = aer[aer.outcome == "won"].groupby("player_id").size()
    aer_all = aer.groupby("player_id").size()
    passes = ev[(ev.type == "pass") & ev.difficulty.notna() & (ev.pass_type != "cross")]
    p_cnt = passes.groupby("player_id").size()
    p_cox = passes.assign(c=(passes.outcome == "complete").astype(float) - (1 - passes.difficulty)) \
        .groupby("player_id").c.mean()
    shots = ev[ev.type == "shot"]
    s_cnt = shots.groupby("player_id").size()
    gmx = shots.assign(g=(shots.outcome == "goal").astype(float) - shots.xg).groupby("player_id").g.sum()
    crosses = ev[(ev.type == "pass") & (ev.pass_type == "cross") & ev.set_piece.isna()]
    c_cnt = crosses.groupby("player_id").size()
    c_rate = crosses.assign(c=(crosses.outcome == "complete").astype(float)).groupby("player_id").c.mean()
    fouls = ev[ev.type == "foul"].groupby("player_id").size()
    cards = ev[ev.type == "card"].groupby("player_id").size()
    claims = ev[ev.type == "gk_claim"].groupby("player_id").size()
    df = pd.DataFrame({"minutes": mins})
    df["position"] = df.index.map(positions)
    df["pressed"] = pressed
    df["dispossessed"] = disp
    df["disp_per_press"] = df.dispossessed.fillna(0) / df.pressed
    df["aerials"] = aer_all
    df["aerial_win_rate"] = aer_won.reindex(df.index).fillna(0) / df.aerials
    df["passes"] = p_cnt
    df["completion_over_expected"] = p_cox
    df["shots"] = s_cnt
    df["goals_minus_xg_per_shot"] = gmx / df.shots
    df["crosses"] = c_cnt
    df["cross_completion"] = c_rate
    df["fouls_cards_per90"] = (fouls.reindex(df.index).fillna(0) + cards.reindex(df.index).fillna(0)) / df.minutes * 90
    df["claims_per90"] = claims.reindex(df.index).fillna(0) / df.minutes * 90
    return df


def _sp(shots: pd.DataFrame) -> pd.Series:
    """Shots from corner and free-kick deliveries (direct free kicks and penalties excluded)."""
    return (shots.set_piece_phase.fillna(False) & shots.play_pattern.isin(["from_corner", "from_free_kick"])
            & ~shots.set_piece.isin(["penalty", "free_kick"]))


def team_metrics(ev: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    shots = ev[ev.type == "shot"]
    goals = ev[((ev.type == "shot") & (ev.outcome == "goal")) | (ev.type == "own_goal")]
    passes = ev[ev.type == "pass"]
    for cid in pd.unique(pd.concat([matches.home_id, matches.away_id])):
        mm = matches[(matches.home_id == cid) | (matches.away_id == cid)]
        ids = set(mm.match_id)
        n = len(mm)
        sh_for = shots[(shots.team_id == cid) & shots.match_id.isin(ids)]
        sh_ag = shots[(shots.team_id != cid) & shots.match_id.isin(ids)]
        ga = goals[goals.match_id.isin(ids) & (((goals.team_id != cid) & (goals.type == "shot"))
                                               | ((goals.team_id == cid) & (goals.type == "own_goal")))]
        late_xga = sh_ag[sh_ag.minute >= 75].xg.sum() / max(1, n) / 15
        early_xga = sh_ag[sh_ag.minute < 75].xg.sum() / max(1, n) / 75
        p_own = passes[(passes.team_id == cid) & passes.match_id.isin(ids)]
        p_opp = passes[(passes.team_id != cid) & passes.match_id.isin(ids)]
        ft = p_own[(p_own.end_x > 70) & (p_own.outcome == "complete")]
        home = mm[mm.home_id == cid]
        away = mm[mm.away_id == cid]

        def xgd(df, is_home):
            if not len(df):
                return float("nan")
            ids_ = set(df.match_id)
            f_ = shots[shots.match_id.isin(ids_) & (shots.team_id == cid)].xg.sum()
            a_ = shots[shots.match_id.isin(ids_) & (shots.team_id != cid)].xg.sum()
            return float((f_ - a_) / len(df))

        def ppg(df, is_home):
            if not len(df):
                return float("nan")
            gf = df.home_goals if is_home else df.away_goals
            gaa = df.away_goals if is_home else df.home_goals
            return float((3 * (gf > gaa) + (gf == gaa)).mean())

        pressures = ev[(ev.type == "pressure") & (ev.team_id == cid) & ev.match_id.isin(ids)]
        rows[cid] = {
            "matches": n,
            "sp_xga_per_match": sh_ag[_sp(sh_ag)].xg.sum() / n,
            "sp_xg_per_match": sh_for[_sp(sh_for)].xg.sum() / n,
            "late_xga_ratio": late_xga / early_xga if early_xga else float("nan"),
            "late_goals_conceded_share": (ga.minute >= 75).mean() if len(ga) else float("nan"),
            "opp_offsides_per_match": ((ev.type == "offside") & (ev.team_id != cid) & ev.match_id.isin(ids)).sum() / n,
            "counter_xga_per_match": sh_ag[sh_ag.play_pattern == "counter"].xg.sum() / n,
            "fouls_per_match": ((ev.type == "foul") & (ev.team_id == cid) & ev.match_id.isin(ids)).sum() / n,
            "home_minus_away_ppg": ppg(home, True) - ppg(away, False),
            "home_minus_away_xgd": xgd(home, True) - xgd(away, False),
            "left_entry_share": (ft.end_y > 45.33).mean() if len(ft) else float("nan"),
            "right_entry_share": (ft.end_y < 22.67).mean() if len(ft) else float("nan"),
            "pressures_per_opp_pass": len(pressures) / max(1, len(p_opp)),
            "long_pass_share": p_own.pass_type.isin(["long"]).mean() if len(p_own) else float("nan"),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


# truth trait -> (scope, metric, direction expected: +1 high, -1 low, min sample column, min sample)
SIGNALS = {
    "loses_ball_under_pressure": ("player", "disp_per_press", +1, "pressed", 40),
    "press_resistant_playmaker": ("player", "disp_per_press", -1, "pressed", 40),
    "weak_in_the_air": ("player", "aerial_win_rate", -1, "aerials", 15),
    "error_prone_passer": ("player", "completion_over_expected", -1, "passes", 200),
    "clinical_finisher": ("player", "goals_minus_xg_per_shot", +1, "shots", 15),
    "elite_crosser": ("player", "cross_completion", +1, "crosses", 15),
    "hothead": ("player", "fouls_cards_per90", +1, "minutes", 600),
    "goalkeeper_weak_on_crosses": ("player", "claims_per90", -1, "minutes", 600),
    "set_piece_defense_weak": ("team", "sp_xga_per_match", +1, "matches", 5),
    "set_piece_attack_strong": ("team", "sp_xg_per_match", +1, "matches", 5),
    "late_fade": ("team", "late_xga_ratio", +1, "matches", 5),
    "high_line_exposed": ("team", "opp_offsides_per_match", +1, "matches", 5),
    "poor_discipline": ("team", "fouls_per_match", +1, "matches", 5),
    "fortress_home": ("team", "home_minus_away_xgd", +1, "matches", 8),
    "left_flank_focus": ("team", "left_entry_share", +1, "matches", 5),
    "right_flank_focus": ("team", "right_entry_share", +1, "matches", 5),
    "style_change_press_intensity": ("team", "pressures_per_opp_pass", 0, "matches", 5),
    "style_change_directness": ("team", "long_pass_share", 0, "matches", 5),
}


def signal_checks(truths, ev, matches, lineups, positions, prev_team: pd.DataFrame | None = None) -> list[dict]:
    pm = player_metrics(ev, lineups, positions)
    tm = team_metrics(ev, matches)
    out = []
    for t in truths:
        trait = t.trait
        if trait not in SIGNALS:
            continue
        scope, metric, sign, sample_col, min_n = SIGNALS[trait]
        row = {"truth_id": t.truth_id, "trait": trait, "club": t.club_name,
               "player": t.player_name, "position": t.position, "planted": t.planted,
               "metric": metric}
        if scope == "player":
            if t.player_id not in pm.index:
                row.update(value=None, peer_mean=None, z=None, sample=0, detectable=False)
                out.append(row)
                continue
            me = pm.loc[t.player_id]
            peers = pm[(pm.position == t.position) & (pm[sample_col] >= min_n)]
            if trait == "goalkeeper_weak_on_crosses":
                peers = pm[(pm.position == "GK") & (pm.minutes >= min_n)]
            value, sample = me[metric], me[sample_col]
        else:
            if t.club_id not in tm.index:
                continue
            me = tm.loc[t.club_id]
            peers = tm
            value, sample = me[metric], me[sample_col]
            if sign == 0 and prev_team is not None and t.club_id in prev_team.index:
                before = prev_team.loc[t.club_id][metric]
                row.update(value=round(float(value), 4), before=round(float(before), 4),
                           change=round(float(value - before), 4), sample=int(sample),
                           detectable=abs(value - before) > 0.02 if metric == "long_pass_share"
                           else abs(value - before) > 0.015)
                out.append(row)
                continue
        z = _z(value, peers[metric])
        ok = bool(z is not None and not (isinstance(sample, float) and math.isnan(sample))
                  and sample >= min_n and z * sign >= 1.0)
        row.update(value=None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), 4),
                   peer_mean=round(float(peers[metric].mean()), 4) if len(peers) else None,
                   z=None if z is None else round(z, 2),
                   sample=None if sample is None or (isinstance(sample, float) and math.isnan(sample)) else int(sample),
                   detectable=ok)
        out.append(row)
    return out


# Report


def _load(out_dir: str, season: str) -> pd.DataFrame:
    path = os.path.join(out_dir, "public", "events", f"events_{season}.parquet")
    return pd.read_parquet(path, columns=EVENT_COLS)


def build_report(out_dir: str, prev: str, cur: str, truths_prev, truths_cur) -> dict:
    pub = os.path.join(out_dir, "public")
    matches = pd.read_csv(os.path.join(pub, "matches.csv"))
    lineups = pd.read_csv(os.path.join(pub, "lineups.csv"))
    players = pd.read_csv(os.path.join(pub, "players.csv"))
    standings_df = pd.read_csv(os.path.join(pub, "standings.csv"))
    positions = dict(zip(players.player_id, players.position))

    ev_prev = _load(out_dir, prev)
    ev_cur = _load(out_dir, cur)

    sections = {}
    checks = []
    for label, season, div, ev in (("Top division", prev, 1, ev_prev), ("Second tier", prev, 2, ev_prev),
                                   ("Top division (rounds so far)", cur, 1, ev_cur)):
        mm = matches[(matches.season == season) & (matches.division == div) & (matches.stage == "league")]
        e = ev[ev.match_id.isin(set(mm.match_id))]
        tab = standings_df[(standings_df.season == season) & (standings_df.division == div)]
        full = season == prev
        metrics = league_metrics(e, mm, tab if (full and div == 1) else None)
        sections[f"{label} {season}"] = metrics
        if season == prev and div == 1:
            clubs_d1 = set(mm.home_id) | set(mm.away_id)
            sq = squad_metrics(e, lineups, positions, pub, season, clubs_d1)
            sections[f"Players and squads {season}"] = sq
            metrics_all = {**metrics, **sq}
            for k, (lo, hi, desc) in {**REFERENCE, **SQUAD_REFERENCE}.items():
                v = metrics_all.get(k)
                ok = v is not None and lo <= v <= hi
                checks.append({"metric": k, "description": desc, "value": None if v is None else round(v, 3),
                               "low": lo, "high": hi, "pass": ok})

    # Signal checks: previous season truths on full-season data (both divisions),
    # current-season truths on previous + current data.
    mm_prev = matches[matches.season == prev]
    lu_prev = lineups[lineups.season == prev]
    sig_prev = []
    for div in (1, 2):
        mm_d = mm_prev[(mm_prev.division == div) & (mm_prev.stage == "league")]
        ids = set(mm_d.match_id)
        e = ev_prev[ev_prev.match_id.isin(ids)]
        lu = lu_prev[lu_prev.match_id.isin(ids)]
        clubs_d = set(mm_d.home_id) | set(mm_d.away_id)
        tr = [t for t in truths_prev if t.club_id in clubs_d]
        sig_prev += signal_checks(tr, e, mm_d, lu, positions)
    prev_team_div1 = team_metrics(ev_prev[ev_prev.match_id.isin(set(mm_prev[mm_prev.division == 1].match_id))],
                                  mm_prev[(mm_prev.division == 1) & (mm_prev.stage == "league")])
    mm_cur = matches[matches.season == cur]
    lu_cur = lineups[lineups.season == cur]
    sig_cur = signal_checks(truths_cur, ev_cur, mm_cur, lu_cur, positions, prev_team=prev_team_div1)

    passed = sum(c["pass"] for c in checks)
    planted_prev = [s for s in sig_prev if s["planted"]]
    planted_cur = [s for s in sig_cur if s["planted"]]
    report = {
        "passed": passed, "total": len(checks), "checks": checks, "sections": sections,
        "signals_previous_season": sig_prev, "signals_current_season": sig_cur,
        "detectability": {
            "previous_season": f"{sum(s['detectable'] for s in planted_prev)}/{len(planted_prev)}",
            "current_season_after_rounds": f"{sum(s['detectable'] for s in planted_cur)}/{len(planted_cur)}",
        },
    }
    os.makedirs(os.path.join(out_dir, "reports"), exist_ok=True)
    with open(os.path.join(out_dir, "reports", "realism_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=lambda o: None if isinstance(o, float) and math.isnan(o) else str(o))
    with open(os.path.join(out_dir, "reports", "realism_report.md"), "w", encoding="utf-8") as fh:
        fh.write(_markdown(report, prev, cur))
    return report


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}"
    return str(v)


def _markdown(r: dict, prev: str, cur: str) -> str:
    lines = ["# Realism report", "",
             f"**{r['passed']} of {r['total']}** league-level checks inside real-football ranges "
             f"(top division, {prev}, full season).", "",
             "Ranges are approximate figures for a modern top-flight league and are deliberately wide.", "",
             "| Check | Synthetic | Real-world range | |", "|---|---|---|---|"]
    for c in r["checks"]:
        lines.append(f"| {c['description']} | {_fmt(c['value'])} | {c['low']} - {c['high']} | "
                     f"{'pass' if c['pass'] else 'CHECK'} |")
    lines += ["", "## Do the hidden truths show up in the data?", "",
              "For every planted trait we measure the matching statistic and compare it with peers "
              "(same position for players, same division for teams). *Detectable* means at least one "
              "standard deviation away from peers in the expected direction, on a usable sample.", "",
              f"- Previous season ({prev}, full season): **{r['detectability']['previous_season']}** planted traits detectable",
              f"- Current season ({cur}, rounds played so far): **{r['detectability']['current_season_after_rounds']}** "
              "- smaller sample, so the Scout should also use last season's data.", "",
              f"### {prev}", "", "| Club | Player | Trait | Metric | Value | Peer mean | z | Detectable |",
              "|---|---|---|---|---|---|---|---|"]
    for s in r["signals_previous_season"]:
        if not s["planted"]:
            continue
        lines.append(f"| {s['club']} | {s['player'] or ''} | {s['trait']} | {s['metric']} | {_fmt(s.get('value'))} | "
                     f"{_fmt(s.get('peer_mean'))} | {_fmt(s.get('z'))} | {'yes' if s['detectable'] else 'no'} |")
    lines += ["", f"### {cur} (so far)", "", "| Club | Player | Trait | Metric | Value | Peer mean / before | z / change | Detectable |",
              "|---|---|---|---|---|---|---|---|"]
    for s in r["signals_current_season"]:
        ref = s.get("peer_mean") if "before" not in s else s.get("before")
        zc = s.get("z") if "change" not in s else s.get("change")
        lines.append(f"| {s['club']} | {s['player'] or ''} | {s['trait']}{'' if s['planted'] else ' (natural)'} | "
                     f"{s['metric']} | {_fmt(s.get('value'))} | {_fmt(ref)} | {_fmt(zc)} | "
                     f"{'yes' if s['detectable'] else 'no'} |")
    lines += ["", "## League summaries", ""]
    for name, metrics in r["sections"].items():
        lines += [f"### {name}", "", "| Metric | Value |", "|---|---|"]
        for k, v in metrics.items():
            lines.append(f"| {k} | {_fmt(v)} |")
        lines.append("")
    return "\n".join(lines)
