"""Player match ratings: a transparent 0-10 score built from what each player did.

Every player starts at 6.0 when he comes on. Each action moves the rating by a fixed,
published amount (ACTIONS), so any rating can be explained line by line: "7.4 = 6.0 +
goal 1.0 + 3 key passes 0.45 - 6 misplaced passes 0.21 ...". The same code rates the live
match at any clock and every match of both seasons (for season averages), so a live
rating and a season average are directly comparable.

Weights were calibrated on the 2025-26 season so an ordinary game lands between 6.5 and
7, a strong one around 7.5-8, and only a standout one above 8.5 (see calibrate()).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASE = 6.0
LOW, HIGH = 3.0, 10.0
DEFENDERS = {"CB", "RB", "LB", "LWB", "RWB"}
FINAL_THIRD_X = 70.0

# code: (label, rating change, counts as a touch)
ACTIONS: dict[str, tuple[str, float, bool]] = {
    "goal":      ("Goal", 1.00, True),
    "pen_goal":  ("Penalty scored", 0.70, True),
    "assist":    ("Assist", 0.60, False),
    "key_pass":  ("Key pass", 0.12, False),
    "shot_on":   ("Shot on target", 0.10, True),
    "shot_off":  ("Shot off target", -0.04, True),
    "shot_blk":  ("Shot blocked", 0.00, True),
    "big_miss":  ("Big chance missed", -0.30, False),
    "pass_ft":   ("Accurate pass in the final third", 0.010, True),
    "pass_ok":   ("Accurate pass", 0.003, True),
    "pass_bad":  ("Misplaced pass", -0.035, True),
    "carry":     ("Carry", 0.00, True),
    "drb_ok":    ("Dribble past a man", 0.10, True),
    "drb_bad":   ("Failed dribble", -0.05, True),
    "lost":      ("Dispossessed", -0.08, True),
    "tackle":    ("Tackle won", 0.10, True),
    "intercept": ("Interception", 0.08, True),
    "block":     ("Block", 0.12, False),
    "clear":     ("Clearance", 0.10, True),
    "recover":   ("Ball recovery", 0.02, True),
    "air_won":   ("Header won", 0.06, False),
    "air_lost":  ("Header lost", -0.03, False),
    "save":      ("Save", 0.20, True),          # plus the shot's xG (harder saves count more)
    "claim":     ("Cross claimed", 0.08, True),
    "conceded":  ("Goal conceded", -0.08, False),   # goalkeeper and defenders on the pitch; keepers -0.25
    "clean":     ("Clean sheet", 0.40, False),      # 60+ minutes, nothing conceded; keepers +0.6
    "foul":      ("Foul", -0.05, False),
    "fouled":    ("Fouled", 0.03, False),
    "offside":   ("Caught offside", -0.03, False),
    "yellow":    ("Yellow card", -0.30, False),
    "red":       ("Red card", -1.50, False),
    "own_goal":  ("Own goal", -1.00, True),
}
SAVE_XG_WEIGHT = 1.0
KEEPER_CONCEDED, KEEPER_CLEAN = -0.25, 0.60
BIG_CHANCE_XG = 0.30


def _code(ev: pd.DataFrame) -> pd.Series:
    t, o = ev["type"].astype(str), ev["outcome"].astype(str)
    final = ev.end_x.fillna(0) >= FINAL_THIRD_X
    card = ev.get("card", pd.Series(index=ev.index, dtype=object)).astype(str)
    conds = [
        (t == "pass") & (o == "complete") & final,
        (t == "pass") & (o == "complete"),
        (t == "pass") & o.isin(["incomplete", "out"]),
        (t == "carry"),
        (t == "take_on") & (o == "success"),
        (t == "take_on") & (o == "fail"),
        (t == "dispossessed"),
        (t == "tackle"),
        (t == "interception"),
        (t == "block"),
        (t == "clearance"),
        (t == "ball_recovery"),
        (t == "aerial_duel") & (o == "won"),
        (t == "aerial_duel") & (o == "lost"),
        (t == "gk_claim"),
        (t == "foul"),
        (t == "foul_won"),
        (t == "offside"),
        (t == "card") & (card == "yellow"),
        (t == "card") & card.isin(["red", "second_yellow"]),
        (t == "own_goal"),
    ]
    codes = ["pass_ft", "pass_ok", "pass_bad", "carry", "drb_ok", "drb_bad", "lost", "tackle", "intercept",
             "block", "clear", "recover", "air_won", "air_lost", "claim", "foul", "fouled", "offside",
             "yellow", "red", "own_goal"]
    return pd.Series(np.select(conds, codes, default=""), index=ev.index)


def _on_pitch(lineups: pd.DataFrame, end_minute: pd.Series | dict) -> pd.DataFrame:
    """Each player's on/off minute (players who never came on are dropped)."""
    lu = lineups.copy()
    lu = lu[(lu.started == True) | lu.minute_on.notna()]  # noqa: E712
    lu["on"] = np.where(lu.started == True, 0, lu.minute_on.fillna(0))  # noqa: E712
    ends = lu.match_id.map(end_minute) if isinstance(end_minute, dict) else end_minute
    lu["off"] = lu.minute_off.fillna(ends).astype(float)
    return lu[["match_id", "team_id", "player_id", "position", "on", "off"]]


