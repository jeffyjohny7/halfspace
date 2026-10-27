"""Pre-match matchup report: context, form, style clash, edges and live-checkable predictions."""

from __future__ import annotations

import datetime as dt
import math

import pandas as pd

from .availability import probable_xi, team_news
from .metrics import TEAM_METRICS
from .profiles import form, head_to_head, league_table
from .scout import Scout
from .store import Store
from .util import clean, competition_name, pct_rank

STYLE_METRICS = ["possession", "field_tilt", "ppda", "pressures_per_opp_pass", "long_pass_share", "xg", "opp_xg",
                 "sp_xg", "opp_sp_xg", "counter_xg", "opp_counter_xg", "late_xga_ratio", "fouls",
                 "left_entry_share", "right_entry_share", "opp_offsides"]

# For a player of the opponent: which side of the beneficiary's attack does he face?
# The opponent's left back defends against the beneficiary's right flank.
FACES_FLANK = {"LB": "right", "LW": "right", "RB": "left", "RW": "left"}


def ordinal(x: float) -> str:
    """72 -> '72nd', 11 -> '11th', 1 -> '1st'."""
    n = int(round(x))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

def _team_view(store: Store, scout: Scout, club_id: str, season: str) -> dict:
    tab = scout.team_table(season)
    div = store.division_of(club_id, season)
    tab = tab[tab.division == div]
    row = tab[tab.team_id == club_id]
    vals = row.iloc[0].to_dict() if len(row) else {}
    pct = {m: pct_rank(vals.get(m), tab[m]) for m in STYLE_METRICS if m in tab}
    med = {m: float(tab[m].median()) for m in STYLE_METRICS if m in tab}
    return {"values": vals, "percentile": pct, "league_median": med}


def _fixture(store: Store, home_id: str, away_id: str, season: str, match_id: str | None) -> dict:
    up = store.upcoming
    row = up[(up.home_id == home_id) & (up.away_id == away_id) & (up.season == season)]
    if match_id:
        row = up[up.match_id == match_id]
    if row.empty:
        return {"match_id": match_id, "date": None, "round": None}
    r = row.iloc[0]
    return {"match_id": r.match_id, "date": r.date, "round": int(r["round"]),
            "home_days_rest": None if pd.isna(r.home_days_rest) else int(r.home_days_rest),
            "away_days_rest": None if pd.isna(r.away_days_rest) else int(r.away_days_rest)}


def _europe_before(store: Store, club_id: str, date: str | None, season: str) -> dict | None:
    if not date:
        return None
    eu = store.european_fixtures
    eu = eu[(eu.club_id == club_id) & (eu.season == season)]
    d = dt.date.fromisoformat(date)
    for r in eu.itertuples():
        e = dt.date.fromisoformat(r.date)
        if 0 < (d - e).days <= 4:
            return {"competition": competition_name(r.competition), "date": r.date, "days_before": (d - e).days}
    return None


def _europe_fatigue_effect(store: Store) -> dict:
    """League evidence: what happens late in games after a midweek European trip?"""
    tm = store.table("team_match")
    tm = tm[(tm.stage == "league") & (tm.division == 1)]
    eu, rest = tm[tm.midweek_europe.astype(bool)], tm[~tm.midweek_europe.astype(bool)]
    if len(eu) < 10:
        return {}
    return {"matches_after_europe": len(eu), "late_xg_conceded_after_europe": float(eu.opp_late_xg.mean()),
            "late_xg_conceded_otherwise": float(rest.opp_late_xg.mean()),
            "points_per_match_after_europe": float(eu.points.mean()),
            "points_per_match_otherwise": float(rest.points.mean())}


def _stakes(store: Store, season: str, home_id: str, away_id: str) -> dict:
    t = league_table(store, season, store.division_of(home_id, season))["table"]
    out = {}
    for cid in (home_id, away_id):
        me = next(r for r in t if r["club_id"] == cid)
        def pos_with(extra):
            pts = me["points"] + extra
            return 1 + sum(1 for r in t if r["club_id"] != cid and (r["points"], r["gd"]) > (pts, me["gd"]))
        out[cid] = {"position": me["position"], "points": me["points"], "zone": me["zone"],
                    "position_if_win": pos_with(3), "position_if_draw": pos_with(1)}
    return out


