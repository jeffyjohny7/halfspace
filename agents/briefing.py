"""Code-side support for the Scout and Recap agents.

* checking a pre-match brief against the evidence (and a safe brief built from the
  matchup report when the model is unavailable);
* the full-time fact sheet the Recap agent writes from, checking its recap, and a
  safe recap.
"""

from __future__ import annotations

import json
import re

from analytics.api import Analyst
from analytics.matchup import ordinal

from .schemas import PreMatchBrief, Recap, Storyline
from .state import BroadcastState
from .verifier import Verifier

SEASON_NOTE = re.compile(r"\s*\(20\d\d-\d\d:[^)]*\)")


def tidy(text: str) -> str:
    """Drop the '(2026-27: 0.56, 10 matches; ...)' sample notes from engine text."""
    text = SEASON_NOTE.sub("", text).replace(".;", ";").replace(";.", ".")
    return re.sub(r"\s{2,}", " ", text).strip()


def team_news_storylines(report: dict) -> list[Storyline]:
    """A storyline for each club missing regular starters, with who is expected to come in."""
    out = []
    fx = report["fixture"]
    for club, cid in ((fx["home"], fx["home_id"]), (fx["away"], fx["away_id"])):
        news = (report.get("team_news") or {}).get(club) or {}
        regulars = [x for x in news.get("unavailable") or [] if x.get("regular_starter")]
        if not regulars:
            continue
        parts = [f"{x['player']} ({x['position']}, {x['reason']})" for x in regulars[:3]]
        text = (f"{club} are without {len(parts)} regular starter{'s' if len(parts) > 1 else ''}: "
                + ", ".join(parts) + ".")
        changes = (report.get("probable_lineups") or {}).get(club, {}).get("changes") or []
        if changes:
            c = changes[0]
            text += f" {c['in']} is expected to replace {c['out']}."
        out.append(Storyline(title=f"{club} team news", text=text, evidence_ids=[f"team_news:{cid}"],
                             confidence="high"))
    return out


def known_ids(report: dict) -> set[str]:
    ids = {e["edge_id"] for e in report["edges"]} | {p["prediction_id"] for p in report["predictions_to_track"]}
    ids |= {f"team_news:{report['fixture']['home_id']}", f"team_news:{report['fixture']['away_id']}"}
    for fs in report["findings"].values():
        ids |= {f["finding_id"] for f in fs}
    for e in report["edges"]:
        ids |= set(e.get("supporting_findings", []))
    return ids


def names_in(texts: list[str], roster: dict[str, str]) -> list[str]:
    blob = "\n".join(texts)
    return [n for n in roster if n in blob]


# ---------------------------------------------------------------------------- pre-match

def offline_brief(report: dict) -> PreMatchBrief:
    fx = report["fixture"]
    edges = sorted(report["edges"], key=lambda e: -e["strength"])[:4]
    stories = team_news_storylines(report)[:1]
    for e in edges:
        text = tidy(e["explanation"])
        parts = [p for p in re.split(r"(?<=[.])\s+", text) if p]
        stories.append(Storyline(title=e["title"], text=" ".join(parts[:2]),
                                 evidence_ids=[e["edge_id"]] + [p["prediction_id"] for p in e["predictions"]],
                                 confidence="high" if e["strength"] >= 4 else "medium"))
    watch = []
    for club, ks in report["key_players"].items():
        for k in ks:
            if k["name"] not in watch:
                watch.append(k["name"])
                break
    for e in edges:
        for p in e["predictions"]:
            if p.get("subject_type") == "player" and p["subject"] not in watch:
                watch.append(p["subject"])
    ctx = report["context"]["stakes"]
    h, a = fx["home"], fx["away"]
    headline = f"{h} v {a}: the scouting file"
    battle = edges[0]["title"][:1].lower() + edges[0]["title"][1:] if edges else ""   # keep names capitalised
    preview = (f"{h} sit {ordinal(ctx[fx['home_id']]['position'])} in the table, {a} "
               f"{ordinal(ctx[fx['away_id']]['position'])}. The data points to {battle} as the key battle."
               if edges else "")
    return PreMatchBrief(headline=headline, storylines=stories, players_to_watch=watch[:4], tactical_preview=preview)


