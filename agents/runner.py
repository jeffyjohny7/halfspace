"""Run a whole broadcast: pre-match brief, the live match tick by tick, the recap.

The runner plays the showcase feed forward. Before every tick it writes the live
clock file, so the MCP server cannot show any agent an event that has not happened
yet. Output goes to data/runtime/broadcast/:

    brief.json     the verified pre-match brief
    cues.jsonl     every on-screen cue, with its variants, facts and verification record
    recap.json     the verified post-match recap
    run_log.json   every decision by every agent, model-call timings, counters
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path

from analytics.api import Analyst

from . import workflows
from .config import BroadcastConfig, Viewer
from .executors import PostmatchRequest, PrematchRequest, Tick
from .llm import make_client
from .state import BroadcastState
from .team import Sink, Team, build_agents
from .verifier import Verifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCOUT_TOOLS = ["overview", "matchup_report", "team_news", "match_lineup", "injuries", "scout_findings",
               "goals_breakdown", "player_profile", "club_profile", "head_to_head", "squad_report", "glossary"]
LIVE_TOOLS = ["live_player", "live_ratings", "live_state", "scout_findings"]


def write_clock(path: Path, clock_s: float) -> bool:
    """Atomic write with retries (Windows can briefly lock the file while the server reads it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    for i in range(6):
        try:
            tmp.write_text(json.dumps({"clock_s": round(float(clock_s), 1)}), encoding="utf-8")
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.05 * (i + 1))
    return False


def schedule(analyst: Analyst, every_s: float, until_clock: float | None = None) -> list[float]:
    """Regular check-ins plus an immediate tick a few seconds after goals, red cards and whistles."""
    ev = analyst.live.ev
    end = analyst.live.end_clock
    trig = ev[((ev.t == "shot") & (ev.o == "goal")) | (ev.t == "own_goal") | (ev.t == "period_end")
              | ((ev.t == "card") & ev.card.astype(str).isin(["red", "second_yellow"]))]
    urgent = {min(end, float(t) + 5.0) for t in trig.clock_s} | {end}
    regular = {float(t) for t in range(int(every_s), int(end), int(every_s))}
    out: list[float] = []
    for t in sorted(regular | urgent):
        if until_clock is not None and t > until_clock:
            break
        if out and t - out[-1] < 20 and t not in urgent:
            continue          # a regular check-in right after an urgent one adds nothing
        out.append(t)
    return out


