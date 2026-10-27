"""Export everything the web app needs for the showcase match into one JSON file.

    uv run scripts/export_web.py                       # uses data/runtime/broadcast (the latest broadcast run)
    uv run scripts/export_web.py --broadcast <folder>  # a different run's output
    uv run scripts/export_web.py --offline             # no broadcast run yet: build one with safe templates

Writes web/data/match.json. The app replays the match from it: every number on screen
comes from the analytics engine or from verified broadcast cues.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics import rating as rating_mod  # noqa: E402
from analytics.api import Analyst  # noqa: E402
from analytics.metrics import PLAYER_METRICS  # noqa: E402

WHEEL = {   # six metrics per role, short labels for the percentile wheel
    "ST": [("goals_p90", "Goals"), ("npxg_p90", "Chances (xG)"), ("shots_p90", "Shots"),
           ("finishing_over_xg", "Finishing"), ("aerial_win_rate", "Headers won"), ("xt_p90", "Threat (xT)")],
    "W": [("npxg_p90", "Chances (xG)"), ("xa_p90", "Chances made"), ("take_on_success", "Dribbling"),
          ("xt_p90", "Threat (xT)"), ("progressive_carries_p90", "Carries forward"), ("cross_completion", "Crossing")],
    "AM": [("xt_p90", "Threat (xT)"), ("xa_p90", "Chances made"), ("key_passes_p90", "Key passes"),
           ("npxg_p90", "Chances (xG)"), ("take_on_success", "Dribbling"), ("progressive_passes_p90", "Passes forward")],
    "CM": [("xt_p90", "Threat (xT)"), ("progressive_passes_p90", "Passes forward"),
           ("completion_over_expected", "Passing"), ("tackles_interceptions_p90", "Ball winning"),
           ("pressures_p90", "Pressing"), ("dispossessed_per_pressed", "Press resistance")],
    "DM": [("tackles_interceptions_p90", "Ball winning"), ("completion_over_expected", "Passing"),
           ("progressive_passes_p90", "Passes forward"), ("pressures_p90", "Pressing"),
           ("dispossessed_per_pressed", "Press resistance"), ("aerial_win_rate", "Headers won")],
    "CB": [("aerial_win_rate", "Headers won"), ("tackles_interceptions_p90", "Ball winning"),
           ("completion_over_expected", "Passing"), ("progressive_passes_p90", "Passes forward"),
           ("dispossessed_per_pressed", "Press resistance"), ("fouls_cards_p90", "Discipline")],
    "FB": [("tackles_interceptions_p90", "Ball winning"), ("progressive_passes_p90", "Passes forward"),
           ("cross_completion", "Crossing"), ("xa_p90", "Chances made"),
           ("dispossessed_per_pressed", "Press resistance"), ("take_on_success", "Dribbling")],
    "GK": [("gk_goals_prevented", "Shot stopping"), ("gk_claim_rate", "Claiming crosses"),
           ("pass_completion", "Passing"), ("long_pass_completion", "Long passing")],
}
ROLE = {"RW": "W", "LW": "W", "RB": "FB", "LB": "FB"}
EVENT_TYPES = ["pass", "carry", "take_on", "shot", "dispossessed", "tackle", "interception", "clearance",
               "aerial_duel", "foul", "card", "substitution", "injury", "ball_recovery", "own_goal", "offside",
               "gk_save", "block"]


def portrait_kits() -> dict[str, str]:
    """player_id -> the club whose kit he wears in his portrait (web/assets/players/kits.json)."""
    folder = ROOT / "web" / "assets" / "players"
    kits = json.loads((folder / "kits.json").read_text(encoding="utf-8")) if (folder / "kits.json").exists() else {}
    return {pid: club for pid, club in kits.items() if (folder / f"{pid}.webp").exists()}

def r(v, n=3):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(float(v), n)


def contrast_ok(hex_color: str) -> bool:
    """Is this kit colour light enough to read on the dark pitch background?"""
    h = hex_color.lstrip("#")
    rr, gg, bb = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * rr + 0.7152 * gg + 0.0722 * bb
    return lum > 0.16


def side_colour(primary: str, secondary: str, avoid: str | None = None) -> str:
    for c in (primary, secondary):
        if contrast_ok(c) and c.upper() not in ("#FFFFFF", "#FFF") and c != avoid:
            return c
    return secondary if contrast_ok(secondary) else "#D9D9D9"


def club_block(a: Analyst, cid: str, meta: dict, report: dict, avoid: str | None = None) -> dict:
    s = a.store
    row = s.clubs[s.clubs.club_id == cid].iloc[0]
    stakes = report["context"]["stakes"].get(cid, {})
    mgr = s.club_season(cid, s.current_season) or {}
    return {
        "id": cid, "name": row["name"], "short": row.short_name, "town": row.town, "stadium": row.stadium,
        "kit": [row.kit_primary, row.kit_secondary],
        "colour": side_colour(row.kit_primary, row.kit_secondary, avoid),
        "position": stakes.get("position"), "points": stakes.get("points"), "zone": stakes.get("zone"),
        "manager": mgr.get("manager"), "philosophy": mgr.get("manager_philosophy"),
    }


def player_sheet(a: Analyst, pid: str, side: str, shirt: int | None, team_news_ids: dict) -> dict:
    s = a.store
    prof = a.player_profile(pid)
    pos = prof["position"]
    role = ROLE.get(pos, pos)
    seasons = {}
    for season, block in prof["seasons"].items():
        if not block or "metrics" not in block:
            continue
        wheel = []
        for key, label in WHEEL.get(role, WHEEL["CM"]):
            m = block["metrics"].get(key)
            if not m or m.get("percentile") is None:
                continue
            pct = float(m["percentile"])
            if PLAYER_METRICS.get(key) and PLAYER_METRICS[key].better == "low":
                pct = 100 - pct
            wheel.append({"key": key, "label": label, "pct": round(pct), "value": r(m["value"]),
                          "median": r(m.get("position_median")), "full_label": m["label"]})
        seasons[season] = {"club": block.get("club"), "minutes": int(block.get("minutes") or 0),
                           "matches": int(block.get("matches") or 0), "starts": int(block.get("starts") or 0),
                           "goals": int(block.get("goals") or 0), "assists": int(block.get("assists") or 0),
                           "wheel": wheel}
    em = a.player_event_map(pid)
    findings = []
    for f in a.scout.findings(prof["club_id"], s.current_season, min_confidence="medium") if prof.get("club_id") else []:
        if f.get("player_id") == pid:
            findings.append({"summary": f["summary"].split(" (20")[0], "confidence": f["confidence"],
                             "direction": f["direction"]})
    return {
        "id": pid, "name": prof["name"], "pos": pos, "age": prof.get("age"), "height": prof.get("height_cm"),
        "foot": prof.get("preferred_foot"), "side": side, "num": shirt,
        "seasons": seasons, "availability": prof.get("availability"), "injuries": prof.get("injury_record"),
        "lost_ball": {k: {"count": v["count"], "by_zone": v["by_zone"]} for k, v in em["maps"].items()},
        "findings": findings[:3],
        "news": team_news_ids.get(pid),
        "ratings": prof.get("match_ratings") or {},
    }


HEAT_BINS = (21, 14)          # 5 m x ~4.9 m cells, in the player's own attacking frame (x toward goal)
ON_BALL = ["pass", "carry", "take_on", "shot", "dispossessed", "tackle", "interception", "clearance",
           "aerial_duel", "ball_recovery", "block", "gk_save", "gk_claim", "foul_won"]


def season_heat(a: Analyst, pids: list[str]) -> dict[str, dict[str, list[int]]]:
    """Where each player was involved, per season: a coarse grid scaled 0-100 (for the player card heat map)."""
    import numpy as np
    out: dict[str, dict[str, list[int]]] = {p: {} for p in pids}
    for season in a.store.seasons:
        ev = a.store.events(season, columns=["player_id", "type", "x", "y"])
        ev = ev[ev.player_id.astype(str).isin(pids) & ev["type"].astype(str).isin(ON_BALL) & ev.x.notna()]
        for pid, g in ev.groupby(ev.player_id.astype(str)):
            h, _, _ = np.histogram2d(g.x.clip(0, 104.9), g.y.clip(0, 67.9), bins=HEAT_BINS, range=[[0, 105], [0, 68]])
            if h.max() > 0:
                out[pid][season] = [int(round(v)) for v in (100 * h.T / h.max()).ravel()]   # rows = y bins
    return out


def season_stats(a: Analyst, pid: str) -> dict:
    """Per-game numbers for the player card, from the player-match table."""
    pm = a.store.table("player_match")
    me = pm[pm.player_id.astype(str) == pid]
    out = {}
    for season, g in me.groupby("season"):
        n = len(g)
        if not n:
            continue
        s = g.sum(numeric_only=True)
        per = lambda col: round(float(s[col]) / n, 2) if col in s else None  # noqa: E731
        rate = lambda won, tot: round(float(s[won]) / float(s[tot]), 3) if col_ok(s, tot) else None  # noqa: E731
        touches = sum(float(s[c]) for c in ("passes", "carries", "take_ons", "shots", "dispossessed", "clearances",
                                           "ball_recoveries", "tackles", "interceptions", "saves", "claims") if c in s)
        out[season] = {
            "matches": n, "minutes": int(s["minutes"]), "goals": int(s["goals"]), "assists": int(s["assists"]),
            "touches_pg": round(touches / n, 1), "recoveries_pg": per("ball_recoveries"),
            "tackles_int_pg": round((float(s["tackles"]) + float(s["interceptions"])) / n, 2),
            "headers_won_pg": per("aerials_won"), "header_rate": rate("aerials_won", "aerials"),
            "key_passes_pg": per("key_passes"), "pass_rate": rate("passes_completed", "passes"),
            "passes_pg": per("passes"), "shots_pg": per("shots"), "xg_pg": per("xg"),
            "dribbles_pg": per("take_ons_won"), "dribble_rate": rate("take_ons_won", "take_ons"),
            "saves_pg": per("saves"), "clearances_pg": per("clearances"), "clean_sheets": None,
        }
    return out


def col_ok(s, col) -> bool:
    return col in s and float(s[col]) > 0


def store_name(a: Analyst, cid: str) -> str:
    return a.store.club_name(cid)


def load_broadcast(folder: Path) -> tuple[dict | None, list, dict | None]:
    brief = json.loads((folder / "brief.json").read_text(encoding="utf-8")) if (folder / "brief.json").exists() else None
    cues = []
    if (folder / "cues.jsonl").exists():
        cues = [json.loads(x) for x in (folder / "cues.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    recap = json.loads((folder / "recap.json").read_text(encoding="utf-8")) if (folder / "recap.json").exists() else None
    return brief, cues, recap


def slim_cue(c: dict) -> dict:
    return {"id": c["cue_id"], "phase": c["phase"], "kind": c["kind"], "clock": c["clock_s"], "minute": c["minute"],
            "priority": c["priority"], "duration": c["duration_s"], "overlay": c["overlay"], "facts": c["facts"],
            "angle": c.get("angle"), "variants": c["variants"],
            "refs": [x["event_id"] for x in (c.get("evidence") or {}).get("event_refs", [])],
            "checked": {"attempts": c["verification"]["attempts"],
                        "rejected": sum(len(h["problems"]) for h in c["verification"]["rejections"]),
                        "degraded": c["verification"]["degraded"]}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--broadcast", help="folder with brief.json / cues.jsonl / recap.json")
    ap.add_argument("--offline", action="store_true", help="run an offline broadcast first (no model)")
    ap.add_argument("--out", default=str(ROOT / "web" / "data" / "match.json"))
    args = ap.parse_args()

    bdir = Path(args.broadcast) if args.broadcast else Path(args.data) / "runtime" / "broadcast"
    if args.offline:
        from agents.config import BroadcastConfig
        from agents.runner import Broadcast
        bdir = Path(args.data) / "runtime" / "broadcast_offline"
        cfg = BroadcastConfig(data_dir=args.data, mode="offline", languages=("es", "ar", "hi", "ml"), out_dir=str(bdir),
                              verbose=False)
        asyncio.run(Broadcast(cfg).run())

    a = Analyst(args.data)
    s = a.store
    meta = s.showcase_meta
    live = a.live
    report = a.showcase_report()
    hid, aid = meta["home_id"], meta["away_id"]
    home = club_block(a, hid, meta, report)
    away = club_block(a, aid, meta, report, avoid=home["colour"])
    home["formation"], away["formation"] = meta.get("home_formation"), meta.get("away_formation")

    ev = live.ev
    end = live.end_clock
    periods = []
    for p in (1, 2):
        e = ev[ev.period == p]
        periods.append({"period": p, "start": r(e.clock_s.min(), 1), "end": r(e.clock_s.max(), 1),
                        "start_minute": int(e.minute.min()), "end_minute": int(e.minute.max())})

    # Line-ups with shirt numbers.
    sq = s.squads[s.squads.season == s.current_season]
    shirt = dict(zip(sq.player_id, sq.shirt))
    lu = s.showcase_lineups
    lineups = {}
    for side, cid in (("home", hid), ("away", aid)):
        rows = lu[lu.team_id == cid]
        lineups[side] = [{"id": r_.player_id, "name": s.player_name(r_.player_id),
                          "num": int(shirt.get(r_.player_id, 0)) or None,
                          "pos": r_.position if isinstance(r_.position, str) else s.player_positions.get(r_.player_id),
                          "slot": r_.slot if isinstance(r_.slot, str) else None,
                          "start": bool(r_.started)} for r_ in rows.itertuples() if (r_.started or r_.minutes > 0)]

    news = {"home": a.team_news(hid), "away": a.team_news(aid)}
    news_ids = {}
    for side in ("home", "away"):
        for x in news[side].get("unavailable", []) + news[side].get("doubtful", []):
            news_ids[x["player_id"]] = {"status": x["status"], "reason": x["reason"],
                                        "expected_return": x.get("expected_return")}

    # The match minute by minute.
    timeline = []
    clock = 0.0
    while True:
        clock = min(clock + 60.0, end)
        st = live.state(clock)
        h, w = st["home"], st["away"]
        l10 = st["last_10_minutes"]
        timeline.append({"c": r(clock, 1), "m": st["clock"]["minute"], "p": st["clock"]["period"],
                         "s": [h["goals"], w["goals"]], "xg": [r(h["xg"], 2), r(w["xg"], 2)],
                         "sh": [h["shots"], w["shots"]], "sot": [h["shots_on_target"], w["shots_on_target"]],
                         "pos": [r(h["possession"], 3), r(w["possession"], 3)],
                         "tilt": [r(h["field_tilt"], 3), r(w["field_tilt"], 3)],
                         "t10": [r(l10["home"]["field_tilt"], 3), r(l10["away"]["field_tilt"], 3)],
                         "pass": [h["passes"], w["passes"]], "corners": [h["corners"], w["corners"]],
                         "fouls": [h["fouls"], w["fouls"]], "cards": [h["yellow_cards"], w["yellow_cards"]],
                         "chaos": r(st["tempo"].get("chaos_index"), 0)})
        if clock >= end:
            break
    momentum = [{"m": b["from_minute"], "net": r(b["net"], 3)} for b in live.momentum(end)]

    # Predictions with their status over time.
    preds_full = {p["prediction_id"]: p for p in report["predictions_to_track"]}
    pred_rows = {pid: [] for pid in preds_full}
    for t in timeline:
        for p in a.live_predictions(t["c"]):
            pred_rows[p["prediction_id"]].append([t["m"], r(p["value"], 3), p["status"]])
    predictions = []
    for pid, p in preds_full.items():
        predictions.append({"id": pid, "text": p["text"], "label": p["label"], "subject": p["subject"],
                            "subject_type": p["subject_type"], "measure": p["measure"], "kind": p["kind"],
                            "confirm_at": p["confirm_at"],
                            "expected": p.get("expected_if_trait_holds"),
                            "average": p.get("expected_average") or p.get("expected_average_player"),
                            "timeline": pred_rows[pid]})

    # Events (compact) for pitch maps and live player lines.
    pidx = {}
    players_order = []
    for side in ("home", "away"):
        for pl in lineups[side]:
            pidx[pl["id"]] = len(players_order)
            players_order.append(pl["id"])
    shots = live.shots
    xg_by_event = dict(zip(shots.event_id, shots.xg))
    events = []
    for e in ev[ev.t.isin(EVENT_TYPES)].itertuples():
        team = 0 if e.team == hid else 1
        pi = pidx.get(e.player_id if isinstance(e.player_id, str) else str(e.player_id), -1)
        events.append([r(e.clock_s, 1), int(e.minute), team, pi, e.t,
                       None if not isinstance(e.o, str) else e.o,
                       r(e.x, 1), r(e.y, 1), r(e.end_x, 1), r(e.end_y, 1),
                       r(xg_by_event.get(e.event_id), 3) if e.t in ("shot", "own_goal") else None,
                       int(e.event_id)])
    moments = a.live_key_moments(end, 0.0, 0.0)

    sheets = {}
    for side, cid in (("home", hid), ("away", aid)):
        probable = (report["probable_lineups"].get(store_name(a, cid), {}) or {}).get("players", [])
        ids = ([pl["id"] for pl in lineups[side]] + [x["player_id"] for x in news[side].get("unavailable", [])]
               + [p_["player_id"] for p_ in probable])
        for pid in dict.fromkeys(ids):
            try:
                sheets[pid] = player_sheet(a, pid, side, int(shirt.get(pid, 0)) or None, news_ids)
            except Exception as ex:  # a player with too little data
                print(f"  skipped {pid}: {ex}")

    # Player card: per-game season numbers, season heat maps and the portrait, if there is one.
    heat = season_heat(a, list(sheets))
    kits = portrait_kits()
    for pid, sheet in sheets.items():
        sheet["season_stats"] = season_stats(a, pid)
        sheet["heat"] = heat.get(pid, {})
        club = hid if sheet["side"] == "home" else aid
        sheet["photo"] = f"assets/players/{pid}.webp" if kits.get(pid) == club else None

    # Match ratings: every rated action as [clock, action index, change]; the app adds them up to its clock.
    codes = list(rating_mod.ACTIONS)
    acts = a.live.rating_actions
    for pid, sheet in sheets.items():
        mine = acts[acts.player_id == pid]
        sheet["acts"] = [[r(c, 1), codes.index(k), round(float(d), 3)] for c, k, d in zip(mine.clock_s, mine.code, mine.delta)]
    subs_on = {str(e.related_player_id): r(e.clock_s, 1) for e in ev[ev.t == "substitution"].itertuples()}
    for side in ("home", "away"):
        for pl in lineups[side]:
            pl["on_clock"] = 0.0 if pl["start"] else subs_on.get(pl["id"])

    brief, cues, recap = load_broadcast(bdir)
    table = a.league_table()["table"] if "table" in a.league_table() else []
    viewers = sorted({k for c in cues for k in c["variants"]})

    bundle = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"broadcast_folder": str(bdir), "cues": len(cues),
                   "llm_cues": sum(any(v.get("source") == "llm" for v in c["variants"].values()) for c in cues)},
        "match": {"id": meta["match_id"], "date": meta["date"], "round": meta["round"], "season": meta["season"],
                  "stadium": home["stadium"], "home": home, "away": away, "end": r(end, 1), "periods": periods,
                  "midweek_europe": report["context"].get("midweek_europe")},
        "lineups": lineups, "players_order": players_order,
        "team_news": {side: {"summary": news[side].get("summary"),
                             "out": [{"id": x["player_id"], "name": x["player"], "pos": x["position"],
                                      "status": x["status"], "reason": x["reason"],
                                      "expected_return": x.get("expected_return"),
                                      "matches_remaining": x.get("matches_remaining"),
                                      "regular": x.get("regular_starter")}
                                     for x in news[side].get("unavailable", []) + news[side].get("doubtful", [])]}
                      for side in ("home", "away")},
        "probable": {side: report["probable_lineups"].get(blk["name"], {}) for side, blk in (("home", home), ("away", away))},
        "brief": brief,
        "edges": [{"id": e["edge_id"], "title": e["title"], "beneficiary": e["beneficiary"],
                   "text": e["explanation"]} for e in report["edges"]],
        "predictions": predictions,
        "timeline": timeline, "momentum": momentum,
        "events": events,
        "event_fields": ["clock", "minute", "team", "player", "type", "outcome", "x", "y", "end_x", "end_y", "xg", "id"],
        "moments": [{"id": m["moment_id"], "clock": m["clock_s"], "minute": m["minute"], "type": m["type"],
                     "team": 0 if m["team_id"] == hid else 1, "facts": m["facts"], "importance": m["importance"]}
                    for m in moments if m["type"] in ("goal", "red_card", "yellow_card", "injury", "big_chance",
                                                      "penalty_missed", "substitution")],
        "players": sheets,
        "heat_bins": list(HEAT_BINS),
        "rating_scale": {"base": rating_mod.BASE, "low": rating_mod.LOW, "high": rating_mod.HIGH,
                         "actions": [[k, v[0], v[1], v[2]] for k, v in rating_mod.ACTIONS.items()]},
        "cues": [slim_cue(c) for c in cues],
        "viewers": viewers,
        "recap": recap,
        "table": table,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB): {len(cues)} cues, {len(events)} events, "
          f"{len(sheets)} player sheets, {len(timeline)} minutes")


if __name__ == "__main__":
    main()