def check_brief(brief: PreMatchBrief, report: dict, evidence: list[str], verifier: Verifier,
                roster: dict[str, str]) -> tuple[PreMatchBrief, list[str]]:
    """Keep the storylines that pass; return the cleaned brief and feedback for a rewrite."""
    ids = known_ids(report)
    blob = "\n".join(evidence)
    allowed = names_in(evidence, roster) + [report["fixture"]["home"], report["fixture"]["away"]]
    feedback, kept = [], []
    for i, s in enumerate(brief.storylines, 1):
        valid_ids = [x for x in s.evidence_ids if x in ids or x in blob]
        probs = verifier.check("analyst", "en", s.title, s.text, evidence, "", allowed, [], check_length=False)
        if not valid_ids:
            probs.append("cite at least one edge_id, finding_id or prediction_id exactly as it appears in tool results")
        if probs:
            feedback.append(f"storyline {i} ({s.title}): " + "; ".join(probs))
        else:
            kept.append(s.model_copy(update={"evidence_ids": valid_ids}))
    for field_name in ("headline", "tactical_preview"):
        probs = verifier.check("analyst", "en", "x", getattr(brief, field_name), evidence, "", allowed, [], check_length=False)
        if probs:
            feedback.append(f"{field_name}: " + "; ".join(probs))
    names_only = [re.sub(r"\s*\(.*?\)\s*$", "", p).strip() for p in brief.players_to_watch]
    brief = brief.model_copy(update={"players_to_watch": names_only})
    watch = [p for p in brief.players_to_watch if p in roster and p in allowed]
    dropped = [p for p in brief.players_to_watch if p not in watch]
    if dropped:
        feedback.append("players_to_watch must be exact names from tool results: " + ", ".join(dropped))
    cleaned = brief.model_copy(update={"storylines": kept, "players_to_watch": watch})
    return cleaned, feedback


def merge_with_safe(brief: PreMatchBrief, safe: PreMatchBrief, header_ok: bool) -> PreMatchBrief:
    """Top up a brief with fewer than 3 good storylines from the safe version."""
    stories = list(brief.storylines)
    have = {x for s in stories for x in s.evidence_ids}
    for s in safe.storylines:
        if len(stories) >= 3:
            break
        if not have.intersection(s.evidence_ids):
            stories.append(s)
    return PreMatchBrief(headline=brief.headline if header_ok else safe.headline, storylines=stories,
                         players_to_watch=brief.players_to_watch or safe.players_to_watch,
                         tactical_preview=brief.tactical_preview if header_ok else safe.tactical_preview)


# ---------------------------------------------------------------------------- full-time