class Broadcast:
    def __init__(self, cfg: BroadcastConfig, client=None):
        """client: optional chat client override (tests use a scripted one)."""
        self.cfg = cfg
        self.client = client
        self.team: Team | None = None

    def _mcp(self, name: str, allowed: list[str]):
        from agent_framework import MCPStdioTool
        env = {**os.environ, "MATCH_DATA_DIR": str(Path(self.cfg.data_dir).resolve()),
               "PYTHONPATH": str(PROJECT_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}
        return MCPStdioTool(name=name, command=sys.executable, args=["-m", "mcp_server.server"], env=env,
                            allowed_tools=allowed, load_prompts=False, request_timeout=180)

    async def run(self, until_minute: float | None = None, speed: float = 0.0, prematch: bool = True,
                  postmatch: bool = True) -> dict:
        cfg = self.cfg
        t0 = time.time()
        analyst = Analyst(cfg.data_dir)
        store = analyst.store
        meta = store.showcase_meta
        report = analyst.showcase_report()
        fav = analyst.club_id(cfg.favourite_club) if cfg.favourite_club else None
        focus = analyst.player_id(cfg.focus_player) if cfg.focus_player else None
        viewers = [Viewer(f"club:{fav}", v.language, v.audience) if v.profile.startswith("club:") else v
                   for v in cfg.viewers()]
        roster = {name: "" for name in store.player_names.values()}
        clubs = list(store.club_names.values())
        state = BroadcastState(meta["match_id"], meta["home_id"], meta["away_id"], store.club_name(meta["home_id"]),
                               store.club_name(meta["away_id"]), viewers, matchup=report)
        out_dir = Path(cfg.out_dir or Path(cfg.data_dir) / "runtime" / "broadcast")
        sink = Sink(out_dir)
        clock_file = Path(cfg.data_dir).resolve() / "runtime" / "live_clock.json"   # the file the MCP server reads
        client = self.client if self.client is not None else make_client(cfg.mode, cfg.max_tool_calls)
        traced = False
        if client is not None and self.client is None and cfg.trace:
            from .telemetry import enable_foundry_tracing
            traced = await enable_foundry_tracing(client, sensitive=cfg.trace_content)

        until_clock = None
        if until_minute is not None:
            later = analyst.live.ev[analyst.live.ev.minute >= until_minute]
            until_clock = float(later.clock_s.min()) if len(later) else None

        timings: dict[str, float] = {}
        published_before = 0
        write_clock(clock_file, 0.0)
        try:
            async with AsyncExitStack() as stack:
                scout_tools, live_tools = [], []
                if client is not None:
                    scout_tools = [await stack.enter_async_context(self._mcp("match_intel", SCOUT_TOOLS))]
                    live_tools = [await stack.enter_async_context(self._mcp("live_intel", LIVE_TOOLS))]
                writer_client = None
                if client is not None and self.client is None and cfg.writer_model:
                    writer_client = make_client(cfg.mode, cfg.max_tool_calls, model=cfg.writer_model)
                agents = build_agents(client, scout_tools, live_tools, cfg.reasoning_effort,
                                      writer_client=writer_client, translation_effort=cfg.translation_effort)
                cl = analyst.store.clubs
                places = [str(x) for x in list(cl.get("stadium", [])) + list(cl.get("town", [])) if isinstance(x, str)]
                team = Team(cfg, analyst, state, agents, Verifier(roster, clubs, places), sink, focus, fav)
                self.team = team
                team.log_line(f"Broadcast: {state.home} v {state.away}  |  mode={cfg.mode if client else 'offline'}  |  "
                              f"viewers: {', '.join(v.key for v in viewers)}"
                              + (f"  |  traces -> Foundry{' (with content)' if cfg.trace_content else ''}"
                                 if traced else ""))

                if prematch:
                    team.log_line("Pre-match: Scout investigating the fixture...")
                    ts = time.time()
                    await workflows.prematch(team).run(PrematchRequest())
                    timings["prematch_s"] = round(time.time() - ts, 1)
                    b = state.brief or {}
                    team.log_line(f"  Brief: {b.get('headline')}  ({len(b.get('storylines', []))} storylines"
                                  f"{', safe version' if b.get('degraded') else ''})")
                    published_before = len(state.cues)

                ticks = schedule(analyst, cfg.tick_every_s, until_clock)
                team.log_line(f"Live: {len(ticks)} check-ins" + (f" (paced at {speed:g}x)" if speed else ""))
                live_wf = workflows.live_tick(team)
                ts = time.time()
                wall0 = time.time()
                for clock in ticks:
                    if speed:
                        wait = wall0 + clock / speed - time.time()
                        if wait > 0:
                            await asyncio.sleep(wait)
                    write_clock(clock_file, clock)
                    await live_wf.run(Tick(clock))
                timings["live_s"] = round(time.time() - ts, 1)
                reached_end = bool(ticks) and ticks[-1] >= analyst.live.end_clock

                if postmatch and reached_end:
                    team.log_line("Full-time: Recap writing...")
                    ts = time.time()
                    await workflows.postmatch(team).run(PostmatchRequest())
                    timings["postmatch_s"] = round(time.time() - ts, 1)
        finally:
            try:
                clock_file.unlink()
            except OSError:
                pass

        timings["total_s"] = round(time.time() - t0, 1)
        summary = {
            "match": {"match_id": state.match_id, "home": state.home, "away": state.away},
            "mode": cfg.mode if client is not None else "offline",
            "viewers": [v.key for v in viewers],
            "cues": len(state.cues), "prematch_cues": published_before,
            "degraded_cues": sum(c["verification"]["degraded"] for c in state.cues),
            "counters": state.counters, "timings": timings,
            "game_reads": state.game_reads,
            "log": state.log,
        }
        sink.json("run_log.json", summary)
        team.log_line(f"Done in {timings['total_s']} s: {len(state.cues)} cues, "
                      f"{state.counters['llm_calls']} model calls, {state.counters['verifier_rejections']} rejected texts, "
                      f"{state.counters['template_fallbacks']} safe-template fallbacks. Output: {out_dir}")
        return summary
