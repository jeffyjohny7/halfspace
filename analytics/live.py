"""Live match intelligence over a stream of events."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import rating as rating_mod
from . import xt as xt_mod
from .build import build_shots, enrich
from .store import Store
from .util import clean

WINDOW_S = 600.0   # 10 minutes of play


def window_stats(ev: pd.DataFrame) -> dict:
    """Possession changes, turnovers and passes per possession for a slice of events."""
    minutes = max(1.0, (ev.clock_s.max() - ev.clock_s.min()) / 60.0) if len(ev) else 1.0
    poss = ev.possession_id.nunique() if len(ev) else 0
    passes = int((ev.t == "pass").sum()) if len(ev) else 0
    return {"possessions_per_min": poss / minutes, "turnovers_per_min": float(ev.turnover.sum()) / minutes if len(ev) else 0.0,
            "passes_per_possession": passes / max(1, poss)}


def compute_window_reference(ev: pd.DataFrame, max_matches: int = 120) -> dict:
    """Distribution of 10-minute spells across the league, for the control/chaos index."""
    rows = []
    for i, (_mid, g) in enumerate(ev.groupby(ev.match_id.astype(str), sort=False)):
        if i >= max_matches:
            break
        end = g.clock_s.max()
        start = 0.0
        while start + WINDOW_S <= end:
            w = g[(g.clock_s >= start) & (g.clock_s < start + WINDOW_S)]
            rows.append(window_stats(w))
            start += WINDOW_S / 2
    df = pd.DataFrame(rows)
    return {k: [float(df[k].quantile(q / 100)) for q in range(0, 101, 5)] for k in df.columns}


def _pct_from_quantiles(v: float, qs: list[float]) -> float:
    return float(np.interp(v, qs, np.arange(0, 101, 5)))


class LiveMatch:
    def __init__(self, store: Store, events: pd.DataFrame, meta: dict, lineups: pd.DataFrame,
                 reference: dict | None = None):
        self.store = store
        self.meta = meta
        self.home_id, self.away_id = meta["home_id"], meta["away_id"]
        matches = pd.DataFrame([{"match_id": meta["match_id"], "home_id": self.home_id, "away_id": self.away_id}])
        grid = xt_mod.from_json(store.xt_grid)
        self.ev = enrich(events, grid, matches)
        self.ev["team"] = self.ev.team_id.astype(str)
        self.shots = build_shots(self.ev, meta.get("season", store.current_season), matches)
        self.lineups = lineups
        self.reference = reference
        self.end_clock = float(self.ev.clock_s.max())
        self.rating_actions = rating_mod.actions(self.ev, self.shots, lineups)

    @classmethod
    def showcase(cls, store: Store) -> "LiveMatch":
        ref = None
        try:
            import json
            ref = json.loads(store.derived_path("window_reference.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            pass
        return cls(store, store.showcase_events(), store.showcase_meta, store.showcase_lineups, ref)

    # Helpers
    def upto(self, clock_s: float) -> pd.DataFrame:
        return self.ev[self.ev.clock_s <= clock_s]

    def _name(self, team_id: str) -> str:
        return self.store.club_name(team_id)

    def _clock_label(self, ev: pd.DataFrame) -> dict:
        if ev.empty:
            return {"period": 1, "minute": 0, "display": "0:00"}
        last = ev.iloc[-1]
        return {"period": int(last.period), "minute": int(last.minute),
                "display": f"{int(last.minute)}:{int(last.second):02d}",
                "finished": bool(last.t == "period_end" and last.period == 2)}

    def _team_block(self, ev: pd.DataFrame, shots: pd.DataFrame, team: str) -> dict:
        opp = self.away_id if team == self.home_id else self.home_id
        mine, theirs = ev[ev.team == team], ev[ev.team == opp]
        sh = shots[(shots.team_id == team) & (shots.kind == "shot")]
        goals = int((shots.is_goal & (shots.scoring_team_id == team)).sum())
        passes, opp_passes = mine[mine.t == "pass"], theirs[theirs.t == "pass"]
        f3, of3 = (passes.x >= 70).sum(), (opp_passes.x >= 70).sum()
        def_high = mine[mine.t.isin(["tackle", "interception", "foul"]) & (mine.x >= 42)]
        cards = mine[mine.t == "card"]
        return {
            "team_id": team, "team": self._name(team), "goals": goals,
            "xg": float(sh.xg.sum()), "shots": len(sh), "shots_on_target": int(sh.outcome.isin(["goal", "saved"]).sum()),
            "big_chances": int((sh.xg >= 0.3).sum()),
            "passes": len(passes), "pass_completion": float((passes.o == "complete").mean()) if len(passes) else None,
            "possession": len(passes) / max(1, len(passes) + len(opp_passes)),
            "field_tilt": float(f3 / max(1, f3 + of3)),
            "ppda": float((opp_passes.x <= 63).sum() / max(1, len(def_high))),
            "pressures": int((mine.t == "pressure").sum()),
            "xt": float(mine.xt_added.sum()),
            "box_entries": int(mine.into_box.sum()),
            "corners": int(((mine.t == "pass") & (mine.set_piece.astype(str) == "corner")).sum()),
            "fouls": int((mine.t == "foul").sum()), "offsides": int((mine.t == "offside").sum()),
            "yellow_cards": int((cards.card.astype(str) == "yellow").sum()),
            "red_cards": int(cards.card.astype(str).isin(["red", "second_yellow"]).sum()),
        }

    # State
    def state(self, clock_s: float) -> dict:
        clock_s = min(float(clock_s), self.end_clock)
        ev = self.upto(clock_s)
        shots = self.shots[self.shots.clock_s <= clock_s]
        home, away = self._team_block(ev, shots, self.home_id), self._team_block(ev, shots, self.away_id)
        win = ev[ev.clock_s > clock_s - WINDOW_S]
        wshots = shots[shots.clock_s > clock_s - WINDOW_S]
        last10 = {"home": self._team_block(win, wshots, self.home_id), "away": self._team_block(win, wshots, self.away_id)}
        ws = window_stats(win)
        chaos = None
        if self.reference:
            p1 = _pct_from_quantiles(ws["possessions_per_min"], self.reference["possessions_per_min"])
            p2 = _pct_from_quantiles(ws["turnovers_per_min"], self.reference["turnovers_per_min"])
            p3 = 100 - _pct_from_quantiles(ws["passes_per_possession"], self.reference["passes_per_possession"])
            chaos = (p1 + p2 + p3) / 3
        h10, a10 = last10["home"], last10["away"]
        control = None
        for side, other in ((h10, a10), (a10, h10)):
            if side["possession"] >= 0.58 and side["field_tilt"] >= 0.6:
                control = side["team"]
        label = None if chaos is None else ("chaos" if chaos >= 67 else ("control" if chaos <= 33 else "balanced"))
        return clean({
            "match_id": self.meta["match_id"], "clock_s": clock_s, "clock": self._clock_label(ev),
            "score": {"home": home["goals"], "away": away["goals"], "display": f"{home['team']} {home['goals']}-{away['goals']} {away['team']}"},
            "home": home, "away": away, "last_10_minutes": last10,
            "tempo": {"label": label, "chaos_index": chaos, "team_in_control": control, **ws,
                      "explanation": "Chaos index 0-100 compares the last 10 minutes with every 10-minute spell in "
                                     "last season's league: possession changes, turnovers and passes per possession."},
            "momentum": self.momentum(clock_s),
            "formations": {self._name(self.home_id): self.meta.get("home_formation"),
                           self._name(self.away_id): self.meta.get("away_formation")},
            "substitutions": [{"minute": int(r.minute), "team": self._name(r.team), "off": self.store.player_name(r.player_id),
                               "on": self.store.player_name(r.related_player_id)} for r in ev[ev.t == "substitution"].itertuples()],
        })

    def momentum(self, clock_s: float, block_s: float = 300.0) -> list[dict]:
        """Per 5-minute block: threat (xT) plus 2 x xG for each side; net > 0 favours home."""
        ev = self.upto(clock_s)
        shots = self.shots[(self.shots.clock_s <= clock_s) & (self.shots.kind == "shot")]
        out = []
        start = 0.0
        while start < clock_s:
            e = ev[(ev.clock_s >= start) & (ev.clock_s < start + block_s)]
            s = shots[(shots.clock_s >= start) & (shots.clock_s < start + block_s)]
            h = e[e.team == self.home_id].xt_added.sum() + 2 * s[s.team_id == self.home_id].xg.sum()
            a = e[e.team == self.away_id].xt_added.sum() + 2 * s[s.team_id == self.away_id].xg.sum()
            minute = int(e.minute.min()) if len(e) else int(start // 60)
            out.append({"from_minute": minute, "home": float(h), "away": float(a), "net": float(h - a)})
            start += block_s
        return out

    # Key moments
    def key_moments(self, clock_s: float, since_s: float = 0.0, min_importance: float = 0.0) -> list[dict]:
        clock_s = min(float(clock_s), self.end_clock)
        ev = self.upto(clock_s)
        shots = self.shots[self.shots.clock_s <= clock_s]
        moments: list[dict] = []
        score = {self.home_id: 0, self.away_id: 0}
        pn = self.store.player_name

        def add(r, kind, importance, team, facts, refs):
            moments.append({"moment_id": f"{self.meta['match_id']}:{kind}:{int(r.event_id)}", "clock_s": float(r.clock_s),
                            "minute": int(r.minute), "period": int(r.period), "type": kind, "team": self._name(team),
                            "team_id": team, "importance": round(float(importance), 2), "facts": facts,
                            "event_refs": [{"match_id": self.meta["match_id"], "event_id": int(x)} for x in refs]})

        for r in shots.sort_values("clock_s").itertuples():
            if r.is_goal:
                scorer_team = r.scoring_team_id
                other = self.away_id if scorer_team == self.home_id else self.home_id
                before = (score[scorer_team], score[other])
                score[scorer_team] += 1
                after = (score[scorer_team], score[other])
                ctx = ("equaliser" if after[0] == after[1] else "takes the lead" if before[0] == before[1] else
                       "extends the lead" if before[0] > before[1] else "pulls one back")
                facts = {"scorer": pn(r.player_id), "own_goal": r.kind == "own_goal", "assist": pn(r.assist_player_id),
                         "assist_type": r.assist_type, "phase": r.phase, "xg": r.xg, "body_part": r.body_part,
                         "score_after": f"{score[self.home_id]}-{score[self.away_id]}", "context": ctx}
                refs = [r.event_id] + ([int(r.assist_event_id)] if pd.notna(r.assist_event_id) else [])
                add(r, "goal", 1.0, scorer_team, facts, refs)
            elif r.kind == "shot" and (r.xg >= 0.3 or r.phase == "penalty"):
                kind = "penalty_missed" if r.phase == "penalty" else "big_chance"
                facts = {"shooter": pn(r.player_id), "xg": r.xg, "outcome": r.outcome, "phase": r.phase,
                         "goalkeeper": pn(r.goalkeeper_id), "assist": pn(r.assist_player_id)}
                add(r, kind, 0.55 + 0.4 * min(r.xg, 0.8), r.team_id, facts, [r.event_id])
        for r in ev[ev.t == "card"].itertuples():
            red = str(r.card) in ("red", "second_yellow")
            add(r, "red_card" if red else "yellow_card", 0.9 if red else 0.25, r.team,
                {"player": pn(r.player_id), "card": str(r.card)}, [r.event_id])
        subs = ev[ev.t == "substitution"]
        for r in subs.itertuples():
            if str(r.o) == "injury":
                continue                      # reported with the injury itself
            add(r, "substitution", 0.2, r.team, {"off": pn(r.player_id), "on": pn(r.related_player_id)}, [r.event_id])
        for r in ev[ev.t == "injury"].itertuples():
            off = str(r.o) == "off"
            rep = subs[(subs.player_id.astype(object) == r.player_id) & (subs.o.astype(str) == "injury")]
            facts = {"player": pn(r.player_id), "outcome": "replaced" if off else "carries on",
                     "replaced_by": pn(rep.related_player_id.iloc[0]) if off and len(rep) else None}
            add(r, "injury", 0.55 if off else 0.3, r.team, facts,
                [r.event_id] + ([int(rep.event_id.iloc[0])] if off and len(rep) else []))
        moments += self._swings(ev, shots)
        moments = [m for m in moments if m["clock_s"] > since_s and m["importance"] >= min_importance]
        moments.sort(key=lambda m: m["clock_s"])
        return clean(moments)

    def _swings(self, ev: pd.DataFrame, shots: pd.DataFrame) -> list[dict]:
        """Momentum swings (field tilt in the last 10 minutes crosses 65%) and pressure spells."""
        out = []
        if ev.empty:
            return out
        last_team, last_t = None, -1e9
        t = 300.0
        end = ev.clock_s.max()
        while t <= end:
            w = ev[(ev.clock_s > t - WINDOW_S) & (ev.clock_s <= t)]
            f3 = w[(w.t == "pass") & (w.x >= 70)]
            hf, af = (f3.team == self.home_id).sum(), (f3.team == self.away_id).sum()
            tilt = hf / max(1, hf + af)
            now = self.home_id if tilt >= 0.65 else (self.away_id if tilt <= 0.35 else None)
            # A swing: a new team takes over the territory, or the same team re-asserts after 15+ minutes.
            if now and (hf + af) >= 12 and (now != last_team or t - last_t >= 900):
                last_team, last_t = now, t
                r = w.iloc[-1]
                out.append({"moment_id": f"{self.meta['match_id']}:momentum:{int(r.event_id)}", "clock_s": float(t),
                            "minute": int(r.minute), "period": int(r.period), "type": "momentum_swing",
                            "team": self._name(now), "team_id": now, "importance": 0.45,
                            "facts": {"field_tilt_last_10": float(tilt if now == self.home_id else 1 - tilt),
                                      "final_third_passes": int(hf if now == self.home_id else af)},
                            "event_refs": []})
            s5 = shots[(shots.clock_s > t - 300) & (shots.clock_s <= t) & (shots.kind == "shot")]
            for team in (self.home_id, self.away_id):
                mine = s5[s5.team_id == team]
                if len(mine) >= 3 and mine.xg.sum() >= 0.5:
                    r = mine.iloc[-1]
                    key = f"{self.meta['match_id']}:pressure_spell:{int(r.event_id)}"
                    if not any(o["moment_id"] == key for o in out):
                        out.append({"moment_id": key, "clock_s": float(r.clock_s), "minute": int(r.minute),
                                    "period": int(r.period), "type": "pressure_spell", "team": self._name(team),
                                    "team_id": team, "importance": 0.5,
                                    "facts": {"shots_in_5_minutes": len(mine), "xg_in_5_minutes": float(mine.xg.sum())},
                                    "event_refs": [{"match_id": self.meta["match_id"], "event_id": int(x)}
                                                   for x in mine.event_id]})
            t += 60.0
        return out

    # Predictions
    def measure(self, p: dict, clock_s: float) -> tuple[float, int]:
        """Current value of a prediction's measure, and its sample size."""
        ev = self.upto(clock_s)
        shots = self.shots[(self.shots.clock_s <= clock_s) & (self.shots.kind == "shot")]
        m, sid = p["measure"], p["subject_id"]
        if m == "dispossessed":
            v = int(((ev.t == "dispossessed") & (ev.player_id.astype(object) == sid)).sum())
            return v, v
        if m == "turnovers":
            v = int((ev.turnover & (ev.player_id.astype(object) == sid) & (ev.under_pressure.fillna(False) | (ev.t == "dispossessed"))).sum())
            return v, v
        if m == "aerial_win_rate":
            a = ev[(ev.t == "aerial_duel") & (ev.player_id.astype(object) == sid)]
            return (float((a.o == "won").mean()) if len(a) else float("nan")), len(a)
        if m == "set_piece_xg_for":
            s = shots[(shots.team_id == sid) & shots.phase.isin(["corner", "free_kick"])]
            return float(s.xg.sum()), len(s)
        if m == "counter_xg_for":
            s = shots[(shots.team_id == sid) & (shots.phase == "counter")]
            return float(s.xg.sum()), len(s)
        if m == "late_xg_for":
            s = shots[(shots.team_id == sid) & shots.is_late]
            return float(s.xg.sum()), len(s)
        if m == "offsides_won":
            opp = p.get("opponent_id")
            v = int(((ev.t == "offside") & (ev.team == opp)).sum())
            return v, v
        if m == "fouls_by_opponent":
            v = int(((ev.t == "foul") & (ev.team == sid)).sum())
            return v, v
        raise ValueError(f"Unknown measure {m}")

    def track(self, predictions: list[dict], clock_s: float) -> list[dict]:
        clock_s = min(float(clock_s), self.end_clock)
        ev = self.upto(clock_s)
        minute = float(ev.minute.iloc[-1]) if len(ev) else 0.0
        frac = min(1.0, max(minute, 1.0) / 90.0)
        finished = bool(len(ev) and ev.iloc[-1].t == "period_end" and ev.iloc[-1].period == 2)
        out = []
        for p in predictions:
            value, n = self.measure(p, clock_s)
            kind = p.get("kind", "count_at_least")
            if kind == "rate_at_most":
                if n < p.get("min_sample", 4) or value != value:
                    status = "waiting for a sample"
                elif value <= p["confirm_at"]:
                    status = "confirmed"
                else:
                    status = "not happening" if finished or n >= 8 else "not yet"
                pace = None
            else:
                pace = value / frac
                if value >= p["confirm_at"]:
                    status = "confirmed"
                elif finished:
                    status = "did not happen"
                elif minute < 20:
                    status = "too early"
                elif pace >= p["confirm_at"]:
                    status = "on track"
                else:
                    status = "behind pace"
            out.append({"prediction_id": p["prediction_id"], "label": p["label"], "text": p["text"],
                        "value": value, "sample": n, "confirm_at": p["confirm_at"],
                        "full_match_pace": pace, "status": status, "minute": minute})
        return clean(out)

    # Ratings
    def _played_by(self, clock_s: float) -> pd.DataFrame:
        """Line-up rows of players who have been on the pitch by clock_s (no future substitutions)."""
        ev = self.upto(clock_s)
        came_on = set(ev[ev.t == "substitution"].related_player_id.dropna().astype(str))
        lu = self.lineups
        return lu[(lu.started == True) | lu.player_id.astype(str).isin(came_on)]  # noqa: E712

    def rating(self, player_id: str, clock_s: float) -> dict:
        clock_s = min(float(clock_s), self.end_clock)
        if player_id not in set(self._played_by(clock_s).player_id.astype(str)):
            return {"rating": None, "note": "Has not played yet."}
        a = self.rating_actions
        a = a[(a.player_id == player_id) & (a.clock_s <= clock_s)]
        return clean({"rating": round(float(rating_mod.clamp(rating_mod.BASE + a.delta.sum())), 1),
                      "starts_at": rating_mod.BASE, "why": rating_mod.breakdown(a, top=6),
                      "stats": rating_mod.stat_line(a)}, nd=2)

    def ratings(self, clock_s: float) -> dict:
        clock_s = min(float(clock_s), self.end_clock)
        a = self.rating_actions[self.rating_actions.clock_s <= clock_s]
        r = rating_mod.match_ratings(a, self._played_by(clock_s))
        out = {}
        for team in (self.home_id, self.away_id):
            t = r[r.team_id.astype(str) == team].sort_values("rating", ascending=False)
            out[self._name(team)] = [
                {"player": self.store.player_name(p), "rating": round(float(v), 1),
                 "top_reasons": rating_mod.breakdown(a[a.player_id == p], top=3)}
                for p, v in zip(t.player_id, t.rating)]
        best = r.sort_values("rating", ascending=False).head(1)
        return clean({"minute": self._clock_label(self.upto(clock_s))["minute"], "by_team": out,
                      "highest": None if best.empty else {"player": self.store.player_name(best.player_id.iloc[0]),
                                                          "rating": round(float(best.rating.iloc[0]), 1)},
                      "how": "Everyone starts at 6.0; each action adds or removes a fixed amount (rating_scale)."}, nd=2)

    # Player focus
    def player(self, player_id: str, clock_s: float) -> dict:
        clock_s = min(float(clock_s), self.end_clock)
        ev = self.upto(clock_s)
        me = ev[ev.player_id.astype(object) == player_id]
        pressed = ev[(ev.t == "pressure") & (ev.related_player_id.astype(object) == player_id)]
        shots = self.shots[(self.shots.clock_s <= clock_s) & (self.shots.player_id == player_id) & (self.shots.kind == "shot")]
        kp = self.shots[(self.shots.clock_s <= clock_s) & (self.shots.assist_player_id == player_id)]
        passes = me[me.t == "pass"]
        done = passes[(passes.o == "complete") & passes.difficulty.notna()]
        lu = self.lineups[self.lineups.player_id == player_id]
        subs = ev[ev.t == "substitution"]
        on_pitch = None
        if len(lu):
            r = lu.iloc[0]
            started = bool(r.started)
            came_on = subs[subs.related_player_id.astype(object) == player_id]
            went_off = subs[subs.player_id.astype(object) == player_id]
            sent_off = me[(me.t == "card") & me.card.astype(str).isin(["red", "second_yellow"])]
            on_pitch = (started or len(came_on) > 0) and went_off.empty and sent_off.empty
        hardest = done.sort_values("difficulty", ascending=False).head(1)
        return clean({
            "player_id": player_id, "player": self.store.player_name(player_id), "on_pitch": on_pitch,
            "touches": int(me.t.isin(["pass", "carry", "take_on", "shot", "dispossessed", "clearance", "ball_recovery"]).sum()),
            "passes": len(passes), "pass_completion": float((passes.o == "complete").mean()) if len(passes) else None,
            "progressive_actions": int(me.progressive.sum()), "xt_added": float(me.xt_added.sum()),
            "shots": len(shots), "xg": float(shots.xg.sum()), "goals": int(shots.is_goal.sum()),
            "key_passes": len(kp), "assists": int(kp.is_goal.sum()),
            "times_pressed": len(pressed), "dispossessed": int((me.t == "dispossessed").sum()),
            "aerials_won": int(((me.t == "aerial_duel") & (me.o == "won")).sum()),
            "aerials_lost": int(((me.t == "aerial_duel") & (me.o == "lost")).sum()),
            "tackles": int(((me.t == "tackle") & (me.o == "won")).sum()), "interceptions": int((me.t == "interception").sum()),
            "fouls": int((me.t == "foul").sum()), "cards": [str(c) for c in me[me.t == "card"].card],
            "fastest_shot_kmh": _max_or_none(me[me.t == "shot"], "ball_speed_kmh"),
            "longest_pass_m": float(passes.pass_length.max()) if len(passes) else None,
            "hardest_completed_pass": None if hardest.empty else {
                "difficulty": float(hardest.difficulty.iloc[0]), "minute": int(hardest.minute.iloc[0]),
                "event_id": int(hardest.event_id.iloc[0]), "length_m": float(hardest.pass_length.iloc[0])},
            "pass_difficulty_note": "Difficulty 0-1 = chance an average passer would fail this pass in this context.",
            "match_rating": self.rating(player_id, clock_s),
        })

    def events(self, event_ids: list[int], clock_s: float) -> list[dict]:
        ev = self.upto(clock_s)
        return _event_rows(self.store, ev[ev.event_id.isin(event_ids)])


