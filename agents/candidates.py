"""Turn the live match into candidate on-screen items, each with checkable facts.

Everything here is computed by the analytics engine; the Analyst agent only ranks
and explains these candidates. That keeps every number on screen traceable.
"""

from __future__ import annotations

from analytics.api import Analyst
from analytics.profiles import PHASE_LABELS

from .state import BroadcastState, Candidate

STAT_MARKS = [15, 30, 60, 75]


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.0f}%"


def _edge_for(state: BroadcastState, *, prediction_id: str | None = None, kind: str | None = None,
              beneficiary_id: str | None = None) -> dict | None:
    for e in (state.matchup or {}).get("edges", []):
        if prediction_id and any(p["prediction_id"] == prediction_id for p in e.get("predictions", [])):
            return e
        if kind and e["kind"] == kind and (beneficiary_id is None or e["beneficiary_id"] == beneficiary_id):
            return e
    return None


def _first_sentences(text: str, n: int = 2) -> str:
    parts = [p.strip() for p in text.replace("; ", ". ").split(". ") if p.strip()]
    s = ". ".join(parts[:n])
    return s if s.endswith(".") else s + "."


def _format_value(measure: str, value) -> str:
    if value is None:
        return "n/a"
    if measure == "aerial_win_rate":
        return f"{value * 100:.0f}%"
    if "xg" in measure:
        return f"{value:.2f}"
    return f"{int(value)}"