def _key_players(scout: Scout, club_id: str, season: str, n: int = 3) -> list[dict]:
    out = []
    for metric in ("xt_p90", "npxg_p90"):
        cmp_ = scout.player_cmp(metric).reset_index()
        c = cmp_[(cmp_.season == season) & (cmp_.team_id == club_id) & (cmp_.minutes >= 270)]
        for r in c.sort_values("shrunk", ascending=False).head(n).itertuples():
            out.append({"player_id": r.player_id, "name": r.name, "position": r.position, "metric": metric,
                        "value": r.raw, "percentile": r.percentile})
    return out


def _f(findings: list[dict], *cats: str) -> list[dict]:
    return [f for f in findings if f["category"] in cats]


def build_edges(store: Store, scout: Scout, ben: str, opp: str, season: str, ben_view: dict, opp_view: dict,
                ben_f: list[dict], opp_f: list[dict], fixture: dict, opp_europe: dict | None) -> list[dict]:
    edges: list[dict] = []
    bname, oname = store.club_name(ben), store.club_name(opp)
    bp = ben_view["percentile"]
    bv = ben_view["values"]

    def add(kind, title, text, strength, supports, predictions):
        predictions = [x for x in predictions if x]
        edges.append({"edge_id": f"{ben}>{opp}:{kind}:{len(edges)}", "beneficiary_id": ben, "beneficiary": bname,
                      "opponent_id": opp, "opponent": oname, "kind": kind, "title": title, "explanation": text,
                      "strength": round(float(strength), 2), "supporting_findings": supports,
                      "predictions": predictions})

    # 1. Pressing vs players who lose the ball or misplace passes.
    press_pct = bp.get("pressures_per_opp_pass") or 0
    if press_pct >= 55 or _f(ben_f, "intense_press"):
        for f in _f(opp_f, "loses_ball_under_pressure", "error_prone_passer"):
            flank = FACES_FLANK.get(f["position"] or "")
            boost, extra = 1.0, ""
            if flank:
                cat = f"{flank}_flank_focus"
                share = bv.get(f"{flank}_entry_share")
                if _f(ben_f, cat) or (bp.get(f"{flank}_entry_share") or 0) >= 70:
                    boost = 1.5
                    extra = (f" {bname} also attack down their {flank} - straight at him "
                             f"({share:.0%} of their final-third entries).")
            strength = abs(f["z"]) * (0.5 + press_pct / 100) * boost
            text = (f"{bname} press hard ({bv.get('pressures_per_opp_pass', 0):.3f} pressures per opponent pass, "
                    f"{ordinal(press_pct)} percentile). {f['summary']}{extra}")
            preds = [_pred_player(scout, f, "dispossessed" if f["category"] == "loses_ball_under_pressure"
                                  else "turnovers", season, press_factor=_press_factor(ben_view))]
            add("press_vs_ball_loser", f"Press {f['player']}", text, strength, [f["finding_id"]], preds)

    # 2. Set pieces and crosses vs aerial or set-piece weakness.
    sp_pct = bp.get("sp_xg") or 0
    ben_sp = _f(ben_f, "set_piece_attack_strong", "elite_crosser", "strong_in_the_air")
    weak = _f(opp_f, "set_piece_defense_weak", "weak_in_the_air", "goalkeeper_weak_on_crosses", "vulnerable_to_crosses")
    if weak and (ben_sp or sp_pct >= 65):
        strength = max(abs(w["z"]) for w in weak) * (0.6 + sp_pct / 100) * (1.3 if ben_sp else 1.0)
        bits = "; ".join(w["summary"] for w in weak[:3])
        own = "; ".join(s["summary"] for s in ben_sp[:2]) or (
            f"{bname} create {bv.get('sp_xg', 0):.2f} xG per match from set-piece deliveries ({ordinal(sp_pct)} percentile).")
        text = f"Set pieces: {own} {oname} at the back: {bits}"
        preds = [_pred_team(scout, store, ben, opp, "set_piece_xg_for", season, ben_view, opp_view)]
        for w in weak:
            if w["category"] == "weak_in_the_air" and w["player_id"]:
                preds.append(_pred_player(scout, w, "aerial_win_rate", season))
        add("set_pieces", "Set pieces and crosses", text, strength, [w["finding_id"] for w in weak + ben_sp], preds)

    # 3. Late in the game: fitness and midweek European football.
    fade = _f(opp_f, "late_fade")
    eff = _europe_fatigue_effect(store) if opp_europe else {}
    if opp_europe and not (eff and eff["late_xg_conceded_after_europe"] >= 1.15 * eff["late_xg_conceded_otherwise"]):
        opp_europe = None  # the league data shows no meaningful midweek-Europe effect; say nothing
    if fade or opp_europe:
        parts, strength = [], 0.0
        if fade:
            parts.append(fade[0]["summary"])
            strength += abs(fade[0]["z"])
        if opp_europe:
            parts.append(f"{oname} played in the {opp_europe['competition']} {opp_europe['days_before']} days earlier.")
            if eff:
                parts.append(f"League-wide, teams after a midweek European game concede "
                             f"{eff['late_xg_conceded_after_europe']:.2f} xG after the 75th minute vs "
                             f"{eff['late_xg_conceded_otherwise']:.2f} otherwise.")
            strength += 1.0
        add("late_game", "Last 15 minutes", " ".join(parts), strength, [f["finding_id"] for f in fade],
            [_pred_team(scout, store, ben, opp, "late_xg_for", season, ben_view, opp_view)])

    # 4. Balls in behind a high line.
    line = _f(opp_f, "high_line_exposed", "vulnerable_to_counters")
    ctr_pct = bp.get("counter_xg") or 0
    finisher = _f(ben_f, "clinical_finisher")
    if line and (ctr_pct >= 55 or finisher or _f(ben_f, "direct_style")):
        strength = max(abs(x["z"]) for x in line) * (0.6 + ctr_pct / 100) * (1.3 if finisher else 1.0)
        text = " ".join(x["summary"] for x in line[:2]) + (
            f" {bname} create {bv.get('counter_xg', 0):.2f} xG per match on the counter ({ordinal(ctr_pct)} percentile).")
        if finisher:
            text += " " + finisher[0]["summary"]
        add("in_behind", "Balls in behind", text, strength, [x["finding_id"] for x in line + finisher],
            [_pred_team(scout, store, ben, opp, "offsides_won", season, ben_view, opp_view),
             _pred_team(scout, store, ben, opp, "counter_xg_for", season, ben_view, opp_view)])

    # 5. Discipline: fouls give set pieces.
    disc = _f(opp_f, "poor_discipline", "hothead")
    if disc and (ben_sp or sp_pct >= 55):
        strength = max(abs(x["z"]) for x in disc) * 0.8
        text = (f"{oname}: " + " ".join(x["summary"] for x in disc[:2])
                + f" More {oname} fouls mean more set pieces for {bname}, a dangerous delivery side.")
        preds = [_pred_team(scout, store, ben, opp, "fouls_by_opponent", season, ben_view, opp_view)]
        add("discipline", "Fouls into set pieces", text, strength, [x["finding_id"] for x in disc], preds)

    # 6. Venue.
    if fixture.get("match_id") and _f(ben_f, "fortress_home") and store.upcoming.set_index("match_id").loc[
            fixture["match_id"]].home_id == ben:
        f = _f(ben_f, "fortress_home")[0]
        add("venue", "Home advantage", f["summary"], abs(f["z"]) * 0.8, [f["finding_id"]], [])
    edges.sort(key=lambda e: -e["strength"])
    return edges


