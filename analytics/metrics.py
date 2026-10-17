"""Season aggregates, metric definitions, shrinkage and peer comparisons.

Small samples lie. Every rate here is shrunk toward the peer median before it
is compared ("empirical Bayes"): a player who lost the ball 3 times in 4
presses is not yet a liability. Comparisons use robust z-scores
(median and MAD), so one extreme player does not hide another.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .store import Store

COUNT_COLS = [
    "minutes", "passes", "passes_completed", "passes_xp_n", "passes_xp_completed", "passes_xp_expected",
    "passes_under_pressure", "passes_under_pressure_completed", "long_passes", "long_passes_completed",
    "progressive_passes", "passes_into_final_third", "passes_into_box", "crosses", "crosses_completed",
    "set_piece_deliveries", "carries", "progressive_carries", "take_ons", "take_ons_won", "xt_added",
    "dispossessed", "turnovers", "turnovers_under_pressure", "turnovers_own_third", "pressures", "tackles",
    "interceptions", "blocks", "clearances", "ball_recoveries", "aerials", "aerials_won", "fouls",
    "fouls_won", "offsides", "saves", "claims", "times_pressed", "shots", "xg", "npxg", "goals",
    "np_goals", "np_shots", "shots_on_target", "headers", "key_passes", "xa", "assists", "own_goals",
    "shots_on_target_faced", "goals_conceded_on_target", "expected_goals_on_target", "crosses_faced",
    "yellow", "red", "cards", "take_ons_faced",
]


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    num: str | tuple[str, str]       # column, or (a, b) meaning a - b
    den: str                         # "minutes" => per 90
    prior: float                     # shrinkage strength in denominator units
    better: str | None               # "high", "low" or None
    unit: str = "rate"               # "per90", "rate", "pct"
    positions: tuple[str, ...] | None = None
    min_den: float = 0.0             # minimum denominator to be a peer
    team_adjust: bool = False        # remove part of the team-wide effect (system, style)
    team_gamma: float = 0.7          # share of the team effect removed


def _m(*a, **k) -> Metric:
    return Metric(*a, **k)


OUTFIELD = ("RB", "CB", "LB", "DM", "CM", "AM", "RW", "LW", "ST")
ATTACKERS = ("ST", "RW", "LW", "AM")

PLAYER_METRICS: dict[str, Metric] = {m.name: m for m in [
    _m("goals_p90", "Non-penalty goals per 90", "np_goals", "minutes", 900, "high", "per90", OUTFIELD, 450),
    _m("npxg_p90", "Non-penalty xG per 90", "npxg", "minutes", 900, "high", "per90", OUTFIELD, 450),
    _m("shots_p90", "Shots per 90", "shots", "minutes", 900, "high", "per90", OUTFIELD, 450),
    _m("xa_p90", "Expected assists per 90", "xa", "minutes", 900, "high", "per90", OUTFIELD, 450),
    _m("key_passes_p90", "Key passes per 90", "key_passes", "minutes", 900, "high", "per90", OUTFIELD, 450),
    _m("xt_p90", "Threat added (xT) per 90", "xt_added", "minutes", 900, "high", "per90", OUTFIELD, 450,
       team_adjust=True),
    _m("progressive_passes_p90", "Progressive passes per 90", "progressive_passes", "minutes", 900, "high", "per90", OUTFIELD, 450),
    _m("progressive_carries_p90", "Progressive carries per 90", "progressive_carries", "minutes", 900, "high", "per90", OUTFIELD, 450),
    _m("passes_p90", "Passes per 90", "passes", "minutes", 900, None, "per90", None, 450),
    _m("pass_completion", "Pass completion", "passes_completed", "passes", 60, "high", "pct", None, 100),
    _m("completion_over_expected", "Pass completion above expected", ("passes_xp_completed", "passes_xp_expected"),
       "passes_xp_n", 150, "high", "pct", OUTFIELD, 100),
    _m("pressured_pass_completion", "Pass completion under pressure", "passes_under_pressure_completed",
       "passes_under_pressure", 40, "high", "pct", OUTFIELD, 30),
    _m("long_pass_completion", "Long pass completion", "long_passes_completed", "long_passes", 30, "high", "pct", None, 20),
    _m("cross_completion", "Open-play cross completion", "crosses_completed", "crosses", 25, "high", "pct", OUTFIELD, 15),
    _m("take_on_success", "Take-on success", "take_ons_won", "take_ons", 20, "high", "pct", OUTFIELD, 10),
    _m("dispossessed_per_pressed", "Ball lost when pressed", "dispossessed", "times_pressed", 40, "low", "pct", OUTFIELD, 25,
       team_adjust=True),
    _m("turnovers_under_pressure_p90", "Turnovers under pressure per 90", "turnovers_under_pressure", "minutes",
       900, "low", "per90", OUTFIELD, 450),
    _m("turnovers_own_third_p90", "Turnovers in own third per 90", "turnovers_own_third", "minutes", 900, "low",
       "per90", OUTFIELD, 450),
    _m("pressures_p90", "Pressures per 90", "pressures", "minutes", 900, None, "per90", OUTFIELD, 450),
    _m("tackles_interceptions_p90", "Tackles + interceptions per 90", ("tackles", "interceptions"), "minutes", 900,
       "high", "per90", OUTFIELD, 450),
    _m("aerial_win_rate", "Aerial duels won", "aerials_won", "aerials", 25, "high", "pct", OUTFIELD, 15),
    _m("aerials_p90", "Aerial duels per 90", "aerials", "minutes", 900, None, "per90", OUTFIELD, 450),
    _m("fouls_cards_p90", "Fouls + cards per 90", ("fouls", "cards"), "minutes", 900, "low", "per90", OUTFIELD, 450,
       team_adjust=True),
    _m("fouls_per_duel", "Fouls + cards per defensive duel", ("fouls", "cards"), "duels", 60, "low", "rate",
       OUTFIELD, 40, team_adjust=True, team_gamma=1.0),
    _m("finishing_over_xg", "Goals minus xG per shot (non-penalty)", ("np_goals", "npxg"), "np_shots", 40, "high",
       "rate", OUTFIELD, 12),
    _m("gk_goals_prevented", "Goals prevented per shot on target", ("expected_goals_on_target", "goals_conceded_on_target"),
       "shots_on_target_faced", 40, "high", "rate", ("GK",), 20),
    _m("gk_claim_rate", "Crosses claimed", "claims", "crosses_faced", 60, "high", "pct", ("GK",), 40),
]}
# Fix: "tackles_interceptions_p90" sums two columns rather than subtracting.
_SUM_METRICS = {"tackles_interceptions_p90", "fouls_cards_p90"}


def numerator(df: pd.DataFrame, metric: Metric) -> pd.Series:
    if isinstance(metric.num, tuple):
        a, b = metric.num
        return df[a] + df[b] if metric.name in _SUM_METRICS else df[a] - df[b]
    return df[metric.num]


def denominator(df: pd.DataFrame, metric: Metric) -> pd.Series:
    return df["minutes"] / 90.0 if metric.den == "minutes" else df[metric.den]


def raw_value(df: pd.DataFrame, metric: Metric) -> pd.Series:
    den = denominator(df, metric)
    return numerator(df, metric) / den.replace(0, np.nan)


def sample(df: pd.DataFrame, metric: Metric) -> pd.Series:
    return df["minutes"] if metric.den == "minutes" else df[metric.den]


# ---------------------------------------------------------------------------
# Player seasons
# ---------------------------------------------------------------------------

def player_seasons(store: Store, league_only: bool = True) -> pd.DataFrame:
    """One row per (season, player): summed counts plus context."""
    pm = store.table("player_match")
    if league_only:
        m = store.matches
        league_ids = set(m.loc[m.stage == "league", "match_id"])
        pm = pm[pm.match_id.isin(league_ids)]
    g = pm.groupby(["season", "player_id"])
    agg = g[COUNT_COLS].sum()
    agg["matches"] = g.size()
    agg["starts"] = g.started.sum()
    agg["team_id"] = g.team_id.first()
    agg = agg.reset_index()
    agg["position"] = agg.player_id.map(store.player_positions)
    cs = store.club_seasons[["season", "club_id", "division"]].rename(columns={"club_id": "team_id"})
    agg = agg.merge(cs, on=["season", "team_id"], how="left")
    agg["name"] = agg.player_id.map(store.player_names)
    agg["club"] = agg.team_id.map(store.club_names)
    agg["duels"] = agg.pressures + agg.take_ons_faced
    return agg


def _robust_scale(values: pd.Series) -> tuple[float, float]:
    v = values.dropna()
    if len(v) < 4:
        return float("nan"), float("nan")
    med = float(v.median())
    mad = float((v - med).abs().median() * 1.4826)
    if not mad or np.isnan(mad):
        mad = float(v.std()) or float("nan")
    return med, mad


def compare_players(ps: pd.DataFrame, metric: Metric) -> pd.DataFrame:
    """Add shrunk value, robust z and percentile for one metric, within
    (season, division, position) peer groups."""
    df = ps.copy()
    if metric.positions:
        df = df[df.position.isin(metric.positions)]
    df["raw"] = raw_value(df, metric)
    df["team_effect"] = 0.0
    if metric.team_adjust:
        # Leave-one-out team rate vs league rate: part of a player's number is the system
        # he plays in. Remove team_gamma of the gap so the comparison is about the player.
        num_all = numerator(df, metric).fillna(0.0)
        den_all = denominator(df, metric).fillna(0.0)
        tot = pd.DataFrame({"season": df.season, "team_id": df.team_id, "division": df.division,
                            "num": num_all, "den": den_all})
        tnum = tot.groupby(["season", "team_id"]).num.transform("sum") - tot.num
        tden = tot.groupby(["season", "team_id"]).den.transform("sum") - tot.den
        lnum = tot.groupby(["season", "division"]).num.transform("sum")
        lden = tot.groupby(["season", "division"]).den.transform("sum")
        loo = tnum / tden.replace(0, np.nan)
        league = lnum / lden.replace(0, np.nan)
        df["team_effect"] = (metric.team_gamma * (loo - league)).fillna(0.0)
        df["raw"] = df["raw"] - df["team_effect"]
    df["n"] = sample(df, metric) / (90.0 if metric.den == "minutes" else 1.0)
    prior = metric.prior / (90.0 if metric.den == "minutes" else 1.0)
    min_n = metric.min_den / (90.0 if metric.den == "minutes" else 1.0)
    out = []
    for _key, grp in df.groupby(["season", "division", "position"]):
        peers = grp[grp.n >= min_n]
        med, _ = _robust_scale(peers.raw)
        if np.isnan(med):
            med = float(grp.raw.median()) if grp.raw.notna().any() else 0.0
        # Beta-binomial style shrinkage: (count + median * prior) / (sample + prior).
        num = numerator(grp, metric).fillna(0.0) - grp.team_effect * denominator(grp, metric).fillna(0.0)
        grp = grp.assign(shrunk=(num + med * prior) / (grp.n + prior))
        pe = grp[grp.n >= min_n]
        pmed, pmad = _robust_scale(pe.shrunk)
        grp = grp.assign(peer_median=pmed, peer_mad=pmad, peer_count=len(pe),
                         z=(grp.shrunk - pmed) / pmad if pmad and not np.isnan(pmad) else np.nan)
        ranks = pe.shrunk.to_numpy()
        grp = grp.assign(percentile=[float((ranks < v).mean() * 100 + (ranks == v).mean() * 50) if len(ranks) else np.nan
                                     for v in grp.shrunk])
        out.append(grp)
    return pd.concat(out) if out else df.assign(shrunk=np.nan, z=np.nan, percentile=np.nan)


# ---------------------------------------------------------------------------
# Team seasons
# ---------------------------------------------------------------------------

TEAM_METRICS: dict[str, tuple[str, str | None, str]] = {
    # name: (label, better, kind)
    "points_per_match": ("Points per match", "high", "mean"),
    "goals_for": ("Goals scored per match", "high", "mean"),
    "goals_against": ("Goals conceded per match", "low", "mean"),
    "xg": ("xG per match", "high", "mean"),
    "opp_xg": ("xG conceded per match", "low", "mean"),
    "xgd": ("xG difference per match", "high", "mean"),
    "shots": ("Shots per match", "high", "mean"),
    "opp_shots": ("Shots conceded per match", "low", "mean"),
    "possession": ("Possession (share of passes)", None, "mean"),
    "field_tilt": ("Field tilt (share of final-third passes)", "high", "mean"),
    "ppda": ("Opponent passes per defensive action (lower = more pressing)", None, "ratio"),
    "pressures_per_opp_pass": ("Pressures per opponent pass", None, "ratio"),
    "long_pass_share": ("Share of long passes (directness)", None, "ratio"),
    "sp_xg": ("Set-piece delivery xG per match", "high", "mean"),
    "opp_sp_xg": ("Set-piece delivery xG conceded per match", "low", "mean"),
    "opp_counter_xg": ("Counter-attack xG conceded per match", "low", "mean"),
    "counter_xg": ("Counter-attack xG per match", "high", "mean"),
    "opp_cross_xg": ("xG conceded from crosses per match", "low", "mean"),
    "late_xga_ratio": ("xG conceded per minute after 75' vs before", "low", "special"),
    "opp_offsides": ("Opponents caught offside per match (high line)", None, "mean"),
    "fouls": ("Fouls per match", "low", "mean"),
    "cards": ("Cards per match", "low", "mean"),
    "turnovers_own_third": ("Turnovers in own third per match", "low", "mean"),
    "left_entry_share": ("Final-third entries down the left", None, "special"),
    "right_entry_share": ("Final-third entries down the right", None, "special"),
    "home_minus_away_xgd": ("Home minus away xG difference per match", None, "special"),
    "corners": ("Corners won per match", "high", "mean"),
    "crosses": ("Open-play crosses per match", None, "mean"),
}


def team_values(tm: pd.DataFrame) -> dict[str, float]:
    """Season values for one team from its team-match rows."""
    n = len(tm)
    if n == 0:
        return {}
    v: dict[str, float] = {}
    for name, (_label, _better, kind) in TEAM_METRICS.items():
        if kind == "mean":
            if name == "points_per_match":
                v[name] = float(tm.points.mean())
            elif name == "cards":
                v[name] = float((tm.yellows + tm.reds).mean())
            else:
                v[name] = float(tm[name].mean())
    v["ppda"] = float(tm.opp_passes_own_60.sum() / max(1.0, tm.def_actions_high.sum()))
    v["pressures_per_opp_pass"] = float(tm.pressures.sum() / max(1.0, tm.opp_passes.sum()))
    v["long_pass_share"] = float(tm.long_passes.sum() / max(1.0, tm.passes.sum()))
    early = (tm.opp_xg - tm.opp_late_xg).sum() / 75.0
    late = tm.opp_late_xg.sum() / 15.0
    v["late_xga_ratio"] = float(late / early) if early > 0 else float("nan")
    entries = tm.entries_left + tm.entries_centre + tm.entries_right
    v["left_entry_share"] = float(tm.entries_left.sum() / max(1.0, entries.sum()))
    v["right_entry_share"] = float(tm.entries_right.sum() / max(1.0, entries.sum()))
    home, away = tm[tm.is_home & ~tm.neutral], tm[~tm.is_home & ~tm.neutral]
    v["home_minus_away_xgd"] = float(home.xgd.mean() - away.xgd.mean()) if len(home) and len(away) else float("nan")
    v["matches"] = float(n)
    return v


def team_season_table(store: Store, season: str, division: int | None = None,
                      venue: str = "all", last_n: int | None = None) -> pd.DataFrame:
    tm = store.table("team_match")
    tm = tm[(tm.season == season) & (tm.stage == "league")]
    if division is not None:
        tm = tm[tm.division == division]
    if venue == "home":
        tm = tm[tm.is_home]
    elif venue == "away":
        tm = tm[~tm.is_home]
    rows = []
    for team_id, grp in tm.groupby("team_id"):
        grp = grp.sort_values("date")
        if last_n:
            grp = grp.tail(last_n)
        rows.append({"team_id": team_id, "division": int(grp.division.iloc[0]), **team_values(grp)})
    df = pd.DataFrame(rows)
    if len(df):
        df["club"] = df.team_id.map(store.club_names)
    return df


def team_z(table: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Robust z of a team metric within its division, with light shrinkage for small samples."""
    out = []
    for _d, grp in table.groupby("division"):
        med, _ = _robust_scale(grp[metric])
        prior = 6.0
        shr = (grp[metric].fillna(med) * grp.matches + med * prior) / (grp.matches + prior)
        pmed, pmad = _robust_scale(shr)
        out.append(grp.assign(shrunk=shr, peer_median=pmed, peer_mad=pmad,
                              z=(shr - pmed) / pmad if pmad and not np.isnan(pmad) else np.nan,
                              percentile=shr.rank(pct=True) * 100))
    return pd.concat(out) if out else table
