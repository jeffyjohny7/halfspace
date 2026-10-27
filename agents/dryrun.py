"""A scripted stand-in for the model, for dry runs and tests (no Azure needed)."""

from __future__ import annotations

import json
import re

from .briefing import tidy
from .llm import scripted_client
from .schemas import AnalystReading, PreMatchBrief, Recap, Rendered

BAD = "4242"
NATIVE = {
    "ml": ("മത്സരത്തിലെ പ്രധാന നിമിഷം", "കണക്കുകൾ ഇങ്ങനെ"),
    "hi": ("मैच का अहम पल", "आंकड़े इस तरह हैं"),
    "ta": ("ஆட்டத்தின் முக்கிய தருணம்", "புள்ளிவிவரங்கள்"),
    "ar": ("لحظة مهمة في المباراة", "الأرقام"),
    "es": ("Momento clave del partido", "Los datos"),
    "fr": ("Moment clé du match", "Les chiffres"),
    "pt": ("Momento decisivo do jogo", "Os números"),
    "de": ("Schlüsselmoment des Spiels", "Die Zahlen"),
}
VARIANT_LINE = re.compile(r"^- profile=(\S+) language=([a-z]+)\.")
LENGTH_LINE = re.compile(r"\((\d+) characters\); body .*\((\d+) characters\)")
NUM = re.compile(r"\d+(?:\.\d+)?%?")


def _last_user(messages) -> str:
    for m in reversed(messages):
        if getattr(m, "role", None) == "user":
            return m.text or ""
    return ""


def _tool_results(messages) -> list[str]:
    out = []
    for m in messages:
        for c in getattr(m, "contents", []) or []:
            if getattr(c, "type", None) == "function_result":
                r = c.result
                out.append(" ".join(str(getattr(x, "text", x)) for x in r) if isinstance(r, list) else str(getattr(r, "text", r)))
    return out


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def _section(prompt: str, start: str, stop_prefixes: tuple[str, ...]) -> list[str]:
    lines, on = [], False
    for line in prompt.splitlines():
        if line.startswith(start):
            on = True
            continue
        if on:
            if line.startswith(stop_prefixes):
                break
            if line.startswith("- "):
                lines.append(line[2:])
    return lines


def _call(name: str, **args):
    from agent_framework import Content
    return [Content.from_function_call(f"call-{name}", name, arguments=args)]