def actions(ev: pd.DataFrame, shots: pd.DataFrame, lineups: pd.DataFrame) -> pd.DataFrame:
    """Every rated action: match_id, team_id, player_id, clock_s, minute, code, delta.

    ev: events of one or more matches (raw columns); shots: build.build_shots output for them;
    lineups: lineup rows (match_id, team_id, player_id, position, started, minute_on, minute_off).
    """
    cols = ["match_id", "team_id", "player_id", "clock_s", "minute"]
    ev = ev[ev.player_id.notna()]
    base = ev[cols].copy()
    base["code"] = _code(ev)
    base = base[base.code != ""]
    rows = [base]

    sh = shots[shots.kind == "shot"]
    pen = sh.phase.astype(str) == "penalty"
    oc = sh.outcome.astype(str)
    s = sh[cols].copy()
    s["code"] = np.select([(oc == "goal") & pen, oc == "goal", oc == "saved", oc == "off_target"],
                          ["pen_goal", "goal", "shot_on", "shot_off"], default="shot_blk")
    rows.append(s)
    miss = sh[(sh.xg >= BIG_CHANCE_XG) & (oc != "goal")][cols].copy()
    miss["code"] = "big_miss"
    rows.append(miss)
    a = sh[sh.assist_player_id.notna()]
    ka = a[cols].copy()
    ka["player_id"] = a.assist_player_id.astype(str)
    ka["code"] = np.where(a.is_goal, "assist", "key_pass")
    rows.append(ka)
    # Saves: credited from the shot, worth more the better the chance was.
    sv = sh[(oc == "saved") & sh.goalkeeper_id.notna()]
    saves = sv[cols].copy()
    saves["player_id"] = sv.goalkeeper_id.astype(str)
    saves["team_id"] = sv.opponent_id.astype(str)
    saves["code"] = "save"
    saves["extra"] = SAVE_XG_WEIGHT * sv.xg.fillna(0).values
    rows.append(saves)

    out = pd.concat(rows, ignore_index=True)
    out["extra"] = out.get("extra", pd.Series(0.0, index=out.index)).fillna(0.0)

    # Goals conceded and clean sheets for keepers and defenders on the pitch.
    end_min = ev.groupby("match_id").minute.max().to_dict()
    end_clock = ev.groupby("match_id").clock_s.max().to_dict()
    lu = _on_pitch(lineups[lineups.match_id.isin(end_min)], end_min)
    lu = lu[lu.position.isin(DEFENDERS | {"GK"})]
    goals = shots[shots.is_goal][["match_id", "scoring_team_id", "clock_s", "minute"]]
    if not goals.empty and not lu.empty:
        g = goals.merge(lu, on="match_id")
        g = g[(g.team_id != g.scoring_team_id) & (g.minute >= g.on) & (g.minute <= g.off)]
        c = g[cols].copy()
        c["code"] = "conceded"
        c["extra"] = np.where(g.position == "GK", KEEPER_CONCEDED - ACTIONS["conceded"][1], 0.0)
        out = pd.concat([out, c], ignore_index=True)
        conceded_players = set(zip(c.match_id, c.player_id))
    else:
        conceded_players = set()
    cs = lu[(lu.off - lu.on >= 60)]
    cs = cs[[(m, p) not in conceded_players for m, p in zip(cs.match_id, cs.player_id)]]
    if not cs.empty:
        cl = pd.DataFrame({"match_id": cs.match_id, "team_id": cs.team_id, "player_id": cs.player_id,
                           "clock_s": cs.match_id.map(end_clock), "minute": cs.match_id.map(end_min),
                           "code": "clean",
                           "extra": np.where(cs.position == "GK", KEEPER_CLEAN - ACTIONS["clean"][1], 0.0)})
        out = pd.concat([out, cl], ignore_index=True)

    out["delta"] = out.code.map({k: v[1] for k, v in ACTIONS.items()}).astype(float) + out.extra
    out["player_id"] = out.player_id.astype(str)
    out["team_id"] = out.team_id.astype(str)
    return out.drop(columns="extra").sort_values(["match_id", "clock_s"], kind="stable").reset_index(drop=True)


