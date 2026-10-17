"""Score the stats-only Scout against the hidden answer key (baseline).

Usage:
    uv run scripts/eval_scout.py                     # medium+ confidence
    uv run scripts/eval_scout.py --min-confidence low
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.scout import Scout  # noqa: E402
from analytics.store import Store  # noqa: E402
from evaluation.answer_key import hidden_support, load_truths, score  # noqa: E402


def run(data: str, min_conf: str) -> dict:
    store = Store(data)
    scout = Scout(store)
    report = {}
    for season, blend in ((store.previous_season, False), (store.current_season, True)):
        clubs = store.club_seasons
        top = sorted(clubs[(clubs.season == season) & (clubs.division == 1)].club_id)
        findings = [f for c in top for f in scout.findings(c, season, min_confidence=min_conf, blend=blend)]
        res = score(findings, load_truths(data, season), clubs=set(top),
                    support=hidden_support(findings, data, season))
        res["clubs"] = len(top)
        res["findings_total"] = len(findings)
        res["blend_previous_season"] = blend
        report[season] = res
    return report


def to_markdown(report: dict, min_conf: str) -> str:
    lines = ["# Scout baseline vs the hidden answer key", "",
             f"Stats engine only, no LLM. Findings at **{min_conf}** confidence or above, top division.", ""]
    for season, r in report.items():
        lines += [f"## {season}" + (" (blending last season)" if r["blend_previous_season"] else " (full season)"), "",
                  f"- Planted traits recovered: **{r['planted_found']}/{r['planted_truths']}** (recall {r['recall']:.0%})",
                  f"- Precision vs answer key (lower bound): **{r['precision_lower_bound']:.0%}** "
                  f"({r['findings_matched']}/{r['findings_scored']} catalogue findings)",
                  f"- Precision vs hidden ratings: **{r['precision_hidden_ratings']:.0%}** of {r['findings_checkable']} "
                  "checkable findings point at a rating in the worst/best 20% of peers (planted or natural)",
                  f"- Natural (unplanted) extremes also found: {r['natural_found']}/{r['natural_truths']}", "",
                  "| Confidence | Findings | Planted match | Backed by hidden ratings |", "|---|---|---|---|"]
        for c in ("high", "medium", "low"):
            d = r["precision_by_confidence"].get(c)
            h = r["precision_hidden_by_confidence"].get(c)
            if d or h:
                lines.append(f"| {c} | {h['findings'] if h else d['findings']} | "
                             f"{d['precision']:.0%} | {h['precision']:.0%} |" if d and h else f"| {c} | - | - | - |")
        lines += ["", "| Trait | Recovered |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in r["recall_by_trait"].items()]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--min-confidence", default="medium", choices=["low", "medium", "high"])
    args = ap.parse_args()
    report = run(args.data, args.min_confidence)
    os.makedirs(os.path.join(args.data, "reports"), exist_ok=True)
    with open(os.path.join(args.data, "reports", "scout_eval.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    md = to_markdown(report, args.min_confidence)
    with open(os.path.join(args.data, "reports", "scout_eval.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