def build(analyst: Analyst, state: BroadcastState, clock_s: float, focus_player_id: str | None = None) -> list[Candidate]:
    st = analyst.live_state(clock_s)
    minute = int(st["clock"]["minute"])
    home, away = st["home"], st["away"]
    clubs = [state.home, state.away]
    out: list[Candidate] = []
    since = state.last_tick_clock

    # 1. Key moments since the last tick.
    for m in analyst.live_key_moments(clock_s, since_s=since, min_importance=0.4):
        f = m["facts"]
        team = m["team"]
        names = list(clubs)
        refs = m["event_refs"]
        cid = m["moment_id"]
        if m["type"] == "goal":
            scorer = f["scorer"]
            names.append(scorer.replace(" (own goal)", ""))
            facts = [f"{team} {f['context']}: {scorer} scores in minute {m['minute']}. "
                     f"Score: {state.home} {f['score_after']} {state.away}.",
                     f"Chance quality {f['xg']:.2f} xG, from {PHASE_LABELS.get(f['phase'], f['phase']).lower()}."]
            if f.get("assist"):
                names.append(f["assist"])
                facts.append(f"Assist: {f['assist']} ({f['assist_type']} pass).")
            if f["phase"] in ("corner", "free_kick", "direct_free_kick"):
                e = _edge_for(state, kind="set_pieces", beneficiary_id=m["team_id"])
                if e:
                    facts.append("Pre-match scouting: " + _first_sentences(e["explanation"], 2))
            h, a = f["score_after"].split("-")
            out.append(Candidate(cid, "goal", m["clock_s"], m["minute"], 1.0, facts, names, refs,
                                 {"template": "goal", "data": {"team": team, "scorer": scorer, "minute": m["minute"],
                                                               "score": {"home": int(h), "away": int(a)},
                                                               "xg": f["xg"], "assist": f.get("assist")}},
                                 subject=cid, must_show=True))
        elif m["type"] == "red_card":
            names.append(f["player"])
            out.append(Candidate(cid, "red_card", m["clock_s"], m["minute"], 1.0,
                                 [f"{f['player']} ({team}) is sent off in minute {m['minute']}; {team} are down to 10 men."],
                                 names, refs, {"template": "card", "data": {"player": f["player"], "team": team, "card": f["card"]}},
                                 subject=cid, must_show=True))
        elif m["type"] in ("big_chance", "penalty_missed"):
            names.append(f["shooter"])
            what = {"saved": f"saved by {f['goalkeeper']}" if f.get("goalkeeper") else "saved",
                    "off_target": "off target", "blocked": "blocked"}.get(f["outcome"], f["outcome"])
            if f.get("goalkeeper"):
                names.append(f["goalkeeper"])
            label = "Penalty missed" if m["type"] == "penalty_missed" else "Big chance"
            out.append(Candidate(cid, m["type"], m["clock_s"], m["minute"], 0.9 if m["type"] == "penalty_missed" else 0.6,
                                 [f"{label} for {team} in minute {m['minute']}: {f['shooter']}, {f['xg']:.2f} xG, {what}."],
                                 names, refs, {"template": "chance", "data": {"team": team, "player": f["shooter"],
                                                                              "xg": f["xg"], "outcome": f["outcome"]}},
                                 subject=f"chance:{m['team_id']}", must_show=m["type"] == "penalty_missed"))
        elif m["type"] == "momentum_swing":
            tilt = f["field_tilt_last_10"]
            out.append(Candidate(cid, "momentum", m["clock_s"], m["minute"], 0.45,
                                 [f"{team} have {_pct(tilt)} of the final-third passes in the last 10 minutes "
                                  f"({f['final_third_passes']} passes)."],
                                 names, refs, {"template": "momentum", "data": {"team": team, "field_tilt": tilt}},
                                 subject=f"momentum:{m['team_id']}"))
        elif m["type"] == "injury":
            player = f["player"]
            names.append(player)
            if f.get("replaced_by"):
                names.append(f["replaced_by"])
                text = (f"{player} ({team}) goes off injured in minute {m['minute']}; "
                        f"{f['replaced_by']} comes on.")
            else:
                text = f"{player} ({team}) is hurt in minute {m['minute']} but carries on."
            out.append(Candidate(cid, "injury", m["clock_s"], m["minute"], 0.55 if f.get("replaced_by") else 0.3,
                                 [text], names, refs,
                                 {"template": "injury", "data": {"team": team, "player": player,
                                                                 "replaced_by": f.get("replaced_by")}},
                                 subject=f"injury:{player}"))
        elif m["type"] == "pressure_spell":
            out.append(Candidate(cid, "pressure_spell", m["clock_s"], m["minute"], 0.5,
                                 [f"{team}: {f['shots_in_5_minutes']} shots worth {f['xg_in_5_minutes']:.2f} xG in 5 minutes."],
                                 names, refs, {"template": "momentum", "data": {"team": team, **f}},
                                 subject=f"pressure:{m['team_id']}"))

    # 2. Pre-match predictions that have just been confirmed (the spine of the product).
    for p in analyst.live_predictions(clock_s):
        prev = state.prediction_status.get(p["prediction_id"])
        state.prediction_status[p["prediction_id"]] = p["status"]
        if p["status"] != "confirmed" or prev == "confirmed":
            continue
        full = next((x for x in (state.matchup or {}).get("predictions_to_track", [])
                     if x["prediction_id"] == p["prediction_id"]), None)
        measure = full["measure"] if full else ""
        value = _format_value(measure, p["value"])
        names = list(clubs)
        if full and full["subject_type"] == "player":
            names.append(full["subject"])
        facts = [f"Pre-match prediction: {p['text']}",
                 f"Live, minute {int(p['minute'])}: {p['label']} = {value}"
                 + (f" from {p['sample']} duels." if measure == "aerial_win_rate" else ".")]
        e = _edge_for(state, prediction_id=p["prediction_id"])
        if e:
            facts.append("Why the Scout flagged it: " + _first_sentences(e["explanation"], 2))
            names += [n for n in (e.get("beneficiary"), e.get("opponent")) if n]
        out.append(Candidate(f"pred:{p['prediction_id']}:{int(clock_s)}", "prediction_confirmed", clock_s, minute, 0.85,
                             facts, names, [],
                             {"template": "prediction_tracker",
                              "data": {"label": p["label"], "value": p["value"], "confirm_at": p["confirm_at"],
                                       "expected_if_trait_holds": full and full.get("expected_if_trait_holds"),
                                       "expected_average": full and (full.get("expected_average_player")
                                                                     or full.get("expected_average")),
                                       "status": "confirmed"}},
                             subject=f"prediction:{p['prediction_id']}"))

    # 3. Tempo: the game turns chaotic or one side takes control.
    tempo = st["tempo"]
    last_label, last_clock = state.last_tempo or (None, -1e9)
    if (tempo["label"] in ("chaos", "control") and minute >= 10
            and (tempo["label"] != last_label or clock_s - last_clock >= 1200)):
        state.last_tempo = (tempo["label"], clock_s)
        facts = [f"Last 10 minutes: chaos index {tempo['chaos_index']:.0f} out of 100, "
                 f"{tempo['possessions_per_min']:.1f} changes of possession per minute."]
        if tempo.get("team_in_control"):
            side = "home" if tempo["team_in_control"] == state.home else "away"
            l10 = st["last_10_minutes"][side]
            facts.append(f"{tempo['team_in_control']} in control: {_pct(l10['possession'])} of the ball and "
                         f"{_pct(l10['field_tilt'])} of final-third passes in the last 10 minutes.")
        out.append(Candidate(f"tempo:{int(clock_s)}", "tempo", clock_s, minute, 0.4, facts, list(clubs), [],
                             {"template": "tempo", "data": {"label": tempo["label"], "chaos_index": tempo["chaos_index"],
                                                            "team_in_control": tempo.get("team_in_control")}},
                             subject="tempo"))

    # 4. Stat cards at fixed points, half-time and full-time summaries.
    def stat_facts(prefix: str) -> list[str]:
        return [f"{prefix}: xG {state.home} {home['xg']:.2f} - {away['xg']:.2f} {state.away}; "
                f"shots {home['shots']}-{away['shots']}; possession {_pct(home['possession'])}-{_pct(away['possession'])}."]
    stat_data = {"home": {k: home[k] for k in ("goals", "xg", "shots", "possession", "field_tilt")},
                 "away": {k: away[k] for k in ("goals", "xg", "shots", "possession", "field_tilt")}}
    period = int(st["clock"]["period"])
    finished = bool(st["clock"].get("finished"))
    ev = analyst.live.ev
    ht = ev[(ev.t == "period_end") & (ev.period == 1)]
    half_time_reached = bool(len(ht)) and clock_s >= float(ht.clock_s.iloc[0])
    def best_rated(at: float, label: str) -> tuple[list[str], list[str]]:
        """The highest match rating so far (rating.py), as a fact line plus the name it allows."""
        top = analyst.live_ratings(at).get("highest")
        if not top:
            return [], []
        return [f"{label}: {top['player']}, match rating {top['rating']:.1f}."], [top["player"]]

    if half_time_reached and "HT" not in state.periods_done:
        state.periods_done.add("HT")
        ht_clock = float(ht.clock_s.iloc[0])
        extra, names = best_rated(ht_clock, "Best rated at half-time")
        out.append(Candidate(f"ht:{int(clock_s)}", "half_time", ht_clock, int(ht.minute.iloc[0]), 0.9,
                             stat_facts(f"Half-time, {state.home} {home['goals']}-{away['goals']} {state.away}") + extra,
                             list(clubs) + names, [], {"template": "stat_card", "data": stat_data}, subject="half_time",
                             must_show=True))
    if finished and "FT" not in state.periods_done:
        state.periods_done.add("FT")
        extra, names = best_rated(clock_s, "Best rated")
        out.append(Candidate(f"ft:{int(clock_s)}", "full_time", clock_s, minute, 1.0,
                             stat_facts(f"Full-time, {state.home} {home['goals']}-{away['goals']} {state.away}") + extra,
                             list(clubs) + names, [], {"template": "stat_card", "data": stat_data}, subject="full_time",
                             must_show=True))
    for mark in STAT_MARKS:
        if minute >= mark and mark not in state.stat_marks_done and (period == 1) == (mark < 45) and not finished:
            state.stat_marks_done.add(mark)
            out.append(Candidate(f"stats:{mark}", "stats", clock_s, minute, 0.3, stat_facts(f"After {minute} minutes"),
                                 list(clubs), [], {"template": "stat_card", "data": stat_data}, subject="stats"))

    # 5. Player-focus stream.
    if focus_player_id:
        key = f"focus:{minute // 15}"
        if minute >= 10 and key not in state.stat_marks_done:
            state.stat_marks_done.add(key)
            pl = analyst.live_player(focus_player_id, clock_s)
            if pl.get("touches"):
                facts = [f"{pl['player']} after {minute} minutes: {pl['touches']} touches, {pl['passes']} passes "
                         f"({_pct(pl['pass_completion'])} completed), dispossessed {pl['dispossessed']} "
                         f"{'time' if pl['dispossessed'] == 1 else 'times'} when pressed {pl['times_pressed']} times, "
                         f"{pl['aerials_won']} aerial duels won and {pl['aerials_lost']} lost."]
                if pl.get("shots"):
                    facts.append(f"{pl['shots']} {'shot' if pl['shots'] == 1 else 'shots'}, {pl['xg']:.2f} xG, "
                                 f"{pl['goals']} {'goal' if pl['goals'] == 1 else 'goals'}.")
                out.append(Candidate(f"focus:{focus_player_id}:{minute}", "player_focus", clock_s, minute, 0.6, facts,
                                     list(clubs) + [pl["player"]], [], {"template": "player_card", "data": pl},
                                     subject=f"focus:{focus_player_id}", audience="player_focus"))
    return out
