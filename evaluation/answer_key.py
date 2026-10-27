"""Score scouting findings against the hidden answer key."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

# category -> (hidden column, direction) used to check unplanted findings against
# the hidden ratings: "low" means the finding claims the rating is unusually low.
PLAYER_ATTR = {
    "loses_ball_under_pressure": ("press_resistance", "low"),
    "press_resistant_playmaker": ("press_resistance", "high"),
    "error_prone_passer": ("passing", "low"),
    "weak_in_the_air": ("aerial", "low"),
    "strong_in_the_air": ("aerial", "high"),
    "hothead": ("discipline", "low"),
    "goalkeeper_weak_on_crosses": ("gk_claiming", "low"),
    "clinical_finisher": ("finishing", "high"),
    "wasteful_finisher": ("finishing", "low"),
    "elite_crosser": ("crossing", "high"),
    "creative_hub": ("vision", "high"),
    "goalkeeper_shot_stopper": ("gk_shot_stopping", "high"),
    "goalkeeper_weak_shot_stopper": ("gk_shot_stopping", "low"),
}
TEAM_ATTR = {
    "set_piece_defense_weak": ("set_piece_defense", "low"),
    "set_piece_attack_strong": ("set_piece_attack", "high"),
    "late_fade": ("fitness", "low"),
    "high_line_exposed": ("line_height", "high"),
    "vulnerable_to_counters": ("line_height", "high"),
    "poor_discipline": ("discipline", "low"),
    "fortress_home": ("home_boost", "high"),
    "left_flank_focus": ("left_bias", "high"),
    "right_flank_focus": ("right_bias", "high"),
    "intense_press": ("press_intensity", "high"),
    "passive_press": ("press_intensity", "low"),
    "direct_style": ("directness", "high"),
    "possession_style": ("directness", "low"),
}
SUPPORT_PCT = 20.0  # hidden rating in the worst/best 20% of peers counts as support


def hidden_support(findings: list[dict], data_dir: str | Path, season: str) -> list[bool | None]:
    """For each finding: does the hidden rating back it up? None = not checkable."""
    hid = Path(data_dir) / "hidden"
    pa = pd.read_csv(hid / "player_attributes.csv")
    pa = pa[pa.season == season]
    ts = pd.read_csv(hid / "team_styles.csv")
    ts = ts[ts.season == season]
    out: list[bool | None] = []
    for f in findings:
        if f["scope"] == "player" and f["category"] in PLAYER_ATTR:
            col, d = PLAYER_ATTR[f["category"]]
            me = pa[pa.player_id == f["player_id"]]
            if me.empty:
                out.append(None)
                continue
            if f["category"] == "creative_hub":
                pa = pa.assign(creative=pa[["passing", "vision", "dribbling"]].mean(axis=1))
                col = "creative"
                me = pa[pa.player_id == f["player_id"]]
            me = me.iloc[0]
            div = ts.set_index("club_id").division.get(me.club_id)
            peers = pa[(pa.position == me.position) & pa.club_id.map(ts.set_index("club_id").division).eq(div)][col]
        elif f["scope"] == "team" and f["category"] in TEAM_ATTR:
            col, d = TEAM_ATTR[f["category"]]
            me = ts[ts.club_id == f["club_id"]]
            if me.empty:
                out.append(None)
                continue
            me = me.iloc[0]
            peers = ts[ts.division == me.division][col]
        else:
            out.append(None)
            continue
        pct = float((peers < me[col]).mean() * 100 + (peers == me[col]).mean() * 50)
        out.append(pct <= SUPPORT_PCT if d == "low" else pct >= 100 - SUPPORT_PCT)
    return out


def load_truths(data_dir: str | Path, season: str) -> list[dict]:
    path = Path(data_dir) / "hidden" / "answer_key.json"
    key = json.loads(path.read_text(encoding="utf-8"))
    return key["seasons"].get(season, [])


def _subject(item: dict) -> str:
    return item["player_id"] if item.get("scope") == "player" else item["club_id"]


def score(findings: list[dict], truths: list[dict], clubs: set[str] | None = None,
          support: list[bool | None] | None = None) -> dict:
    """findings: dicts with scope, club_id, player_id, category, confidence, in_catalogue. support: optional
    hidden-rating support per finding (see hidden_support)."""
    if clubs is not None:
        truths = [t for t in truths if t["club_id"] in clubs]
    catalogue = {t["trait"] for t in truths} | {f["category"] for f in findings if f.get("in_catalogue", True)}
    truth_index = {(_subject(t), t["trait"]): t for t in truths}
    matched_truths: set[tuple] = set()
    rows = []
    support = support if support is not None else [None] * len(findings)
    all_rows = []
    for f, sup in zip(findings, support):
        k = (_subject(f), f["category"])
        hit = k in truth_index
        t = truth_index.get(k)
        row = {**{x: f.get(x) for x in ("finding_id", "club", "player", "category", "confidence", "z")},
               "match": hit, "truth_planted": None if t is None else t["planted"],
               "supported": bool(hit or sup) if (hit or sup is not None) else None}
        all_rows.append(row)
        if not f.get("in_catalogue", True):
            continue
        if hit:
            matched_truths.add(k)
        rows.append(row)
    planted = [t for t in truths if t["planted"]]
    found_planted = [t for t in planted if (_subject(t), t["trait"]) in matched_truths]
    by_trait = defaultdict(lambda: [0, 0])
    for t in planted:
        by_trait[t["trait"]][1] += 1
        if (_subject(t), t["trait"]) in matched_truths:
            by_trait[t["trait"]][0] += 1
    by_conf = defaultdict(lambda: [0, 0])
    for r in rows:
        by_conf[r["confidence"]][1] += 1
        by_conf[r["confidence"]][0] += int(r["match"])
    natural = [t for t in truths if not t["planted"]]
    checkable = [r for r in all_rows if r["supported"] is not None]
    sup_conf = defaultdict(lambda: [0, 0])
    for r in checkable:
        sup_conf[r["confidence"]][1] += 1
        sup_conf[r["confidence"]][0] += int(r["supported"])
    return {
        "findings_checkable": len(checkable),
        "precision_hidden_ratings": round(sum(r["supported"] for r in checkable) / len(checkable), 3) if checkable else None,
        "precision_hidden_by_confidence": {c: {"supported": a, "findings": b, "precision": round(a / b, 3) if b else None}
                                           for c, (a, b) in sorted(sup_conf.items())},
        "unsupported_findings": [r for r in checkable if not r["supported"]],
        "planted_truths": len(planted),
        "planted_found": len(found_planted),
        "recall": round(len(found_planted) / len(planted), 3) if planted else None,
        "natural_truths": len(natural),
        "natural_found": sum((_subject(t), t["trait"]) in matched_truths for t in natural),
        "findings_scored": len(rows),
        "findings_matched": sum(r["match"] for r in rows),
        "precision_lower_bound": round(sum(r["match"] for r in rows) / len(rows), 3) if rows else None,
        "precision_by_confidence": {c: {"matched": a, "findings": b, "precision": round(a / b, 3) if b else None}
                                    for c, (a, b) in sorted(by_conf.items())},
        "recall_by_trait": {k: f"{a}/{b}" for k, (a, b) in sorted(by_trait.items())},
        "missed": [{"club": t["club_name"], "player": t.get("player_name"), "trait": t["trait"]}
                   for t in planted if (_subject(t), t["trait"]) not in matched_truths],
        "unmatched_findings": [r for r in rows if not r["match"]],
        "catalogue": sorted(catalogue),
    }