def _press_factor(view: dict) -> float:
    v = view["values"].get("pressures_per_opp_pass")
    m = view["league_median"].get("pressures_per_opp_pass")
    return float(v / m) if v and m else 1.0


def _pred_player(scout: Scout, f: dict, measure: str, season: str, press_factor: float = 1.0) -> dict:
    """Expected count in a 90-minute match for this player vs an average player in his position."""
    pid = f["player_id"]
    ps = scout.ps
    rows = ps[(ps.player_id == pid) & ps.season.isin(f["seasons_used"])]
    mins = max(1.0, rows.minutes.sum())
    pos_rows = ps[(ps.season == season) & (ps.position == f["position"]) & (ps.division == 1) & (ps.minutes >= 270)]
    if measure == "dispossessed":
        pressed90 = rows.times_pressed.sum() / mins * 90 * press_factor
        own_rate = rows.dispossessed.sum() / max(1.0, rows.times_pressed.sum())
        avg_rate = pos_rows.dispossessed.sum() / max(1.0, pos_rows.times_pressed.sum())
        exp_player, exp_avg = own_rate * pressed90, avg_rate * pressed90
        label = f"{f['player']} dispossessed"
    elif measure == "turnovers":
        exp_player = rows.turnovers_under_pressure.sum() / mins * 90 * press_factor
        exp_avg = pos_rows.turnovers_under_pressure.sum() / max(1.0, pos_rows.minutes.sum()) * 90 * press_factor
        label = f"{f['player']} turnovers under pressure"
    else:  # aerial_win_rate (a rate, needs a few duels before it means anything)
        exp_player = rows.aerials_won.sum() / max(1.0, rows.aerials.sum())
        exp_avg = pos_rows.aerials_won.sum() / max(1.0, pos_rows.aerials.sum())
        confirm = round((exp_player + exp_avg) / 2, 2)
        return {"prediction_id": f"{f['finding_id']}:{measure}", "subject_type": "player", "subject_id": pid,
                "subject": f["player"], "measure": measure, "label": f"{f['player']} aerial duels won",
                "kind": "rate_at_most", "min_sample": 4,
                "expected_if_trait_holds": round(exp_player, 2), "expected_average_player": round(exp_avg, 2),
                "confirm_at": confirm,
                "text": f"{f['player']} wins about {exp_player:.0%} of aerial duels vs {exp_avg:.0%} for an average "
                        f"{f['position']}; confirmed if he wins {confirm:.0%} or fewer of at least 4 duels."}
    confirm = max(2, math.ceil(exp_avg + 0.6 * (exp_player - exp_avg)))
    return {"prediction_id": f"{f['finding_id']}:{measure}", "subject_type": "player", "subject_id": pid,
            "subject": f["player"], "measure": measure, "label": label, "kind": "count_at_least",
            "expected_if_trait_holds": round(exp_player, 2), "expected_average_player": round(exp_avg, 2),
            "confirm_at": confirm,
            "text": f"{label}: expect about {exp_player:.1f} vs {exp_avg:.1f} for an average {f['position']}; "
                    f"confirmed at {confirm}."}