def make_responder():
    state = {"analyst_calls": 0}

    def scout(prompt: str, messages) -> object:
        results = _tool_results(messages)
        if not results:
            m = re.search(r"Fixture: (.+?) \(home\) v (.+?) \(away\)", prompt)
            return _call("matchup_report", home=m.group(1), away=m.group(2))
        report = next(json.loads(r) for r in results if '"edges"' in r)
        stories = []
        for e in report["edges"][:4]:
            first = re.split(r"(?<=[.])\s+", tidy(e["explanation"]))[0]
            stories.append({"title": e["title"], "text": first, "evidence_ids": [e["edge_id"]],
                            "confidence": "high" if e["strength"] >= 4 else "medium"})
        fx0 = report["fixture"]
        for club, cid in ((fx0["home"], fx0["home_id"]), (fx0["away"], fx0["away_id"])):
            out = (report.get("team_news") or {}).get(club, {}).get("out") or []
            if out:
                stories.insert(0, {"title": f"{club} team news", "text": f"{club} are without {out[0]}.",
                                   "evidence_ids": [f"team_news:{cid}"], "confidence": "high"})
                break
        if "rejected" not in prompt:
            stories.insert(1, {"title": "Unbeaten run", "text": f"They have won {BAD} duels in a row.",
                               "evidence_ids": ["made-up-id"], "confidence": "high"})
        fx = report["fixture"]
        watch = [p.split(" (")[0] for ps in report["key_players"].values() for p in ps[:1]]
        return json.dumps({"headline": f"{fx['home']} v {fx['away']}: where the game is won",
                           "storylines": stories, "players_to_watch": watch,
                           "tactical_preview": f"{fx['home']} against {fx['away']}: the edges below decide it."})

    def analyst(prompt: str, messages) -> object:
        state["analyst_calls"] += 1
        cands = json.loads(prompt.split("Candidates:\n", 1)[1].split("\nReturn a pick", 1)[0])
        goal = next((c for c in cands if c["kind"] == "goal"), None)
        clock = int(re.search(r"clock_s (\d+)", prompt).group(1))
        if not _tool_results(messages):
            if goal:
                scorer = re.search(r": (.+?) scores", goal["facts"][0]).group(1).replace(" (own goal)", "")
                return _call("live_player", player=scorer, clock_s=clock)
            if state["analyst_calls"] == 1:
                return _call("live_state", clock_s=clock)
        picks = []
        for i, c in enumerate(cands):
            imp = {"goal": 1.0, "prediction_confirmed": 0.9, "red_card": 1.0}.get(c["kind"], 0.45)
            angle = c["facts"][-1] if len(c["facts"]) > 1 else ""
            if i == 0 and state["analyst_calls"] % 3 == 0:
                angle = f"That makes it {BAD} passes in this spell."
            picks.append({"candidate_id": c["candidate_id"], "importance": imp, "angle": angle})
        return json.dumps({"picks": picks, "game_read": "The game is still open."})

    def fan_lens(prompt: str, messages) -> object:
        facts = _section(prompt, "Facts:", ("Analyst angle", "Names you may use", "Write these"))
        kind = prompt.split(": ", 1)[1].split(",", 1)[0]
        retry = "rejected by the Verifier" in prompt
        out = []
        lm = LENGTH_LINE.search(prompt)
        hmax, bmax = (int(lm.group(1)), int(lm.group(2))) if lm else (60, 160)
        for line in prompt.splitlines():
            m = VARIANT_LINE.match(line)
            if not m:
                continue
            profile, lang = m.group(1), m.group(2)
            if lang == "hi" and kind == "half time" and not retry:
                continue                      # leave one variant out on the first try
            first = facts[0] if facts else ""
            if lang == "en":
                head = _clip(first.split(":")[0], hmax)
                body = _clip(" ".join(facts[:2]) if profile == "analyst" else first, bmax)
                if (kind in ("goal", "prediction confirmed") and not retry and profile == "casual") or \
                        (kind == "tempo" and profile == "analyst"):
                    body = _clip(f"Number {BAD}. " + body, bmax)
            else:
                a, b = NATIVE.get(lang, NATIVE["es"])
                nums = NUM.findall(first)[:3]
                head = _clip(a, hmax)
                body = _clip(f"{b}: {', '.join(nums)}." if nums else f"{b}.", bmax)
            out.append({"profile": profile, "language": lang, "headline": head, "body": body})
        return json.dumps({"variants": out})

    def recap(prompt: str, messages) -> object:
        facts = _section(prompt, "Full-time fact sheet:", ("The pre-match brief", "Player of the match"))
        potm = prompt.split("Player of the match must be one of: ", 1)[1].splitlines()[0].split(", ")[0]
        reason = next((f for f in facts if f.startswith(potm + " (")), facts[0])
        preds = [f for f in facts if "prediction" in f]
        return json.dumps({"headline": _clip(facts[0], 80), "summary": " ".join(facts[:3]),
                           "plan_vs_reality": " ".join(preds[:2]) or "No predictions were tracked.",
                           "player_of_the_match": potm, "player_reason": reason})

    def responder(fmt, messages):
        prompt = _last_user(messages)
        if fmt is PreMatchBrief:
            return scout(prompt, messages)
        if fmt is AnalystReading:
            return analyst(prompt, messages)
        if fmt is Rendered:
            return fan_lens(prompt, messages)
        if fmt is Recap:
            return recap(prompt, messages)
        return "{}"

    return responder


def dry_run_client():
    return scripted_client(make_responder())
