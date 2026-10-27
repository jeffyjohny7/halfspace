"""The Fan Desk: answers fans' questions in the app, checked before they are shown.

One agent with the match-intelligence MCP tools, minus the broadcast's live tools. For today's match it has
two tools of its own that stop at the moment the fan has reached in the replay (FAN_CLOCK): a fan at 30'
can ask who scored and never learn what happens later; a fan who hasn't pressed play learns nothing.
Every answer goes through the same Verifier as the broadcast graphics: each number must
appear in a tool result the agent saw (or in the question / earlier verified answers),
no betting language, and the right script for Malayalam or Hindi. A rejected answer is
rewritten once with the problems listed; if it still fails, the fan gets a plain
"couldn't check that" message, never an unchecked answer.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .config import LANGUAGE_NOTES, LANGUAGES
from .llm import ask, model_options, prompt_json
from .schemas import Answer
from .telemetry import annotate, span
from .verifier import Verifier, tidy_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DESK_TOOLS = ["overview", "league_table", "search", "upcoming_fixtures", "club_profile", "goals_breakdown",
              "player_profile", "squad_report", "scout_findings", "team_news", "injuries", "match_lineup",
              "head_to_head", "matchup_report", "glossary"]
SOURCE_LABELS = {
    "overview": "league overview", "league_table": "league table", "upcoming_fixtures": "fixtures",
    "club_profile": "club stats", "goals_breakdown": "goal records", "player_profile": "player stats",
    "squad_report": "squad stats", "scout_findings": "scouting findings", "team_news": "team news",
    "injuries": "injury records", "match_lineup": "line-ups", "head_to_head": "head-to-head record",
    "matchup_report": "match preview", "glossary": "glossary",
    "match_so_far": "today's match", "player_in_match": "today's match",
}
MAX_QUESTION = 400
# Tool field names (rounds_played, pressures_p90) and ids (match, player, club) that must not reach a fan.
INTERNAL = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b|\b\d{6}-D\d-R\d{2}-\d{2}\b|\bP\d{5}\b|\bC\d{2}\b")
# How far the fan has watched today's match (seconds of play), set per question. None or 0: not started.
FAN_CLOCK: contextvars.ContextVar[float | None] = contextvars.ContextVar("fan_clock", default=None)
NOT_STARTED = ("The fan hasn't started today's match in the app yet, so nothing about it can be shared. "
               "Pre-match news (team news, line-ups, form) is fine.")


def minute_label(clock: dict) -> str:
    """Football time: 45+2', 90+4', or "full time"."""
    if clock.get("finished"):
        return "full time"
    m, period = int(clock.get("minute", 0)), int(clock.get("period", 1))
    if period == 1 and m > 45:
        return f"45+{m - 45}'"
    if period == 2 and m > 90:
        return f"90+{m - 90}'"
    return f"{m}'"


def match_tools(analyst) -> list:
    """Today's match, as far as the fan has watched it. The clamp is in code, not in the prompt."""
    from agent_framework import tool

    def watched() -> float | None:
        c = FAN_CLOCK.get()
        return min(float(c), analyst.live.end_clock) if c and c > 0 else None

    @tool(name="match_so_far", description="Today's match up to the moment the fan has reached in the replay: "
          "score, goals (scorer, minute, assist), red cards, injuries, team stats and the best-rated players. "
          "Shows nothing after that moment.")
    def match_so_far() -> str:
        c = watched()
        if c is None:
            return json.dumps({"watched": False, "note": NOT_STARTED})
        st = analyst.live_state(c)
        events = []
        for m in analyst.live_key_moments(c, 0.0, 0.0):
            f = m["facts"]
            if m["type"] == "goal":
                events.append({"minute": m["minute"], "goal": f.get("scorer"), "team": m["team"],
                               "assist": f.get("assist"), "score_after": f.get("score_after"),
                               "chance_quality_xg": round(f.get("xg") or 0, 2)})
            elif m["type"] == "red_card":
                events.append({"minute": m["minute"], "red_card": f.get("player"), "team": m["team"]})
            elif m["type"] == "injury":
                events.append({"minute": m["minute"], "injured": f.get("player"), "team": m["team"],
                               "replaced_by": f.get("replaced_by")})
        keys = ("goals", "xg", "shots", "shots_on_target", "possession", "corners", "fouls", "yellow_cards",
                "red_cards")
        stats = {st[s]["team"]: {k: (round(st[s][k] * 100) if k == "possession" else st[s][k]) for k in keys}
                 for s in ("home", "away")}
        best = {team: [{"player": p["player"], "rating": p["rating"]} for p in rows[:3]]
                for team, rows in analyst.live_ratings(c)["by_team"].items()}
        return json.dumps({"watched_up_to": minute_label(st["clock"]), "full_time": bool(st["clock"].get("finished")),
                           "score": st["score"]["display"],
                           "events": events, "team_stats (possession in %)": stats,
                           "best_rated_so_far": best}, ensure_ascii=False)

    @tool(name="player_in_match", description="How one player has done in today's match up to the fan's moment: "
          "goals, assists, shots, passes, duels, his match rating and why.")
    def player_in_match(player: str) -> str:
        c = watched()
        if c is None:
            return json.dumps({"watched": False, "note": NOT_STARTED})
        try:
            p = analyst.live_player(player, c)
            r = analyst.live.rating(p["player_id"], c)
        except Exception as e:             # unknown player or not in today's squads
            return json.dumps({"error": f"{player}: {str(e)[:120]}"})
        keep = ("player", "on_pitch", "goals", "assists", "shots", "xg", "key_passes", "passes", "pass_completion",
                "tackles", "interceptions", "aerials_won", "aerials_lost", "dispossessed", "touches")
        out = {k: p.get(k) for k in keep if k in p}
        if isinstance(out.get("pass_completion"), float):
            out["pass_completion"] = f"{out['pass_completion']:.0%}"
        if r.get("rating") is not None:
            out["match_rating"] = r["rating"]
            out["rating_reasons"] = r.get("why", [])[:4]
        return json.dumps(out, ensure_ascii=False, default=str)

    return [match_so_far, player_in_match]