TEAM_MEASURES = {
    # measure: (team metric for the beneficiary, metric for the opponent, label, confirm rule)
    "set_piece_xg_for": ("sp_xg", "opp_sp_xg", "set-piece delivery xG"),
    "late_xg_for": (None, None, "xG after the 75th minute"),
    "offsides_won": (None, "opp_offsides", "opponent offsides"),
    "counter_xg_for": ("counter_xg", "opp_counter_xg", "counter-attack xG"),
    "fouls_by_opponent": (None, "fouls", "fouls committed"),
}


def _pred_team(scout: Scout, store: Store, ben: str, opp: str, measure: str, season: str,
               ben_view: dict, opp_view: dict) -> dict:
    bm, om, label = TEAM_MEASURES[measure]
    bv, ov = ben_view["values"], opp_view["values"]
    med_b, med_o = ben_view["league_median"], opp_view["league_median"]
    if measure == "set_piece_xg_for":
        exp = (bv.get(bm, 0) + ov.get(om, 0)) / 2
        avg = med_b.get(bm, 0)
    elif measure == "counter_xg_for":
        exp = (bv.get(bm, 0) + ov.get(om, 0)) / 2
        avg = med_b.get(bm, 0)
    elif measure == "offsides_won":
        exp, avg = ov.get(om, 0), med_o.get(om, 0)
    elif measure == "fouls_by_opponent":
        exp, avg = ov.get(om, 0), med_o.get(om, 0)
    else:  # late_xg_for
        tm = store.table("team_match")
        div1 = tm[(tm.season == season) & (tm.stage == "league") & (tm.division == 1)]
        mine = div1[div1.team_id == opp]
        exp, avg = float(mine.opp_late_xg.mean()), float(div1.opp_late_xg.mean())
    subject = opp if measure == "fouls_by_opponent" else ben
    if not exp or not avg or exp < 1.15 * avg:
        return None                     # not clearly above average: nothing worth checking live
    # Confirmed once the match is clearly above an average team, 60% of the way to the expectation.
    gap = exp - avg
    is_xg = "xg" in measure
    confirm = round(float(avg + 0.6 * gap), 2) if is_xg else int(math.ceil(avg + max(1.5, 0.6 * gap)))
    fmt = (lambda v: f"{v:.2f}") if is_xg else (lambda v: f"{v:.1f}")
    return {"prediction_id": f"{ben}>{opp}:{measure}", "subject_type": "team", "subject_id": subject,
            "subject": store.club_name(subject), "measure": measure, "label": label, "kind": "count_at_least",
            "beneficiary_id": ben, "opponent_id": opp,
            "expected_if_trait_holds": round(float(exp), 2), "expected_average": round(float(avg), 2),
            "confirm_at": confirm,
            "text": f"{store.club_name(subject)} {label}: expect about {fmt(exp)} vs league average {fmt(avg)}; "
                    f"confirmed at {confirm}."}


