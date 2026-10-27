"""The Scout's evidence engine: find a club's weaknesses, strengths and tendencies.

For each candidate finding we
  1. measure the matching statistic for the player or team,
  2. shrink it toward the peer median (small samples are not trusted),
  3. compare with peers (same position and division) using a robust z-score,
  4. blend in last season when this season's sample is small - each season is
     compared with its own league's peers, so a promoted club's second-tier
     numbers are put in context instead of being taken at face value,
  5. attach a confidence level and example event references.

Category names form a public catalogue of football tendencies. The hidden
answer key is never read here; evaluation/ does that afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .metrics import PLAYER_METRICS, compare_players, player_seasons, team_season_table, team_z, TEAM_METRICS
from .store import Store

CB_ONLY = ("CB",)
WIDE = ("RB", "LB", "RW", "LW")
CREATORS = ("CM", "DM", "AM")
ATTACKERS = ("ST", "RW", "LW", "AM")
DEFENSIVE_OUTFIELD = ("RB", "LB", "CB", "DM", "CM")


@dataclass(frozen=True)
class PlayerCheck:
    category: str
    metric: str
    sign: int                    # +1: finding when metric is high, -1: when low
    direction: str               # weakness | strength | tendency
    positions: tuple[str, ...]
    min_sample: float            # in metric denominator units (minutes for per-90)
    template: str
    ref_kind: str | None
    in_catalogue: bool = True    # part of the answer-key vocabulary


PLAYER_CHECKS = [
    PlayerCheck("loses_ball_under_pressure", "dispossessed_per_pressed", +1, "weakness", DEFENSIVE_OUTFIELD, 25,
                "{name} loses the ball {cur} of the times he is pressed ({pos} median {med}).", "dispossessed"),
    PlayerCheck("press_resistant_playmaker", "dispossessed_per_pressed", -1, "strength", CREATORS, 40,
                "{name} keeps the ball under pressure: dispossessed only {cur} of the times he is pressed ({pos} median {med}).",
                "progressive_pass"),
    PlayerCheck("error_prone_passer", "completion_over_expected", -1, "weakness", ("CB", "DM", "CM"), 150,
                "{name} completes {cur} fewer passes than expected for their difficulty ({pos} median {med}).",
                "pass_incomplete"),
    PlayerCheck("weak_in_the_air", "aerial_win_rate", -1, "weakness", CB_ONLY, 15,
                "{name} wins only {cur} of aerial duels ({pos} median {med}).", "aerial_lost"),
    PlayerCheck("hothead", "fouls_cards_p90", +1, "weakness", DEFENSIVE_OUTFIELD, 450,
                "{name} commits {cur} fouls plus cards per 90, after allowing for his team's style ({pos} median {med}).",
                "foul"),
    PlayerCheck("goalkeeper_weak_on_crosses", "gk_claim_rate", -1, "weakness", ("GK",), 40,
                "Goalkeeper {name} claims only {cur} of crosses he faces (goalkeeper median {med}).", None),
    PlayerCheck("clinical_finisher", "finishing_over_xg", +1, "strength", ATTACKERS, 12,
                "{name} scores {cur} more goals per shot than xG predicts ({pos} median {med}).", None),
    PlayerCheck("elite_crosser", "cross_completion", +1, "strength", WIDE, 15,
                "{name} completes {cur} of open-play crosses ({pos} median {med}).", "cross_complete"),
    # Extra tendencies outside the answer-key catalogue.
    PlayerCheck("creative_hub", "xt_p90", +1, "strength", ("CM", "AM", "RW", "LW", "ST"), 450,
                "{name} adds {cur} expected threat per 90 ({pos} median {med}).", "progressive_pass", False),
    PlayerCheck("strong_in_the_air", "aerial_win_rate", +1, "strength", ("CB", "ST"), 15,
                "{name} wins {cur} of aerial duels ({pos} median {med}).", "aerial_won", False),
    PlayerCheck("wasteful_finisher", "finishing_over_xg", -1, "weakness", ATTACKERS, 12,
                "{name} scores {cur} fewer goals per shot than xG predicts ({pos} median {med}).", None, False),
    PlayerCheck("goalkeeper_shot_stopper", "gk_goals_prevented", +1, "strength", ("GK",), 20,
                "Goalkeeper {name} prevents {cur} goals per shot on target (median {med}).", None, False),
    PlayerCheck("goalkeeper_weak_shot_stopper", "gk_goals_prevented", -1, "weakness", ("GK",), 20,
                "Goalkeeper {name} concedes {cur} more goals per shot on target than expected (median {med}).", None, False),
]


@dataclass(frozen=True)
class TeamCheck:
    category: str
    metric: str
    sign: int
    direction: str
    template: str
    ref_kind: str | None
    in_catalogue: bool = True


TEAM_CHECKS = [
    TeamCheck("set_piece_defense_weak", "opp_sp_xg", +1, "weakness",
              "Concede {cur} xG per match from corners and wide free kicks (league median {med}).",
              "set_piece_shot_conceded"),
    TeamCheck("set_piece_attack_strong", "sp_xg", +1, "strength",
              "Create {cur} xG per match from corners and wide free kicks (league median {med}).", "set_piece_shot_for"),
    TeamCheck("late_fade", "late_xga_ratio", +1, "weakness",
              "Concede chances {cur}x faster after the 75th minute than before (league median {med}x).",
              "late_shot_conceded"),
    TeamCheck("high_line_exposed", "opp_offsides", +1, "weakness",
              "Play a high line: opponents are caught offside {cur} times per match (league median {med}); "
              "balls in behind are their risk.", "offside_won"),
    TeamCheck("poor_discipline", "fouls", +1, "weakness",
              "Commit {cur} fouls per match (league median {med}).", "foul"),
    TeamCheck("fortress_home", "home_minus_away_xgd", +1, "strength",
              "xG difference is {cur} per match better at home than away (league median {med}).", "goal_scored"),
    TeamCheck("left_flank_focus", "left_entry_share", +1, "tendency",
              "{cur} of their final-third entries come down the left (league median {med}).", None),
    TeamCheck("right_flank_focus", "right_entry_share", +1, "tendency",
              "{cur} of their final-third entries come down the right (league median {med}).", None),
    # Outside the answer-key catalogue.
    TeamCheck("vulnerable_to_counters", "opp_counter_xg", +1, "weakness",
              "Concede {cur} xG per match from counter-attacks (league median {med}).", "counter_shot_conceded", False),
    TeamCheck("vulnerable_to_crosses", "opp_cross_xg", +1, "weakness",
              "Concede {cur} xG per match from crosses (league median {med}).", "cross_shot_conceded", False),
    TeamCheck("intense_press", "pressures_per_opp_pass", +1, "tendency",
              "Press hard: {cur} pressures per opponent pass (league median {med}).", None, False),
    TeamCheck("passive_press", "pressures_per_opp_pass", -1, "tendency",
              "Sit off: {cur} pressures per opponent pass (league median {med}).", None, False),
    TeamCheck("direct_style", "long_pass_share", +1, "tendency",
              "Play direct: {cur} of passes are long (league median {med}).", None, False),
    TeamCheck("possession_style", "possession", +1, "tendency",
              "Keep the ball: {cur} of passes in their matches are theirs (league median {med}).", None, False),
]

_VERB_START = ("Create ", "Concede ", "Play ", "Commit ", "Press ", "Sit ", "Keep ")


def _with_club(club: str, text: str) -> str:
    """Team findings always name their club. A subject-less line ("Create 0.45 xG per match...") reached the
    writers as a bare fact, and the model sometimes guessed the wrong club."""
    if text.startswith(_VERB_START):
        return f"{club} {text[0].lower()}{text[1:]}"
    return f"{club}: {text}"


PCT_METRICS = {"dispossessed_per_pressed", "fouls_per_duel", "aerial_win_rate", "gk_claim_rate", "cross_completion",
               "left_entry_share", "right_entry_share", "possession", "long_pass_share", "completion_over_expected"}


def _fmt(metric: str, v: float | None) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    if metric in PCT_METRICS:
        return f"{v * 100:.1f}%" if metric == "completion_over_expected" else f"{v:.0%}"
    if metric == "late_xga_ratio":
        return f"{v:.2f}"
    return f"{v:.2f}" if abs(v) < 10 else f"{v:.1f}"


def confidence(z: float, eff: float, min_sample: float) -> str | None:
    """high = headline claim (safe to show on screen); medium = watch list, to be
    tested live; low = weak signal, only on request."""
    if z is None or np.isnan(z):
        return None
    a = abs(z)
    if a >= 2.5 and eff >= 1.5 * min_sample:
        return "high"
    if a >= 1.5 and eff >= min_sample:
        return "medium"
    if a >= 1.0 and eff >= 0.6 * min_sample:
        return "low"
    return None


CONF_RANK = {"low": 1, "medium": 2, "high": 3}
# How much a previous-season observation counts relative to this season's.
PREV_WEIGHT = {1: 0.5, 2: 0.35}
NEW_MANAGER_FACTOR = 0.6


class Scout:
    def __init__(self, store: Store):
        self.store = store
        self._ps = None
        self._player_cmp: dict[str, pd.DataFrame] = {}
        self._team_tables: dict[str, pd.DataFrame] = {}

    # -- cached comparisons ---------------------------------------------------
    @property
    def ps(self) -> pd.DataFrame:
        if self._ps is None:
            self._ps = player_seasons(self.store)
        return self._ps

    def player_cmp(self, metric: str) -> pd.DataFrame:
        if metric not in self._player_cmp:
            self._player_cmp[metric] = compare_players(self.ps, PLAYER_METRICS[metric]).set_index(["season", "player_id"])
        return self._player_cmp[metric]

    def team_table(self, season: str) -> pd.DataFrame:
        if season not in self._team_tables:
            self._team_tables[season] = team_season_table(self.store, season)
        return self._team_tables[season]

    def _refs(self, subject_type: str, subject_id: str, kind: str | None, seasons: list[str], k: int = 4) -> list[dict]:
        if not kind:
            return []
        r = self.store.table("refs")
        r = r[(r.subject_type == subject_type) & (r.subject_id == subject_id) & (r.kind == kind) & r.season.isin(seasons)]
        r = r.sort_values(["season", "match_id", "event_id"], ascending=[False, False, False]).head(k)
        return [{"match_id": m, "event_id": int(e), "minute": int(mi)} for m, e, mi in zip(r.match_id, r.event_id, r.minute)]

    # -- player findings ------------------------------------------------------
    def _player_findings(self, club_id: str, season: str, blend: bool) -> list[dict]:
        store = self.store
        seasons = store.seasons
        prev = seasons[seasons.index(season) - 1] if blend and seasons.index(season) > 0 else None
        squad = self.ps[(self.ps.season == season) & (self.ps.team_id == club_id)]
        out = []
        for chk in PLAYER_CHECKS:
            metric = PLAYER_METRICS[chk.metric]
            per90 = metric.den == "minutes"
            unit = 90.0 if per90 else 1.0
            cmp_ = self.player_cmp(chk.metric)
            for _, pl in squad[squad.position.isin(chk.positions)].iterrows():
                pid = pl.player_id
                parts = []
                if (season, pid) in cmp_.index:
                    r = cmp_.loc[(season, pid)]
                    parts.append((season, r, 1.0))
                if prev and (prev, pid) in cmp_.index:
                    r = cmp_.loc[(prev, pid)]
                    w = PREV_WEIGHT.get(int(r.division), 0.35) if not np.isnan(r.division) else 0.35
                    parts.append((prev, r, w))
                parts = [(s, r, w) for s, r, w in parts if not np.isnan(r.z) and r.n > 0]
                if not parts:
                    continue
                eff = sum(r.n * w for _s, r, w in parts)
                z = sum(r.z * r.n * w for _s, r, w in parts) / eff
                eff_units = eff * unit
                conf = confidence(chk.sign * z if chk.sign * z > 0 else float("nan"), eff_units, chk.min_sample)
                if conf is None:
                    continue
                cur = parts[0][1] if parts[0][0] == season else None
                ref = cur if cur is not None else parts[0][1]
                seasons_used = [s for s, _r, _w in parts]
                evidence = []
                if chk.category in ("clinical_finisher", "wasteful_finisher"):
                    sh = store.table("shots")
                    g = sh[(sh.player_id == pid) & sh.season.isin(seasons_used) & sh.is_goal].sort_values(
                        ["season", "match_id"], ascending=False).head(4)
                    evidence = [{"match_id": m, "event_id": int(e), "minute": int(mi)}
                                for m, e, mi in zip(g.match_id, g.event_id, g.minute)]
                else:
                    evidence = self._refs("player", pid, chk.ref_kind, seasons_used)
                by_season = {s: {"value": _round(r.raw), "shrunk": _round(r.shrunk), "peer_median": _round(r.peer_median),
                                 "z": _round(r.z, 2), "sample": _round(r.n * unit, 0), "division": int(r.division),
                                 "club_id": r.team_id, "percentile": _round(r.percentile, 0)}
                             for s, r, _w in parts}
                # "completes 12.0% fewer passes", not "-12.0% fewer": the word already carries the sign.
                cur = abs(ref.raw) if " fewer " in chk.template else ref.raw
                text = chk.template.format(name=pl["name"], pos=pl.position,
                                           cur=_fmt(chk.metric, cur), med=_fmt(chk.metric, ref.peer_median))
                if len(parts) > 1 or (parts[0][0] != season):
                    text += " " + _season_note(by_season, season, chk.metric)
                out.append({
                    "finding_id": f"{season}:{pid}:{chk.category}", "scope": "player", "category": chk.category,
                    "direction": chk.direction, "club_id": club_id, "club": store.club_name(club_id),
                    "player_id": pid, "player": pl["name"], "position": pl.position,
                    "metric": chk.metric, "metric_label": metric.label, "z": round(float(z), 2),
                    "confidence": conf, "sample": round(float(eff_units), 1), "seasons_used": seasons_used,
                    "by_season": by_season, "summary": text, "evidence": evidence,
                    "in_catalogue": chk.in_catalogue,
                })
        return out

    # -- team findings --------------------------------------------------------
    def _team_findings(self, club_id: str, season: str, blend: bool) -> list[dict]:
        store = self.store
        seasons = store.seasons
        prev = seasons[seasons.index(season) - 1] if blend and seasons.index(season) > 0 else None
        out = []
        new_manager = store.manager_changed(club_id, season)
        for chk in TEAM_CHECKS:
            parts = []
            for s, base_w in ((season, 1.0), (prev, None)):
                if s is None:
                    continue
                tab = self.team_table(s)
                if club_id not in set(tab.team_id):
                    continue
                zt = team_z(tab, chk.metric).set_index("team_id").loc[club_id]
                if np.isnan(zt.z):
                    continue
                w = base_w if base_w is not None else PREV_WEIGHT.get(int(zt.division), 0.35) * (
                    NEW_MANAGER_FACTOR if new_manager else 1.0)
                parts.append((s, zt, w))
            if not parts:
                continue
            eff = sum(r.matches * w for _s, r, w in parts)
            z = sum(r.z * r.matches * w for _s, r, w in parts) / eff
            signed = chk.sign * z
            conf = confidence(signed if signed > 0 else float("nan"), eff, 6.0)
            if conf is None:
                continue
            ref = parts[0][1]
            seasons_used = [s for s, _r, _w in parts]
            by_season = {s: {"value": _round(r[chk.metric]), "peer_median": _round(r.peer_median),
                             "z": _round(r.z, 2), "matches": int(r.matches), "division": int(r.division)}
                         for s, r, _w in parts}
            text = _with_club(store.club_name(club_id),
                              chk.template.format(cur=_fmt(chk.metric, ref[chk.metric]), med=_fmt(chk.metric, ref.peer_median)))
            if len(parts) > 1 or parts[0][0] != season:
                text += " " + _season_note(by_season, season, chk.metric)
            if new_manager and prev in seasons_used:
                text += " New manager this season, so last season's numbers count for less."
            out.append({
                "finding_id": f"{season}:{club_id}:{chk.category}", "scope": "team", "category": chk.category,
                "direction": chk.direction, "club_id": club_id, "club": store.club_name(club_id),
                "player_id": None, "player": None, "position": None,
                "metric": chk.metric, "metric_label": TEAM_METRICS[chk.metric][0], "z": round(float(z), 2),
                "confidence": conf, "sample": round(float(eff), 1), "seasons_used": seasons_used,
                "by_season": by_season, "summary": text,
                "evidence": self._refs("team", club_id, chk.ref_kind, seasons_used),
                "in_catalogue": chk.in_catalogue,
            })
        out += self._style_change(club_id, season)
        return out

    def _style_change(self, club_id: str, season: str) -> list[dict]:
        """Did a new manager change how the team presses or how direct it plays?"""
        store = self.store
        seasons = store.seasons
        if seasons.index(season) == 0 or not store.manager_changed(club_id, season):
            return []
        prev = seasons[seasons.index(season) - 1]
        cur_t, prev_t = self.team_table(season), self.team_table(prev)
        if club_id not in set(prev_t.team_id) or club_id not in set(cur_t.team_id):
            return []
        both = cur_t.merge(prev_t, on="team_id", suffixes=("", "_prev"))
        both = both[both.division_prev == both.division]
        stable = both[[not store.manager_changed(t, season) for t in both.team_id]]
        out = []
        for metric, cat in (("pressures_per_opp_pass", "style_change_press_intensity"),
                            ("long_pass_share", "style_change_directness")):
            row = both[both.team_id == club_id]
            if row.empty or len(stable) < 5:
                continue
            delta = float(row[metric].iloc[0] - row[f"{metric}_prev"].iloc[0])
            noise = (stable[metric] - stable[f"{metric}_prev"]).abs().median() * 1.4826
            z = delta / noise if noise else float("nan")
            conf = confidence(abs(z), float(row.matches.iloc[0]), 6.0)
            if conf is None:
                continue
            cs_old, cs_new = store.club_season(club_id, prev), store.club_season(club_id, season)
            verb = "more" if delta > 0 else "less"
            label = "pressing" if metric == "pressures_per_opp_pass" else "direct"
            out.append({
                "finding_id": f"{season}:{club_id}:{cat}", "scope": "team", "category": cat, "direction": "change",
                "club_id": club_id, "club": store.club_name(club_id), "player_id": None, "player": None,
                "position": None, "metric": metric, "metric_label": TEAM_METRICS[metric][0],
                "z": round(z, 2), "confidence": conf, "sample": float(row.matches.iloc[0]),
                "seasons_used": [prev, season],
                "by_season": {prev: {"value": _round(row[f"{metric}_prev"].iloc[0])},
                              season: {"value": _round(row[metric].iloc[0])}},
                "summary": (f"Under new manager {cs_new['manager']} ({cs_new['formation']}, replacing "
                            f"{cs_old['manager']}'s {cs_old['formation']}) they are {verb} {label}: "
                            f"{TEAM_METRICS[metric][0].lower()} {_fmt(metric, row[f'{metric}_prev'].iloc[0])} -> "
                            f"{_fmt(metric, row[metric].iloc[0])}."),
                "evidence": [], "in_catalogue": True,
            })
        return out

    # -- public API -----------------------------------------------------------
    def findings(self, club_id: str, season: str | None = None, kind: str = "all",
                 min_confidence: str = "medium", blend: bool = True, include_extra: bool = True) -> list[dict]:
        season = season or self.store.current_season
        res = self._player_findings(club_id, season, blend) + self._team_findings(club_id, season, blend)
        floor = CONF_RANK[min_confidence]
        res = [f for f in res if CONF_RANK[f["confidence"]] >= floor]
        if not include_extra:
            res = [f for f in res if f["in_catalogue"]]
        if kind == "weaknesses":
            res = [f for f in res if f["direction"] == "weakness"]
        elif kind == "strengths":
            res = [f for f in res if f["direction"] == "strength"]
        elif kind == "tendencies":
            res = [f for f in res if f["direction"] in ("tendency", "change")]
        res.sort(key=lambda f: (-CONF_RANK[f["confidence"]], -abs(f["z"])))
        return res


def _round(v, nd: int = 3):
    try:
        if v is None or np.isnan(v):
            return None
    except TypeError:
        return v
    return round(float(v), nd)


def _season_note(by_season: dict, season: str, metric: str) -> str:
    bits = []
    for s, d in by_season.items():
        div = d.get("division")
        league = "" if div in (None, 1) else " in the second tier"
        sample = d.get("sample", d.get("matches"))
        unit = "" if sample is None else (f", {int(sample)} matches" if "matches" in d else f", sample {int(sample)}")
        bits.append(f"{s}{league}: {_fmt(metric, d.get('value'))}{unit}")
    return "(" + "; ".join(bits) + ")"
