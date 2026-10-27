"""The team's shared context: config, data, agents, the verifier and the output sink."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analytics.api import Analyst

from . import prompts
from .config import LANGUAGES, PROFILE_STYLES, BroadcastConfig, Viewer
from .llm import CallResult, ask, model_options
from .state import BroadcastState
from .verifier import Verifier

BREAKER_AFTER = 4
BREAKER_PAUSE_S = 60.0


@dataclass
class Agents:
    scout: Any = None
    analyst: Any = None
    fan_lens: Any = None
    recap: Any = None
    translator: Any = None      # Fan Lens for other languages (more reasoning, optionally a bigger model)

    def writer_for(self, language: str):
        return self.fan_lens if language == "en" or self.translator is None else self.translator


def build_agents(client, scout_tools: list | None = None, live_tools: list | None = None,
                 reasoning_effort: str | None = None, writer_client=None,
                 translation_effort: str | None = None) -> Agents:
    """The LLM agents. Data only reaches them through the MCP tools or the given facts."""
    if client is None:
        return Agents()
    from agent_framework import Agent

    opts = model_options(reasoning_effort)
    return Agents(
        translator=Agent(writer_client or client, prompts.FAN_LENS, name="FanLensTranslator",
                         default_options=model_options(translation_effort or reasoning_effort)),
        scout=Agent(client, prompts.SCOUT, name="Scout", tools=scout_tools or None, default_options=opts),
        analyst=Agent(client, prompts.ANALYST, name="TacticalAnalyst", tools=live_tools or None,
                      default_options=opts),
        fan_lens=Agent(client, prompts.FAN_LENS, name="FanLens", default_options=opts),
        recap=Agent(client, prompts.RECAP, name="Recap", default_options=opts),
    )


class Sink:
    """Writes the broadcast package: brief.json, cues.jsonl, recap.json, run_log.json."""

    def __init__(self, out_dir: Path):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cues_path = self.dir / "cues.jsonl"
        self.cues_path.write_text("", encoding="utf-8")

    def cue(self, cue: dict) -> None:
        with self.cues_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(cue, ensure_ascii=False, default=str) + "\n")

    def json(self, name: str, obj: Any) -> None:
        tmp = self.dir / f".{name}.tmp"
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        tmp.replace(self.dir / name)


class Team:
    def __init__(self, cfg: BroadcastConfig, analyst: Analyst, state: BroadcastState, agents: Agents,
                 verifier: Verifier, sink: Sink, focus_player_id: str | None = None, favourite_club_id: str | None = None):
        self.cfg = cfg
        self.data = analyst
        self.state = state
        self.agents = agents
        self.verifier = verifier
        self.sink = sink
        self.focus_player_id = focus_player_id
        self.favourite_club_id = favourite_club_id
        self.scout_evidence: list[str] = []
        self.on_publish = None          # optional callback(cue)
        self._failures = 0
        self._breaker_until = 0.0

    # ------------------------------------------------------------------ viewers
    def viewers_for(self, audience: str) -> list[Viewer]:
        return [v for v in self.state.viewers if v.audience == audience]

    def style(self, v: Viewer) -> str:
        if v.profile.startswith("club:"):
            return PROFILE_STYLES["club"].format(club=self.data.store.club_name(self.favourite_club_id or v.profile[5:]))
        if v.profile == "player_focus":
            name = self.data.store.player_name(self.focus_player_id) if self.focus_player_id else "the focus player"
            return PROFILE_STYLES["player_focus"].format(player=name)
        return PROFILE_STYLES[v.profile]

    def language_name(self, code: str) -> str:
        return LANGUAGES.get(code, code)

    # ------------------------------------------------------------------ LLM calls
    async def llm(self, agent_name: str, agent: Any, prompt: str, schema, session: Any = None) -> CallResult:
        # Circuit breaker: after several failures in a row, stop calling the model for a minute
        # (the broadcast carries on with safe templates) and then try again.
        if self._failures >= BREAKER_AFTER and time.time() < self._breaker_until:
            self.state.note(agent_name, "llm_skipped", reason="circuit breaker open")
            return CallResult(None, [], "circuit breaker open", 0.0, 0)
        self.state.counters["llm_calls"] += 1
        res = await ask(agent, prompt, schema, timeout_s=self.cfg.llm_timeout_s, retries=self.cfg.llm_retries,
                        session=session)
        if res.blocked:                       # the guardrail did its job; the service is fine
            self.state.counters["guardrail_blocks"] += 1
        elif res.value is None:
            self.state.counters["llm_failures"] += 1
            self._failures += 1
            if self._failures >= BREAKER_AFTER:
                self._breaker_until = time.time() + BREAKER_PAUSE_S
        else:
            self._failures = 0
        self.state.note(agent_name, "llm_call", ok=res.value is not None, seconds=round(res.seconds, 1),
                        attempts=res.attempts, tool_results=len(res.tool_texts), error=res.error,
                        tool_errors=res.tool_errors or None, blocked=res.blocked,
                        errors=res.errors if len(res.errors) > 1 or (res.errors and res.value is not None) else None)
        if self.cfg.verbose and res.value is None:
            print(f"  ! {agent_name} call failed: " + (" ; ".join(e[:240] for e in res.errors) or str(res.error)))
        elif res.errors:
            self.log_line(f"  ~ {agent_name}: worked on attempt {res.attempts} after: {res.errors[0][:200]}")
        for err in res.tool_errors:
            self.log_line(f"  ! {agent_name} tool error: {err[:300]}")
        return res

    def log_line(self, text: str) -> None:
        if self.cfg.verbose:
            print(text, flush=True)


def now() -> float:
    return time.time()