def clamp(x):
    return np.clip(x, LOW, HIGH)


def match_ratings(acts: pd.DataFrame, lineups: pd.DataFrame, upto_clock: float | None = None) -> pd.DataFrame:
    """Rating per player who has been on the pitch (by upto_clock, if given)."""
    a = acts if upto_clock is None else acts[acts.clock_s <= upto_clock]
    played = lineups[(lineups.started == True) | lineups.minute_on.notna()][["match_id", "team_id", "player_id"]]  # noqa: E712
    total = a.groupby(["match_id", "player_id"]).delta.sum()
    r = played.copy()
    r["player_id"] = r.player_id.astype(str)
    r["rating"] = clamp(BASE + r.set_index(["match_id", "player_id"]).index.map(total).fillna(0.0).astype(float))
    return r.reset_index(drop=True)


def breakdown(acts: pd.DataFrame, top: int | None = None) -> list[dict]:
    """One player's actions grouped: [{'action', 'count', 'change'}], biggest effect first."""
    if acts.empty:
        return []
    g = acts.groupby("code").agg(count=("delta", "size"), change=("delta", "sum")).reset_index()
    g = g[g.change.abs() >= 0.005].copy()
    g["action"] = g.code.map(lambda c: ACTIONS[c][0])
    g = g.reindex(g.change.abs().sort_values(ascending=False).index)
    rows = [{"action": r.action, "count": int(r["count"]), "change": round(float(r.change), 2)} for _, r in g.iterrows()]
    return rows[:top] if top else rows


def stat_line(acts: pd.DataFrame) -> dict:
    """The counts fans look for, from one player's actions."""
    c = acts.code.value_counts().to_dict()
    n = lambda *k: int(sum(c.get(x, 0) for x in k))  # noqa: E731
    passes = n("pass_ft", "pass_ok", "pass_bad")
    return {
        "goals": n("goal", "pen_goal"), "assists": n("assist"), "key_passes": n("key_pass", "assist"),
        "shots": n("goal", "pen_goal", "shot_on", "shot_off", "shot_blk"),
        "shots_on_target": n("goal", "pen_goal", "shot_on"),
        "passes": passes, "passes_accurate": n("pass_ft", "pass_ok"), "passes_misplaced": n("pass_bad"),
        "touches": int(acts.code.map(lambda k: ACTIONS[k][2]).sum()) if len(acts) else 0,
        "dribbles": n("drb_ok"), "dribbles_tried": n("drb_ok", "drb_bad"), "dispossessed": n("lost"),
        "tackles": n("tackle"), "interceptions": n("intercept"), "blocks": n("block"), "clearances": n("clear"),
        "recoveries": n("recover"), "headers_won": n("air_won"), "headers": n("air_won", "air_lost"),
        "saves": n("save"), "fouls": n("foul"), "fouled": n("fouled"), "yellow": n("yellow"), "red": n("red"),
    }


def season_ratings(store, seasons: list[str] | None = None) -> pd.DataFrame:
    """Rating of every player in every match of the given seasons (for averages and calibration)."""
    from . import xt
    from .build import build_shots, enrich
    grid = xt.from_json(store.xt_grid)
    out = []
    for season in seasons or store.seasons:
        ev = enrich(store.events(season), grid, store.matches)
        shots = build_shots(ev, season, store.matches)
        lu = store.lineups[store.lineups.season == season]
        acts = actions(ev, shots, lu)
        r = match_ratings(acts, lu)
        r["season"] = season
        out.append(r)
    return pd.concat(out, ignore_index=True)


def calibrate(store) -> dict:
    """Distribution check: ratings of players with 45+ minutes, by position."""
    r = season_ratings(store, [store.seasons[0]])
    lu = store.lineups[["match_id", "player_id", "position", "minutes"]].astype({"player_id": str})
    r = r.merge(lu, on=["match_id", "player_id"])
    r = r[r.minutes >= 45]
    q = r.rating.quantile([0.1, 0.5, 0.9, 0.99]).round(2).to_dict()
    return {"n": len(r), "mean": round(r.rating.mean(), 2), "quantiles": q, "max": round(r.rating.max(), 2),
            "by_position": r.groupby("position").rating.mean().round(2).to_dict()}