def matchup_report(store: Store, scout: Scout, home_id: str, away_id: str, season: str | None = None,
                   match_id: str | None = None, min_confidence: str = "medium") -> dict:
    season = season or store.current_season
    fixture = _fixture(store, home_id, away_id, season, match_id)
    views = {c: _team_view(store, scout, c, season) for c in (home_id, away_id)}
    finds = {c: scout.findings(c, season, min_confidence=min_confidence) for c in (home_id, away_id)}
    europe = {c: _europe_before(store, c, fixture.get("date"), season) for c in (home_id, away_id)}
    edges = []
    for ben, opp in ((home_id, away_id), (away_id, home_id)):
        edges += build_edges(store, scout, ben, opp, season, views[ben], views[opp], finds[ben], finds[opp],
                             fixture, europe[opp])
    # Team news: an edge built on a player who is injured or suspended is dropped,
    # and a doubtful player's edge is kept but flagged.
    news = {c: team_news(store, c, fixture.get("match_id")) for c in (home_id, away_id)}
    out_ids = {x["player_id"] for n in news.values() for x in n.get("unavailable", [])}
    doubt_ids = {x["player_id"] for n in news.values() for x in n.get("doubtful", [])}
    kept, dropped = [], []
    for e in edges:
        pids = {p.get("subject_id") for p in e["predictions"] if p.get("subject_type") == "player"}
        missing = pids & out_ids
        if missing and (e["kind"] == "press_vs_ball_loser" or missing == pids and not
                        any(p.get("subject_type") == "team" for p in e["predictions"])):
            dropped.append({"edge_id": e["edge_id"], "title": e["title"],
                            "reason": "player unavailable: " + ", ".join(store.player_name(x) for x in missing)})
            continue
        notes = []
        if missing:
            e["predictions"] = [p for p in e["predictions"] if p.get("subject_id") not in missing]
            notes.append("Unavailable: " + ", ".join(store.player_name(x) for x in missing))
        if pids & doubt_ids:
            notes.append("Doubtful: " + ", ".join(store.player_name(x) for x in pids & doubt_ids))
        if notes:
            e["team_news_note"] = "; ".join(notes)
        kept.append(e)
    edges = kept
    edges.sort(key=lambda e: -e["strength"])
    predictions = [p for e in edges for p in e["predictions"]]
    seen, uniq = set(), []
    for p in predictions:
        if p["prediction_id"] not in seen:
            seen.add(p["prediction_id"])
            uniq.append(p)
    style = []
    for m in STYLE_METRICS:
        style.append({"metric": m, "label": TEAM_METRICS[m][0],
                      "home": views[home_id]["values"].get(m), "home_percentile": views[home_id]["percentile"].get(m),
                      "away": views[away_id]["values"].get(m), "away_percentile": views[away_id]["percentile"].get(m),
                      "league_median": views[home_id]["league_median"].get(m)})
    manager = {c: store.club_season(c, season) for c in (home_id, away_id)}
    return clean({
        "fixture": {**fixture, "season": season, "home_id": home_id, "home": store.club_name(home_id),
                    "away_id": away_id, "away": store.club_name(away_id)},
        "context": {
            "stakes": _stakes(store, season, home_id, away_id),
            "midweek_europe": {store.club_name(c): e for c, e in europe.items()},
            "managers": {store.club_name(c): {"manager": m["manager"], "formation": m["formation"],
                                              "philosophy": m["manager_philosophy"],
                                              "new_this_season": store.manager_changed(c, season)}
                         for c, m in manager.items()},
        },
        "form": {"home_overall": form(store, home_id, season), "away_overall": form(store, away_id, season),
                 "home_at_home": form(store, home_id, season, venue="home"),
                 "away_on_the_road": form(store, away_id, season, venue="away")},
        "head_to_head": head_to_head(store, home_id, away_id)["meetings"],
        "style_comparison": style,
        "edges": edges,
        "predictions_to_track": uniq,
        "key_players": {store.club_name(home_id): _key_players(scout, home_id, season),
                        store.club_name(away_id): _key_players(scout, away_id, season)},
        "team_news": {store.club_name(c): {k: news[c].get(k) for k in ("summary", "unavailable", "doubtful")}
                      for c in (home_id, away_id)},
        "edges_dropped_for_team_news": dropped,
        "probable_lineups": {store.club_name(home_id): probable_xi(store, home_id, season),
                             store.club_name(away_id): probable_xi(store, away_id, season)},
        "findings": {store.club_name(c): [{k: f[k] for k in ("finding_id", "category", "direction", "player",
                                                              "confidence", "summary", "evidence")}
                                           for f in finds[c]] for c in (home_id, away_id)},
        "method": "Edges pair one side's weakness with the other side's matching strength. Every number comes "
                  "from public match events; predictions are checked live by the live layer.",
    })