NOT_CHECKED = {
    "en": "I couldn't check every number in that answer against the league data, so I won't show it. "
          "Try asking a narrower question, about one player or one club.",
    "ml": "ആ ഉത്തരത്തിലെ എല്ലാ കണക്കുകളും ലീഗ് ഡാറ്റയുമായി ഒത്തുനോക്കാൻ കഴിഞ്ഞില്ല, അതുകൊണ്ട് അത് കാണിക്കുന്നില്ല. "
          "ഒരു കളിക്കാരനെക്കുറിച്ചോ ഒരു ക്ലബ്ബിനെക്കുറിച്ചോ ചോദിച്ചുനോക്കൂ.",
    "hi": "उस जवाब के हर आंकड़े को लीग डेटा से जांचा नहीं जा सका, इसलिए उसे नहीं दिखाया जा रहा। "
          "किसी एक खिलाड़ी या एक क्लब के बारे में पूछकर देखें।",
    "es": "No pude comprobar todas las cifras de esa respuesta con los datos de la liga, así que no la muestro. "
          "Prueba con una pregunta más concreta, sobre un jugador o un club.",
    "ar": "لم أتمكن من التحقق من كل الأرقام في هذه الإجابة مقابل بيانات الدوري، لذلك لن أعرضها. "
          "جرّب سؤالًا أدق عن لاعب واحد أو نادٍ واحد.",
}
# Shown when the Foundry guardrail (content filter or Prompt Shields) stops a question or an answer.
BLOCKED = {
    "en": "This question was stopped by the safety checks, so it won't be answered. "
          "Ask about players, clubs, line-ups, injuries, fixtures or form.",
    "es": "Los controles de seguridad detuvieron esta pregunta, así que no se responderá. "
          "Pregunta por jugadores, clubes, alineaciones, lesiones, partidos o forma.",
    "ar": "أوقفت فحوص الأمان هذا السؤال، لذلك لن تتم الإجابة عنه. "
          "اسأل عن اللاعبين أو الأندية أو التشكيلات أو الإصابات أو المباريات أو المستوى.",
    "hi": "सुरक्षा जांच ने इस सवाल को रोक दिया, इसलिए इसका जवाब नहीं दिया जाएगा। "
          "खिलाड़ियों, क्लबों, लाइन-अप, चोटों, मैचों या फ़ॉर्म के बारे में पूछें।",
    "ml": "സുരക്ഷാ പരിശോധന ഈ ചോദ്യം തടഞ്ഞു, അതിനാൽ ഇതിന് ഉത്തരം നൽകില്ല. "
          "കളിക്കാർ, ക്ലബ്ബുകൾ, ലൈനപ്പുകൾ, പരിക്കുകൾ, മത്സരങ്ങൾ, ഫോം എന്നിവയെക്കുറിച്ച് ചോദിക്കൂ.",
}


