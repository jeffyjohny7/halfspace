"""Export the league hub for the Halfspace app: tables, results, fixtures, stat leaders, clubs and players.

    uv run scripts/export_league.py          # writes web/data/league.json and web/data/<season>/*.json

league.json is what the app loads first: clubs, both seasons' tables and stat leaders, this round's
fixtures (kick-off times, the model's outlook and a preview for each) and the latest results. The rest is
loaded when a fan opens it: web/data/<season>/matches.json (scorers, line-ups, ratings and team numbers
for every result), players.json (season numbers and position percentiles) and clubs.json (style,
scouting notes, squad). Every number comes from the analytics layer; nothing here calls a model.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics.api import Analyst  # noqa: E402
from analytics.util import competition_name  # noqa: E402

LEAGUE = "Crown League"
SAT_SLOTS = ["15:00", "15:00", "15:00", "17:30", "15:00", "17:30", "15:00", "20:00", "15:00"]
LIVE_SLOT = "12:30"                 # the showcase match is the early kick-off: on air now in the app
SUN_SLOTS = ["14:00", "16:30"]
SEASON_NOTE = re.compile(r"\s*\((?:\d{4}-\d{2}: [^)]*)\)")


def portrait_kits() -> dict[str, str]:
    """player_id -> the club whose kit he wears in his portrait (web/assets/players/kits.json)."""
    path = ROOT / "web" / "assets" / "players" / "kits.json"
    kits = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {pid: club for pid, club in kits.items()
            if (ROOT / "web" / "assets" / "players" / f"{pid}.webp").exists()}

def r2(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), d)


def short_codes(clubs: pd.DataFrame) -> dict[str, str]:
    """Three-letter codes, unique across the league (two clubs share 'DUN')."""
    out, used = {}, set()
    for r in clubs.sort_values("club_id").itertuples():
        code = str(r.short_name).upper()
        if code in used:
            letters = [ch for ch in r.name.upper() if ch.isalpha()]
            cons = [ch for ch in letters[1:] if ch not in "AEIOU"]
            for a in cons:
                for b in cons[cons.index(a) + 1:]:
                    cand = letters[0] + a + b
                    if cand not in used:
                        code = cand
                        break
                if code not in used:
                    break
        used.add(code)
        out[r.club_id] = code
    return out


# Outlook

def outlook_model(store, season: str, prev: str | None):
    """Expected goals for a fixture from each side's chance quality for and against (xG per match), this
    season weighted fully and last season's top-flight numbers at half weight, with the league's home edge."""
    tm = store.table("team_match")
    tm = tm[(tm.stage == "league") & (tm.division == 1)]
    cur, old = tm[tm.season == season], tm[tm.season == prev] if prev else tm.iloc[0:0]
    rates = {}
    for team in set(cur.team_id):
        a, b = cur[cur.team_id == team], old[old.team_id == team]
        w = len(a) + 0.5 * len(b)
        rates[team] = ((a.xg.sum() + 0.5 * b.xg.sum()) / w, (a.opp_xg.sum() + 0.5 * b.opp_xg.sum()) / w)
    avg = float(pd.concat([cur.xg, old.xg]).mean())
    ref = old if len(old) else cur
    home_edge = math.sqrt(float(ref[ref.is_home].xg.mean()) / float(ref[~ref.is_home].xg.mean()))

    def predict(home: str, away: str) -> dict:
        (ha, hd), (aa, ad) = rates[home], rates[away]
        lh, la = ha * ad / avg * home_edge, aa * hd / avg / home_edge
        goals = np.arange(11)
        ph = np.exp(-lh) * lh ** goals / np.array([math.factorial(int(g)) for g in goals])
        pa = np.exp(-la) * la ** goals / np.array([math.factorial(int(g)) for g in goals])
        grid = np.outer(ph, pa)
        hw, dr, aw = float(np.tril(grid, -1).sum()), float(np.trace(grid)), float(np.triu(grid, 1).sum())
        tot = hw + dr + aw
        # The likeliest score within the likeliest result, so a 56% home win never reads "1-1".
        mask = {0: np.tril(np.ones_like(grid), -1), 1: np.eye(len(goals)),
                2: np.triu(np.ones_like(grid), 1)}[int(np.argmax([hw, dr, aw]))]
        i, j = np.unravel_index(int((grid * mask).argmax()), grid.shape)
        return {"home_win": round(hw / tot * 100), "draw": round(dr / tot * 100), "away_win": round(aw / tot * 100),
                "xg_home": r2(lh), "xg_away": r2(la), "likely_score": f"{i}-{j}"}
    return predict, {"league_xg_per_team_match": r2(avg), "home_edge": r2(home_edge ** 2)}


# Tables

def form_and_xg(store, season: str, division: int) -> dict:
    tm = store.table("team_match")
    tm = tm[(tm.season == season) & (tm.division == division) & (tm.stage == "league")].sort_values(["date", "round"])
    out = {}
    for team, g in tm.groupby("team_id"):
        last = g.tail(5)
        out[team] = {
            "form": [{"r": r.result, "opp": r.opponent_id, "score": f"{int(r.goals_for)}-{int(r.goals_against)}",
                      "venue": "H" if r.is_home else "A", "match_id": r.match_id} for r in last.itertuples()],
            "xg_for": r2(g.xg.sum(), 1), "xg_against": r2(g.opp_xg.sum(), 1),
        }
    return out


def tables(a: Analyst, season: str) -> dict:
    out = {}
    for div in (1, 2):
        try:
            t = a.league_table(season, division=div)
        except Exception:
            continue
        if not t.get("table"):
            continue
        fx = form_and_xg(a.store, season, div)
        rows = []
        for r in t["table"]:
            f = fx.get(r["club_id"], {})
            rows.append({"pos": r["position"], "club": r["club_id"], "p": r["played"], "w": r["won"], "d": r["drawn"],
                         "l": r["lost"], "gf": r["gf"], "ga": r["ga"], "gd": r["gd"], "pts": r["points"],
                         "zone": competition_name(r["zone"]) if r.get("zone") else None,
                         "form": f.get("form", []), "xgf": f.get("xg_for"), "xga": f.get("xg_against")})
        out[str(div)] = {"after_round": t.get("after_round"), "rows": rows}
    return out


# Players

POS_GROUP = {"GK": "GK", "CB": "DF", "RB": "DF", "LB": "DF", "RWB": "DF", "LWB": "DF", "DM": "MF", "CM": "MF",
             "AM": "MF", "RM": "MF", "LM": "MF", "RW": "FW", "LW": "FW", "ST": "FW", "CF": "FW"}
PCT_METRICS = [("goals_p90", "Goals"), ("xg_p90", "xG"), ("assists_p90", "Assists"), ("key_passes_p90", "Chances created"),
               ("prog_p90", "Progressive passes"), ("dribbles_p90", "Dribbles won"), ("def_p90", "Tackles + interceptions"),
               ("aerial_pct", "Aerials won %"), ("pass_pct", "Pass completion")]


def season_players(a: Analyst, season: str, d1_ids: set) -> tuple[dict, pd.DataFrame]:
    s = a.store
    pm = s.table("player_match")
    pm = pm[(pm.season == season) & pm.match_id.isin(d1_ids)]
    tm = s.table("team_match")[["match_id", "team_id", "goals_against"]]
    pm = pm.merge(tm, on=["match_id", "team_id"], how="left")
    rt = s.player_ratings
    rt = rt[(rt.season == season) & rt.match_id.isin(d1_ids)]
    pl = s.players.set_index("player_id")
    start_year = int(season[:4])
    photos = portrait_kits()
    g = pm[pm.minutes > 0].groupby("player_id")
    agg = g.agg(club=("team_id", "last"), pos=("position", lambda x: x.mode().iloc[0]), apps=("match_id", "nunique"),
                starts=("started", "sum"), minutes=("minutes", "sum"), goals=("goals", "sum"), assists=("assists", "sum"),
                xg=("xg", "sum"), xa=("xa", "sum"), shots=("shots", "sum"), sot=("shots_on_target", "sum"),
                key_passes=("key_passes", "sum"), passes=("passes", "sum"), passes_ok=("passes_completed", "sum"),
                prog=("progressive_passes", "sum"), dribbles=("take_ons_won", "sum"), tackles=("tackles", "sum"),
                interceptions=("interceptions", "sum"), aerials=("aerials", "sum"), aerials_won=("aerials_won", "sum"),
                saves=("saves", "sum"), yellow=("yellow", "sum"), red=("red", "sum"))
    gk = pm[(pm.position == "GK") & (pm.minutes >= 60)]
    agg["clean_sheets"] = gk[gk.goals_against == 0].groupby("player_id").size().reindex(agg.index).fillna(0)
    agg["conceded"] = gk.groupby("player_id").goals_against.sum().reindex(agg.index).fillna(0)
    ravg = rt.groupby("player_id").rating.agg(["mean", "count"])
    agg["rating"] = ravg["mean"].reindex(agg.index)
    m90 = agg.minutes / 90
    agg["goals_p90"], agg["xg_p90"] = agg.goals / m90, agg.xg / m90
    agg["assists_p90"], agg["key_passes_p90"] = agg.assists / m90, agg.key_passes / m90
    agg["prog_p90"], agg["dribbles_p90"] = agg.prog / m90, agg.dribbles / m90
    agg["def_p90"] = (agg.tackles + agg.interceptions) / m90
    agg["aerial_pct"] = (agg.aerials_won / agg.aerials.where(agg.aerials > 0)) * 100
    agg["pass_pct"] = (agg.passes_ok / agg.passes.where(agg.passes > 0)) * 100
    agg["group"] = agg.pos.map(POS_GROUP).fillna("MF")
    qualified = agg[agg.minutes >= 270]
    order = rt.merge(s.table("team_match")[["match_id", "date"]].drop_duplicates("match_id"), on="match_id")
    out = {}
    for pid, r in agg.iterrows():
        peers = qualified[qualified.group == r.group]
        pcts = {}
        if r.minutes >= 270 and len(peers) >= 5:
            for m, _label in PCT_METRICS:
                v = r[m]
                if v is None or pd.isna(v):
                    continue
                pcts[m] = int(round((peers[m] < v).mean() * 100))
        recent = order[order.player_id == pid].sort_values("date").tail(10)
        birth = pl.birth_year.get(pid) if "birth_year" in pl.columns else None
        out[pid] = {
            "name": s.player_name(pid), "club": r.club, "pos": r.pos, "group": r.group,
            "age": int(start_year - birth) if birth and not pd.isna(birth) else None,
            "photo": f"assets/players/{pid}.webp" if photos.get(pid) == r.club else None,
            **{k: int(r[k]) for k in ("apps", "starts", "minutes", "goals", "assists", "shots", "sot", "key_passes",
                                      "prog", "dribbles", "tackles", "interceptions", "aerials", "aerials_won",
                                      "saves", "yellow", "red", "clean_sheets", "conceded")},
            "xg": r2(r.xg), "xa": r2(r.xa), "pass_pct": r2(r.pass_pct, 0), "rating": r2(r.rating, 2),
            "ratings": [[m, r2(v, 1)] for m, v in zip(recent.match_id, recent.rating)],
            "pct": pcts,
        }
    return out, agg


LEADER_BOARDS = [
    ("goals", "Goals", "goals", False), ("assists", "Assists", "assists", False), ("xg", "Expected goals (xG)", "xg", True),
    ("key_passes", "Chances created", "key_passes", False), ("def", "Tackles + interceptions", "def", False),
    ("clean_sheets", "Clean sheets", "clean_sheets", False), ("rating", "Average match rating", "rating", True),
]


def leaders(agg: pd.DataFrame, rounds: int) -> dict:
    agg = agg.copy()
    agg["def"] = agg.tackles + agg.interceptions
    out = {}
    for key, label, col, dec in LEADER_BOARDS:
        pool = agg
        if key == "rating":
            pool = agg[agg.apps >= max(3, rounds // 2)]
        if key == "clean_sheets":
            pool = agg[agg.pos == "GK"]
        top = pool.sort_values([col, "minutes"], ascending=[False, True]).head(10)
        out[key] = {"label": label, "rows": [{"player": pid, "club": r.club, "value": r2(r[col], 2) if dec else int(r[col]),
                                              "apps": int(r.apps)} for pid, r in top.iterrows() if r[col] and r[col] > 0]}
    return out


# Matches

def season_matches(a: Analyst, season: str, matches: pd.DataFrame) -> dict:
    s = a.store
    ids = set(matches.match_id)
    shots = s.table("shots")
    shots = shots[shots.match_id.isin(ids)]
    goals = shots[shots.is_goal.astype(bool)]
    pm = s.table("player_match")
    pm = pm[pm.match_id.isin(ids)]
    tm = s.table("team_match")
    tm = tm[tm.match_id.isin(ids)].set_index(["match_id", "team_id"])
    rt = s.player_ratings.set_index(["match_id", "player_id"]).rating
    lu = s.lineups
    lu = lu[lu.match_id.isin(ids)]
    out = {}
    for m in matches.itertuples():
        mg = goals[goals.match_id == m.match_id].sort_values("clock_s")
        glist = []
        for gl in mg.itertuples():
            og = gl.kind == "own_goal"
            glist.append({"min": int(gl.minute) + 1 if gl.minute is not None else None,
                          "team": gl.scoring_team_id, "player": gl.player_id, "og": bool(og),
                          "pen": str(gl.play_pattern) == "penalty",
                          "assist": None if og or pd.isna(gl.assist_player_id) else gl.assist_player_id})
        stats, lines = {}, {}
        for side, club in (("home", m.home_id), ("away", m.away_id)):
            if (m.match_id, club) in tm.index:
                t = tm.loc[(m.match_id, club)]
                stats[side] = {"xg": r2(t.xg), "shots": int(t.shots), "sot": int(t.shots_on_target),
                               "possession": r2(t.possession * 100, 0), "corners": int(t.corners), "fouls": int(t.fouls),
                               "pass_pct": r2(t.passes_completed / t.passes * 100, 0) if t.passes else None,
                               "yellow": int(t.yellows), "red": int(t.reds)}
            rows = lu[(lu.match_id == m.match_id) & (lu.team_id == club)]
            lines[side] = [{"p": r.player_id, "pos": r.position, "start": bool(r.started),
                            "on": None if r.started else (int(r.minute_on) if not pd.isna(r.minute_on) else None),
                            "off": int(r.minute_off) if not pd.isna(r.minute_off) and r.minute_off < 90 else None,
                            "rt": r2(rt.get((m.match_id, r.player_id)), 1)}
                           for r in rows.itertuples() if r.started or (not pd.isna(r.minute_on) and r.minutes > 0)]
        cards = [{"team": r.team_id, "player": r.player_id, "red": bool(r.red)}
                 for r in pm[(pm.match_id == m.match_id) & ((pm.yellow > 0) | (pm.red > 0))].itertuples()]
        out[m.match_id] = {"goals": glist, "stats": stats, "lineups": lines, "cards": cards}
    return out


# Clubs

def season_clubs(a: Analyst, season: str, club_ids: list[str], players: dict) -> dict:
    s = a.store
    sq = s.squads
    sq = sq[sq.season == season]
    tm = s.table("team_match")
    tm = tm[(tm.season == season) & (tm.stage == "league")]
    phases = ["open_play", "corner", "free_kick", "direct_free_kick", "penalty", "counter", "throw_in", "own_goal"]
    times = ["t0-15", "t16-30", "t31-45+", "t46-60", "t61-75", "t76-90+"]
    out = {}
    for cid in club_ids:
        g = tm[tm.team_id == cid]
        try:
            prof = a.club_profile(cid, season)
        except Exception:
            prof = {}
        try:
            finds = a.scout.findings(cid, season, min_confidence="medium")
        except Exception:
            finds = []
        notes = [{"text": SEASON_NOTE.sub("", f["summary"]).strip(), "kind": f["direction"], "confidence": f["confidence"],
                  "player": f.get("player_id")} for f in finds[:8]]
        metrics = []
        for block in ("attack", "defence", "style"):
            for x in prof.get(block, []) or []:
                metrics.append({"group": block, "label": x["label"], "value": r2(x["value"], 3),
                                "median": r2(x.get("league_median"), 3), "pct": r2(x.get("percentile"), 0),
                                "better": x.get("better")})
        squad = [{"p": r.player_id, "name": s.player_name(r.player_id), "shirt": int(r.shirt), "pos": r.position}
                 for r in sq[sq.club_id == cid].sort_values("shirt").itertuples()]
        top = sorted([(pid, p) for pid, p in players.items() if p["club"] == cid], key=lambda kv: -(kv[1]["rating"] or 0))
        home, away = g[g.is_home], g[~g.is_home]
        out[cid] = {
            "manager": prof.get("manager"), "formation": prof.get("formation"), "philosophy": prof.get("philosophy"),
            "record": {"home": [int((home.result == x).sum()) for x in "WDL"], "away": [int((away.result == x).sum()) for x in "WDL"]},
            "xg_for": r2(g.xg.mean()), "xg_against": r2(g.opp_xg.mean()),
            "goals_for_by": {p: int(g.get(f"goals_for_{p}", pd.Series(dtype=float)).sum()) for p in phases},
            "goals_against_by": {p: int(g.get(f"goals_against_{p}", pd.Series(dtype=float)).sum()) for p in phases},
            "goals_for_time": [int(g.get(f"goals_for_{t}", pd.Series(dtype=float)).sum()) for t in times],
            "goals_against_time": [int(g.get(f"goals_against_{t}", pd.Series(dtype=float)).sum()) for t in times],
            "metrics": metrics, "notes": notes, "squad": squad,
            "top": [pid for pid, _ in top[:5]],
        }
    return out


# Fixtures

def fixtures(a: Analyst, predict, codes: dict) -> list[dict]:
    s = a.store
    up = s.upcoming.sort_values(["date", "match_id"])
    show = s.showcase_meta["match_id"]
    sat_i = sun_i = 0
    first_date = up.date.min()
    out = []
    for r in up.itertuples():
        if r.match_id == show:
            ko, status = LIVE_SLOT, "live"
        elif r.date == first_date:
            ko, status = SAT_SLOTS[sat_i % len(SAT_SLOTS)], "scheduled"
            sat_i += 1
        else:
            ko, status = SUN_SLOTS[sun_i % len(SUN_SLOTS)], "scheduled"
            sun_i += 1
        rep = a.matchup(r.home_id, r.away_id, match_id=r.match_id, compact=True)
        hn, an = s.club_name(r.home_id), s.club_name(r.away_id)
        form = rep.get("form", {})
        out.append({
            "id": r.match_id, "round": int(r.round), "date": str(r.date), "ko": ko, "status": status,
            "home": r.home_id, "away": r.away_id, "outlook": predict(r.home_id, r.away_id),
            "preview": {
                "form": {"home": form.get(f"{hn} last 5", ""), "away": form.get(f"{an} last 5", "")},
                "stakes": rep.get("context", {}).get("stakes", {}),
                "managers": rep.get("context", {}).get("managers", {}),
                "h2h": rep.get("head_to_head", [])[:5],
                "edges": [{"title": e["title"], "text": SEASON_NOTE.sub("", e["explanation"]).strip(),
                           "for": a.club_id(e["beneficiary"]) if e.get("beneficiary") else None,
                           "strength": r2(e.get("strength"), 1)} for e in rep.get("edges", [])[:4]],
                "watch": [p["text"] for p in rep.get("predictions_to_track", [])[:4]],
                "news": {a.club_id(k): v for k, v in (rep.get("team_news") or {}).items()},
                "key_players": {a.club_id(k): v for k, v in (rep.get("key_players") or {}).items()},
                "lineups": {a.club_id(k): v for k, v in (rep.get("probable_lineups") or {}).items()},
                "style": rep.get("style_comparison", []),
            },
        })
    return out


# Main

def export(data_dir: str, out_dir: Path) -> dict:
    a = Analyst(data_dir)
    s = a.store
    seasons = sorted(s.seasons)
    current = s.current_season
    prev = seasons[seasons.index(current) - 1] if seasons.index(current) > 0 else None
    clubs_df = s.clubs
    cs = pd.read_csv(Path(data_dir) / "public" / "club_seasons.csv")
    codes = short_codes(clubs_df)
    crests = {p.stem.replace("crest-", "") for p in (ROOT / "web" / "assets" / "crests").glob("crest-*.webp")}
    clubs = {}
    for r in clubs_df.itertuples():
        mine = cs[cs.club_id == r.club_id]
        clubs[r.club_id] = {"name": r.name, "code": codes[r.club_id], "town": r.town, "stadium": r.stadium,
                            "kit": [r.kit_primary, r.kit_secondary],
                            "crest": f"assets/crests/crest-{r.club_id}.webp" if r.club_id in crests else None,
                            "div": {x.season: int(x.division) for x in mine.itertuples()},
                            "manager": {x.season: x.manager for x in mine.itertuples()}}
    matches = pd.read_csv(Path(data_dir) / "public" / "matches.csv")
    matches = matches[(matches.stage == "league")]
    tm = s.table("team_match").set_index(["match_id", "team_id"])
    predict, model_note = outlook_model(s, current, prev)
    league = {"league": LEAGUE, "current_season": current, "seasons": seasons, "showcase": s.showcase_meta["match_id"],
              "current_round": int(s.upcoming["round"].min()), "clubs": clubs, "outlook_model": model_note, "season": {}}
    for season in seasons:
        sm = matches[matches.season == season]
        d1 = sm[sm.division == 1]
        rounds = int(d1["round"].max()) if len(d1) else 0
        results = []
        for m in d1.sort_values(["round", "date", "match_id"]).itertuples():
            hx = tm.xg.get((m.match_id, m.home_id))
            ax = tm.xg.get((m.match_id, m.away_id))
            results.append({"id": m.match_id, "round": int(m.round), "date": m.date, "home": m.home_id, "away": m.away_id,
                            "hg": int(m.home_goals), "ag": int(m.away_goals), "hxg": r2(hx, 1), "axg": r2(ax, 1)})
        players, agg = season_players(a, season, set(d1.match_id))
        d1_clubs = sorted(set(d1.home_id) | set(d1.away_id))
        league["season"][season] = {"rounds_played": rounds, "tables": tables(a, season), "results": results,
                                    "leaders": leaders(agg, rounds)}
        sdir = out_dir / season
        sdir.mkdir(parents=True, exist_ok=True)
        dump(sdir / "players.json", players)
        dump(sdir / "matches.json", season_matches(a, season, d1))
        dump(sdir / "clubs.json", season_clubs(a, season, d1_clubs, players))
    league["fixtures"] = fixtures(a, predict, codes)
    dump(out_dir / "league.json", league)
    return league


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=_default), encoding="utf-8")


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default=str(ROOT / "web" / "data"))
    a = ap.parse_args()
    out = Path(a.out)
    league = export(a.data, out)
    sizes = {p.relative_to(out).as_posix(): f"{p.stat().st_size // 1024} KB" for p in sorted(out.rglob("*.json"))}
    print(f"League hub: {len(league['clubs'])} clubs, {len(league['fixtures'])} fixtures this round, "
          f"seasons {', '.join(league['seasons'])}.")
    for k, v in sizes.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