def _max_or_none(df: pd.DataFrame, col: str) -> float | None:
    if col not in df.columns or df.empty or df[col].isna().all():
        return None
    return float(df[col].max())


def _event_rows(store: Store, ev: pd.DataFrame) -> list[dict]:
    cols = ["match_id", "event_id", "period", "minute", "second", "team_id", "player_id", "type", "outcome", "x", "y",
            "end_x", "end_y", "receiver_id", "pass_type", "difficulty", "xg", "body_part", "set_piece", "play_pattern",
            "related_player_id", "card", "under_pressure", "ball_speed_kmh"]
    rows = []
    for r in ev[[c for c in cols if c in ev.columns]].to_dict("records"):
        r = {k: (None if (isinstance(v, float) and v != v) else (str(v) if hasattr(v, "categories") else v))
             for k, v in r.items()}
        for k in ("match_id", "team_id", "player_id", "type", "outcome", "receiver_id", "pass_type", "body_part",
                  "set_piece", "play_pattern", "related_player_id", "card"):
            if r.get(k) is not None:
                r[k] = str(r[k])
        r["team"] = store.club_name(r["team_id"])
        for k in ("player_id", "receiver_id", "related_player_id"):
            if r.get(k):
                r[k.replace("_id", "")] = store.player_name(r[k])
        rows.append(r)
    return clean(rows)