def desk_tool(data_dir: str):
    """The MCP server over stdio, limited to the pre-match tools."""
    from agent_framework import MCPStdioTool
    env = {**os.environ, "MATCH_DATA_DIR": str(Path(data_dir).resolve()),
           "PYTHONPATH": str(PROJECT_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return MCPStdioTool(name="league_desk", command=sys.executable, args=["-m", "mcp_server.server"], env=env,
                        allowed_tools=DESK_TOOLS, load_prompts=False, request_timeout=120)


class FanDesk:
    def __init__(self, client, tools: list, verifier: Verifier, reasoning_effort: str | None = None,
                 timeout_s: float = 150.0, analyst=None, fans=None, memory=None):
        """analyst: give it to enable the today's-match tools (clamped to the fan's replay clock).
        fans: a FanStore, for answers made personal (FanContext provider); memory: a MemoryKeeper, to learn
        football preferences from what fans who switched memory on say."""
        from agent_framework import Agent

        from . import prompts
        from .fans import fan_context_provider
        self.analyst = analyst
        self.fans = fans
        self.memory = memory
        tools = list(tools or []) + (match_tools(analyst) if analyst is not None else [])
        self.agent = Agent(client, prompts.FAN_DESK, name="FanDesk", tools=tools or None,
                           default_options=model_options(reasoning_effort),
                           context_providers=[fan_context_provider()])
        self.verifier = verifier
        self.timeout_s = timeout_s
        self.names = list(verifier.roster) + list(verifier.clubs)

    def _prompt(self, question: str, language: str, history: list[dict]) -> str:
        lines = []
        if history:
            lines.append("Earlier in this conversation (for follow-up questions):")
            lines += [f"Fan: {h['q']}\nYou: {h['a']}" for h in history]
            lines.append("")
        c = FAN_CLOCK.get()
        if self.analyst is not None:
            if c and c > 0:
                st = self.analyst.live_state(min(float(c), self.analyst.live.end_clock))
                lines.append(f"The fan has watched today's match up to {minute_label(st['clock'])} "
                             f"(score {st['score']['display']}). "
                             "For anything about it use match_so_far or player_in_match.")
            else:
                lines.append("The fan hasn't started today's match yet: nothing about it beyond pre-match news.")
        lines.append(f"Fan's question: {question}")
        lines.append(f"Answer in {LANGUAGES.get(language, 'English')}. {LANGUAGE_NOTES.get(language, '')}".strip())
        return "\n".join(lines)

    def check(self, text: str, language: str, evidence: list[str], context: list[str]) -> list[str]:
        problems = self.verifier.check("casual", language, "", text, context, "", self.names, evidence,
                                       check_length=False)
        # Fans may ask what a metric means, so explaining one is fine here.
        problems = [p for p in problems if not p.startswith("do not define")]
        if "showcase" in text.lower():          # internal word from the tools; fans know it as today's match
            problems.append('call it "today\'s match", never "the showcase"')
        leaks = sorted(set(INTERNAL.findall(text)))
        if leaks:                               # tool field names and ids mean nothing to a fan
            problems.append("say these in words, not as field names or ids: " + ", ".join(leaks))
        return problems

    async def answer(self, question: str, language: str = "en", history: list[dict] | None = None,
                     clock_s: float | None = None, fan_id: str | None = None) -> dict[str, Any]:
        """clock_s: how far the fan has watched today's match (None or 0: not started).
        fan_id: the fan's profile id; their brief shapes the answer and, with memory on, the Memory Keeper
        reads the question for preferences at the same time."""
        from .fans import FAN_BRIEF, fan_brief
        language = language if language in LANGUAGES else "en"
        prof = self.fans.load(fan_id) if (self.fans is not None and fan_id) else None
        brief = fan_brief(prof, self.analyst, clock_s) if (prof and self.analyst is not None) else []
        token = FAN_CLOCK.set(clock_s)
        btoken = FAN_BRIEF.set(brief)
        try:
            with span("halfspace.ask", language=language, fan_clock_s=clock_s, personal=bool(brief)):
                learn = (asyncio.ensure_future(self._learn(fan_id, question))
                         if (prof and prof.get("memory") and self.memory is not None) else None)
                reply = await self._answer(question, language, history, brief)
                reply["remembered"] = (await learn) if learn is not None else []
                annotate(checked=bool(reply.get("checked")), attempts=len(reply.get("log", [])),
                         sources=reply.get("sources", []), blocked=reply.get("blocked"),
                         remembered=len(reply["remembered"]))
                return reply
        finally:
            FAN_BRIEF.reset(btoken)
            FAN_CLOCK.reset(token)

    async def _learn(self, fan_id: str, question: str) -> list[str]:
        """The Memory Keeper reads the fan's own words; the FanStore keeps only checked football preferences."""
        try:
            with span("halfspace.memory"):
                upd = await self.memory.read(" ".join(str(question).split())[:MAX_QUESTION])
                added = self.fans.learn(fan_id, upd, question) if upd is not None else []
                annotate(added=len(added))
                return added
        except Exception:           # memory is best-effort: the answer never waits on it failing
            return []

    async def _answer(self, question: str, language: str, history: list[dict] | None,
                      brief: list[str] | None = None) -> dict[str, Any]:
        question = " ".join(str(question or "").split())[:MAX_QUESTION]
        history = [h for h in (history or []) if h.get("q") and h.get("a")][-3:]
        if not question:
            return {"error": True, "answer": "Type a question first."}
        # The fan's brief is computed in code (their club's score, last result), so its numbers count as facts.
        context = [question] + [f"{h['q']} {h['a']}" for h in history] + list(brief or [])
        prompt = self._prompt(question, language, history)
        evidence: list[str] = []
        tools: list[str] = []
        log: list[dict] = []
        for attempt in range(2):
            res = await ask(self.agent, prompt, Answer, timeout_s=self.timeout_s, retries=1)
            if res.value is None:
                log.append({"attempt": attempt + 1, "error": res.error, "blocked": res.blocked,
                            "raw": (res.errors[-1] if res.errors else "")[:800]})
                if res.blocked:
                    return {"error": True, "blocked": res.blocked, "lang": language,
                            "answer": BLOCKED.get(language, BLOCKED["en"]), "log": log}
                return {"error": True, "answer": _failure_text(res.error), "log": log}
            evidence += res.tool_texts
            tools += res.tool_names
            text = tidy_text(res.value.answer)
            problems = self.check(text, language, evidence, context)
            log.append({"attempt": attempt + 1, "seconds": round(res.seconds, 1), "tools": res.tool_names,
                        "problems": problems})
            if not problems:
                # The tool results go in the log too, so scripts/eval_agents.py can judge the answer against them.
                log[-1]["evidence"] = [e[:4000] for e in evidence][:8]
                return {"answer": text, "answered": res.value.answered, "checked": True,
                        "sources": _sources(tools), "log": log}
            prompt = (self._prompt(question, language, history)
                      + "\n\nYour previous answer was rejected by the fact checker:\n"
                      + prompt_json({"answer": text, "problems": problems})
                      + "\nLook things up again if you need to, then rewrite it. Use only numbers from tool results.")
        return {"error": True, "held_back": True, "lang": language,
                "answer": NOT_CHECKED.get(language, NOT_CHECKED["en"]), "log": log}


def _sources(tools: list[str]) -> list[str]:
    out: list[str] = []
    for t in tools:
        label = SOURCE_LABELS.get(t)
        if label and label not in out:
            out.append(label)
    return out


def _failure_text(error: str | None) -> str:
    e = (error or "").lower()
    if "credential" in e or "auth" in e or "401" in e or "403" in e:
        return ("The Fan Desk couldn't sign in to Azure AI Foundry. Run az login, check FOUNDRY_PROJECT_ENDPOINT "
                "in .env, then restart scripts/serve_web.py.")
    if "timeout" in e:
        return "That took too long to look up. Try again, or ask about one player or one club."
    return "The question couldn't be answered just now. Try again in a moment."