def recap_facts(analyst: Analyst, state: BroadcastState) -> tuple[list[str], list[dict]]:
    live = analyst.live
    end = live.end_clock
    st = analyst.live_state(end)
    h, a = st["home"], st["away"]
    venue = analyst.store.clubs.set_index("club_id").get("stadium", {}).get(analyst.live.home_id) \
        if "stadium" in analyst.store.clubs.columns else None
    facts = [f"Final score: {st['score']['display']}." + (f" Venue: {venue}." if venue else ""),
             f"xG {h['team']} {h['xg']:.2f} - {a['xg']:.2f} {a['team']}; shots {h['shots']}-{a['shots']}; "
             f"shots on target {h['shots_on_target']}-{a['shots_on_target']}; "
             f"possession {h['possession'] * 100:.0f}%-{a['possession'] * 100:.0f}%."]
    for m in analyst.live_key_moments(end, 0.0, 0.0):
        f = m["facts"]
        if m["type"] == "goal":
            line = (f"Minute {m['minute']}: {f['scorer']} scored for {m['team']} ({f['context']}, {f['score_after']}), "
                    f"{f['xg']:.2f} xG")
            facts.append(line + (f", assist {f['assist']}." if f.get("assist") else "."))
        elif m["type"] == "red_card":
            facts.append(f"Minute {m['minute']}: {f['player']} ({m['team']}) was sent off.")
        elif m["type"] == "injury" and f.get("replaced_by"):
            facts.append(f"Minute {m['minute']}: {f['player']} ({m['team']}) went off injured, replaced by "
                         f"{f['replaced_by']}.")
    for p in analyst.live_predictions(end):
        full = next((x for x in state.matchup["predictions_to_track"] if x["prediction_id"] == p["prediction_id"]), {})
        v = p["value"]
        shown = "n/a" if v is None else (f"{v * 100:.0f}%" if full.get("measure") == "aerial_win_rate"
                                         else (f"{v:.2f}" if "xg" in full.get("measure", "") else f"{int(v)}"))
        verdict = "CAME TRUE" if p["status"] == "confirmed" else "DID NOT HAPPEN"
        facts.append(f"Pre-match prediction {verdict}: {p['text']} Final value: {p['label']} = {shown}.")
    lu = analyst.store.showcase_lineups
    played = lu[lu.minutes.fillna(0) > 0]
    rows = []
    for r in played.itertuples():
        pl = live.player(r.player_id, end)
        score = (pl.get("match_rating") or {}).get("rating") or 0.0     # the published match rating (rating.py)
        rows.append({"name": pl["player"], "team": analyst.store.club_name(r.team_id), "score": score, **pl})
    rows.sort(key=lambda x: -x["score"])
    top = rows[:3]
    for t in top:
        pc = "n/a" if t["pass_completion"] is None else f"{t['pass_completion'] * 100:.0f}%"
        facts.append(f"{t['name']} ({t['team']}): match rating {t['score']:.1f}, {_n(t['goals'], 'goal')}, "
                     f"{_n(t['assists'], 'assist')}, {_n(t['shots'], 'shot')} "
                     f"({t['xg']:.2f} xG), {_n(t['key_passes'], 'key pass', 'key passes')}, "
                     f"{t['xt_added']:.2f} expected threat added, "
                     f"{pc} of passes completed.")
    return facts, top


def _n(count, one: str, many: str | None = None) -> str:
    """'1 goal', '2 goals'."""
    return f"{count} {one if count == 1 else (many or one + 's')}"


def check_recap(recap: Recap, facts: list[str], top: list[dict], verifier: Verifier, clubs: list[str]) -> list[str]:
    names = names_in(facts, verifier.roster) + clubs
    probs = []
    for field_name in ("headline", "summary", "plan_vs_reality", "player_reason"):
        p = verifier.check("analyst", "en", "x", getattr(recap, field_name), facts, "", names, [], check_length=False)
        if p:
            probs.append(f"{field_name}: " + "; ".join(p))
    if recap.player_of_the_match not in [t["name"] for t in top]:
        probs.append("player_of_the_match must be one of: " + ", ".join(t["name"] for t in top))
    if len(recap.headline) > 80:
        probs.append("headline over 80 characters")
    return probs


def offline_recap(facts: list[str], top: list[dict], analyst: Analyst) -> Recap:
    st = analyst.live_state(analyst.live.end_clock)
    came = [f.split(": ", 1)[1].split(" Final value")[0] for f in facts if "prediction CAME TRUE" in f]
    missed = [f.split(": ", 1)[1].split(" Final value")[0] for f in facts if "prediction DID NOT HAPPEN" in f]
    t = top[0]
    return Recap(
        headline=f"Full-time: {st['score']['display']}",
        summary=" ".join(facts[:2]) + " " + " ".join(f for f in facts if f.startswith("Minute")),
        plan_vs_reality=(f"{len(came)} of {len(came) + len(missed)} pre-match predictions came true. "
                         + (f"Came true: {came[0]}" if came else "")),
        player_of_the_match=t["name"],
        player_reason=next(f for f in facts if f.startswith(t["name"] + " (")),
    )


def brief_json(brief: PreMatchBrief, degraded: bool, source: str) -> dict:
    return json.loads(brief.model_dump_json()) | {"degraded": degraded, "source": source}
