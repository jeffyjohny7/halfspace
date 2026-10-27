"""Workflow executors: one per member of the broadcast team.

LLM agents:   Scout, Tactical Analyst, Fan Lens, Recap   (Microsoft Agent Framework agents
              on Foundry, reaching data only through the MCP server or given facts)
Code agents:  Gather (stats engine), Director, Verifier, Brief/Recap checks, Publisher

Messages are plain dataclasses; the shared BroadcastState lives on the Team object.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from typing_extensions import Never

from agent_framework import Executor, WorkflowContext, handler

from . import briefing, candidates, director, templates
from .config import LANGUAGE_NOTES, LANGUAGES, LENGTH_WORDS
from .llm import prompt_json
from .schemas import AnalystReading, PreMatchBrief, Recap, Rendered
from .state import Candidate, CueDraft, RenderJob, Variant
from .team import Team
from .telemetry import annotate
from .verifier import DEFAULT_LIMITS, LIMITS, tidy_text, trim_to_fit


# ---------------------------------------------------------------------------- messages

@dataclass
class Tick:
    clock_s: float


@dataclass
class TickDone:
    clock_s: float
    published: int = 0


@dataclass
class Gathered:
    clock_s: float
    candidates: list


@dataclass
class Reading:
    clock_s: float
    candidates: list
    evidence: list


@dataclass
class PrematchRequest:
    note: str = ""


@dataclass
class BriefDraft:
    brief: Any = None
    evidence: list = field(default_factory=list)
    attempt: int = 1
    feedback: list = field(default_factory=list)
    accepted: bool = False
    degraded: bool = False
    source: str = "llm"


@dataclass
class PostmatchRequest:
    note: str = ""


@dataclass
class RecapDraft:
    recap: Any = None
    facts: list = field(default_factory=list)
    top: list = field(default_factory=list)
    attempt: int = 1
    feedback: list = field(default_factory=list)
    accepted: bool = False
    degraded: bool = False
    source: str = "llm"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------- live: gather

class Gather(Executor):
    """Stats engine: turns the feed into candidate items with checkable facts."""

    def __init__(self, team: Team, id: str = "gather"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_tick(self, tick: Tick, ctx: WorkflowContext[Gathered, TickDone]) -> None:
        t = self.team
        with t.data.lock:
            cands = candidates.build(t.data, t.state, tick.clock_s, t.focus_player_id)
        t.state.last_tick_clock = tick.clock_s
        t.state.counters["candidates"] += len(cands)
        t.state.note("gather", "candidates", clock_s=tick.clock_s, n=len(cands), kinds=[c.kind for c in cands])
        if not cands:
            await ctx.yield_output(TickDone(tick.clock_s, 0))
            return
        await ctx.send_message(Gathered(tick.clock_s, cands))


# ---------------------------------------------------------------------------- live: analyst

def analyst_prompt(team: Team, clock_s: float, cands: list[Candidate]) -> str:
    st = team.data.live_state(clock_s)
    lines = [f"Minute {st['clock']['minute']} (clock_s {int(clock_s)} for live tools). Score: {st['score']['display']}."]
    if team.state.brief:
        lines.append("Pre-match storylines from the Scout:")
        lines += [f"- {s['title']}: {s['text']}" for s in team.state.brief.get("storylines", [])]
    if team.state.game_reads:
        lines.append("Your earlier reads: " + " | ".join(r["read"] for r in team.state.game_reads[-3:]))
    recent = [c for c in team.state.cues if c.get("phase") == "live" and clock_s - c.get("clock_s", 0) <= 900]
    if recent:
        lines.append("Recently on screen (last 15 minutes):")
        lines += [f"- {c['minute']}': {c['angle']}" for c in recent[-5:] if c.get("angle")]
    lines.append("Candidates:")
    lines.append(prompt_json([{"candidate_id": c.cand_id, "kind": c.kind, "minute": c.minute, "facts": c.facts,
                               "always_shown": c.must_show} for c in cands]))
    lines.append("Return a pick for every candidate (candidate_id exactly as given) and a game_read.")
    return "\n".join(lines)


class TacticalAnalyst(Executor):
    """LLM agent: ranks the candidates and adds the angle (why it matters now)."""

    def __init__(self, team: Team, id: str = "tactical_analyst"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_gathered(self, msg: Gathered, ctx: WorkflowContext[Reading]) -> None:
        t = self.team
        picks: dict[str, tuple[float, str]] = {}
        evidence: list[str] = []
        if t.agents.analyst is not None:
            prompt = analyst_prompt(t, msg.clock_s, msg.candidates)
            res = await t.llm("tactical_analyst", t.agents.analyst, prompt, AnalystReading)
            if res.value is not None:
                # What the analyst was shown (score, brief, candidates) plus any tool results it fetched.
                evidence = res.tool_texts + [prompt]
                context_names = briefing.names_in(evidence, t.verifier.roster)
                by_id = {c.cand_id: c for c in msg.candidates}
                for p in res.value.picks:
                    c = by_id.get(p.candidate_id)
                    if c is None:
                        continue
                    angle = tidy_text(p.angle)
                    # The Verifier checks the analyst too: an angle with an unsupported number is dropped.
                    probs = t.verifier.check("analyst", "en", "x", angle, c.facts, "", c.names + context_names,
                                             evidence, check_length=False) if angle else []
                    if probs:
                        t.state.note("verifier", "angle_dropped", cand_id=c.cand_id, angle=angle, problems=probs)
                        angle = ""
                    elif angle:
                        c.names = list(dict.fromkeys(c.names + briefing.names_in([angle], t.verifier.roster)))
                    picks[c.cand_id] = (p.importance, angle)
                read = tidy_text(res.value.game_read)
                facts = [f for c in msg.candidates for f in c.facts]
                if read and not t.verifier.check("analyst", "en", "x", read, facts, "", context_names,
                                                 evidence, check_length=False):
                    t.state.game_reads.append({"clock_s": msg.clock_s, "read": read})
        director.apply_reading(msg.candidates, picks)
        await ctx.send_message(Reading(msg.clock_s, msg.candidates, evidence))


# ---------------------------------------------------------------------------- live: director

class Director(Executor):
    """Code agent: what goes on screen, when, for whom."""

    def __init__(self, team: Team, id: str = "director"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_reading(self, msg: Reading, ctx: WorkflowContext[RenderJob, TickDone]) -> None:
        t = self.team
        drafts = director.direct(t.state, msg.candidates, msg.clock_s, t.cfg.min_gap_s)
        annotate(clock_s=round(msg.clock_s, 1), candidates=len(msg.candidates), on_screen=[d.candidate.kind for d in drafts])
        if not drafts:
            await ctx.yield_output(TickDone(msg.clock_s, 0))
            return
        for d in drafts:
            d.evidence_texts = msg.evidence
            await ctx.send_message(RenderJob(d, phase="live"))


# ---------------------------------------------------------------------------- fan lens (all phases)

def _limits(lang: str) -> tuple[int, int]:
    return LIMITS.get(lang, DEFAULT_LIMITS)


def fan_lens_prompt(team: Team, job: RenderJob, needed: list) -> str:
    """Prompt for one language: every requested profile in that language."""
    c = job.draft.candidate
    lang = needed[0].language
    when = "before kick-off" if job.phase == "prematch" else ("after full-time" if job.phase == "postmatch"
                                                              else f"minute {c.minute}")
    lines = [f"CUE {job.draft.cue_id}: {c.kind.replace('_', ' ')}, {when}, priority {job.draft.priority}.", "Facts:"]
    lines += [f"- {f}" for f in c.facts]
    if c.angle:
        lines.append(f"Analyst angle: {c.angle}")
    names = sorted(set(c.names))
    lines.append("Names you may use (exact spelling, Latin letters): " + ", ".join(names))
    lines.append(f"Language: {team.language_name(lang)} ({lang}). {LANGUAGE_NOTES.get(lang, '')}".rstrip())
    h, b = _limits(lang)
    lines.append(f"Length: headline at most {LENGTH_WORDS['headline']} words ({h} characters); body one or two "
                 f"short sentences, at most {LENGTH_WORDS['body']} words ({b} characters).")
    lines.append("Write these variants:")
    for v in needed:
        lines.append(f"- profile={v.profile} language={v.language}. Style: {team.style(v)}")
    if job.problems:
        lines.append("Your previous attempt was rejected by the Verifier. Fix exactly these problems:")
        for key, probs in job.problems.items():
            if key in {v.key for v in needed}:
                lines.append(f"- {key}: " + " ".join(probs))
    lines.append('Return {"variants": [...]} with profile and language exactly as listed above.')
    return "\n".join(lines)


def _match_variant(out, v, lang_names: dict[str, str]):
    for x in out:
        lang = x.language.strip().lower()
        if x.profile.strip() == v.profile and (lang == v.language or lang == lang_names.get(v.language, "").lower()):
            return x
    return None


class FanLens(Executor):
    """LLM agent: writes the cue for every viewer profile and language."""

    def __init__(self, team: Team, id: str = "fan_lens"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_job(self, job: RenderJob, ctx: WorkflowContext[RenderJob]) -> None:
        t = self.team
        c = job.draft.candidate
        job.attempt += 1
        needed = [v for v in t.viewers_for(c.audience) if v.key not in job.variants]
        job.pending = {}
        if t.agents.fan_lens is None:
            # Offline mode: the safe templates are the text.
            for v in needed:
                job.pending[v.key] = templates.fallback(c, v.profile, v.language)
        elif needed:
            # One call per language, all at once: each call focuses on one script, and the
            # slower translations run alongside English instead of after it.
            by_lang: dict[str, list] = {}
            for v in needed:
                by_lang.setdefault(v.language, []).append(v)
            langs = list(by_lang)
            results = await asyncio.gather(*[
                t.llm(f"fan_lens/{lang}", t.agents.writer_for(lang), fan_lens_prompt(t, job, by_lang[lang]), Rendered)
                for lang in langs])
            for lang, res in zip(langs, results):
                if res.value is None:
                    continue
                for v in by_lang[lang]:
                    x = _match_variant(res.value.variants, v, LANGUAGES)
                    if x is not None:
                        job.pending[v.key] = Variant(v.profile, v.language, tidy_text(x.headline), tidy_text(x.body), "llm")
        if job.attempt > 1:
            t.state.counters["rewrites"] += 1
        annotate(cue_id=job.draft.cue_id, kind=c.kind, attempt=job.attempt, variants_written=sorted(job.pending))
        await ctx.send_message(job)


# ---------------------------------------------------------------------------- verifier (all phases)

class VerifierExec(Executor):
    """Code agent: checks numbers, names, language, safety and length; sends rewrites back."""

    def __init__(self, team: Team, id: str = "verifier"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_job(self, job: RenderJob, ctx: WorkflowContext[RenderJob]) -> None:
        t = self.team
        c = job.draft.candidate
        needed = [v for v in t.viewers_for(c.audience) if v.key not in job.variants]
        problems: dict[str, list[str]] = {}
        english = job.variants.get("casual/en") or job.pending.get("casual/en")
        for v in needed:
            var = job.pending.get(v.key)
            if var is None:
                problems[v.key] = ["variant missing from your answer"]
                continue
            if var.source == "template":
                job.variants[v.key] = var
                continue
            h_max, b_max = _limits(v.language)
            trimmed = trim_to_fit(var.body, b_max, v.language)
            if trimmed and trimmed != var.body:
                t.state.note("verifier", "trimmed", cue_id=job.draft.cue_id, viewer=v.key, dropped=var.body[len(trimmed):].strip())
                var = Variant(var.profile, var.language, var.headline, trimmed, var.source)
            probs = t.verifier.check(v.profile, v.language, var.headline, var.body, c.facts, c.angle, c.names,
                                     job.draft.evidence_texts, english_body=english.body if english else None,
                                     metrics_from_facts_only=True)
            if probs:
                problems[v.key] = probs
            else:
                job.variants[v.key] = var
        job.problems = problems
        if problems:
            t.state.counters["verifier_rejections"] += len(problems)
            job.history.append({"attempt": job.attempt, "problems": problems,
                                "rejected_text": {k: (job.pending[k].headline, job.pending[k].body)
                                                  for k in problems if k in job.pending}})
            t.state.note("verifier", "rejected", cue_id=job.draft.cue_id, attempt=job.attempt, problems=problems)
        annotate(cue_id=job.draft.cue_id, attempt=job.attempt, variants_passed=sorted(job.variants),
                 variants_rejected=sorted(problems), problems=[p for ps in problems.values() for p in ps][:8])
        if not problems:
            job.passed = True
        elif job.attempt >= t.cfg.max_writer_attempts or t.agents.fan_lens is None:
            for key in problems:
                v = next(x for x in needed if x.key == key)
                job.variants[key] = templates.fallback(c, v.profile, v.language)
                t.state.counters["template_fallbacks"] += 1
            job.degraded = True
            job.final = True
        await ctx.send_message(job)


# ---------------------------------------------------------------------------- publisher (all phases)

class Publisher(Executor):
    """Writes each verified cue to the broadcast feed."""

    def __init__(self, team: Team, id: str = "publisher"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_job(self, job: RenderJob, ctx: WorkflowContext[Never, dict]) -> None:
        t = self.team
        d, c = job.draft, job.draft.candidate
        cue = {
            "cue_id": d.cue_id, "phase": job.phase, "kind": c.kind, "clock_s": c.clock_s, "minute": c.minute,
            "priority": d.priority, "duration_s": d.duration_s, "importance": round(c.importance, 2),
            "overlay": c.overlay, "facts": c.facts, "angle": c.angle,
            "evidence": {"candidate_id": c.cand_id, "event_refs": c.refs},
            "variants": {k: {"headline": v.headline, "body": v.body, "source": v.source}
                         for k, v in sorted(job.variants.items())},
            "verification": {"attempts": job.attempt, "rejections": job.history, "degraded": job.degraded},
            "published_at": _iso(),
        }
        annotate(cue_id=d.cue_id, kind=c.kind, minute=c.minute, attempts=job.attempt, degraded=job.degraded,
                 template_variants=sorted(k for k, v in job.variants.items() if v.source == "template"))
        t.state.cues.append(cue)
        t.sink.cue(cue)
        if t.on_publish:
            t.on_publish(cue)
        main = job.variants.get("casual/en") or next(iter(job.variants.values()), None)
        if main:
            tag = " (template)" if job.degraded else ""
            when = {"prematch": "PRE", "postmatch": "FT"}.get(job.phase, f"{c.minute:>2}'")
            t.log_line(f"  [{when}] {main.headline} | {main.body}{tag}")
        await ctx.yield_output(cue)


# ---------------------------------------------------------------------------- pre-match

def scout_prompt(team: Team, draft: BriefDraft | None) -> str:
    fx = team.state.matchup["fixture"]
    p = (f"Fixture: {fx['home']} (home) v {fx['away']} (away), round {fx['round']}, {fx['date']}. "
         f"Investigate with the tools and write the pre-match brief.")
    if draft and draft.feedback:
        p += ("\nThe Verifier rejected parts of your last brief. Rewrite it, using the tool results you already have:\n"
              + "\n".join(f"- {x}" for x in draft.feedback))
    return p


class Scout(Executor):
    """LLM agent with MCP tools: investigates the fixture and writes the pre-match brief."""

    def __init__(self, team: Team, id: str = "scout"):
        super().__init__(id=id)
        self.team = team
        self.session = None

    async def _run(self, draft: BriefDraft | None, ctx) -> None:
        t = self.team
        compact = prompt_json(t.data.matchup(t.state.home_id, t.state.away_id, match_id=t.state.match_id, compact=True))
        attempt = 1 if draft is None else draft.attempt + 1
        if t.agents.scout is None:
            await ctx.send_message(BriefDraft(briefing.offline_brief(t.state.matchup), [compact], attempt,
                                              source="template"))
            return
        if self.session is None:
            self.session = t.agents.scout.create_session()
        res = await t.llm("scout", t.agents.scout, scout_prompt(t, draft), PreMatchBrief, session=self.session)
        if res.session is not None:            # a retry may have had to start a fresh conversation
            self.session = res.session
        evidence = (draft.evidence if draft else []) + res.tool_texts + [compact]
        await ctx.send_message(BriefDraft(res.value, evidence, attempt))

    @handler
    async def start(self, req: PrematchRequest, ctx: WorkflowContext[BriefDraft]) -> None:
        await self._run(None, ctx)

    @handler
    async def rewrite(self, draft: BriefDraft, ctx: WorkflowContext[BriefDraft]) -> None:
        await self._run(draft, ctx)


class BriefCheck(Executor):
    """Code agent: verifies the brief (numbers, ids, names); sends it back once if needed."""

    def __init__(self, team: Team, id: str = "brief_check", max_attempts: int = 2):
        super().__init__(id=id)
        self.team = team
        self.max_attempts = max_attempts

    @handler
    async def on_draft(self, d: BriefDraft, ctx: WorkflowContext[BriefDraft]) -> None:
        t = self.team
        safe = briefing.offline_brief(t.state.matchup)
        if d.brief is None:
            d.brief, d.degraded, d.source, d.accepted = safe, True, "template", True
            t.state.note("brief_check", "fallback", reason="no brief from the Scout")
            await ctx.send_message(d)
            return
        roster = t.verifier.roster
        cleaned, feedback = briefing.check_brief(d.brief, t.state.matchup, d.evidence, t.verifier, roster)
        header_ok = not any(f.startswith(("headline", "tactical_preview")) for f in feedback)
        t.state.note("brief_check", "checked", attempt=d.attempt, kept=len(cleaned.storylines),
                     submitted=len(d.brief.storylines), feedback=feedback)
        if feedback:
            t.state.counters["verifier_rejections"] += len(feedback)
        if len(cleaned.storylines) >= 3 and header_ok:
            d.brief, d.accepted, d.feedback = cleaned, True, feedback
        elif d.attempt < self.max_attempts and d.source == "llm":
            d.feedback, d.accepted = feedback, False
        else:
            d.brief = briefing.merge_with_safe(cleaned, safe, header_ok)
            d.accepted, d.degraded = True, True
        await ctx.send_message(d)


class BriefCues(Executor):
    """Turns the verified brief into pre-match cues for every viewer."""

    def __init__(self, team: Team, id: str = "brief_cues"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_brief(self, d: BriefDraft, ctx: WorkflowContext[RenderJob]) -> None:
        t = self.team
        b: PreMatchBrief = d.brief
        t.state.brief = briefing.brief_json(b, d.degraded, d.source)
        t.scout_evidence = d.evidence
        t.sink.json("brief.json", t.state.brief)
        clubs = [t.state.home, t.state.away]
        edges = {e["edge_id"]: e for e in t.state.matchup["edges"]}
        items = [("brief_intro", [b.headline, b.tactical_preview], {"headline": b.headline}, "intro")]
        for i, s in enumerate(b.storylines, 1):
            support = [briefing.tidy(edges[x]["explanation"]) for x in s.evidence_ids if x in edges]
            items.append(("storyline", [s.text] + support,
                          {"index": i, "title": s.title, "confidence": s.confidence, "evidence_ids": s.evidence_ids},
                          s.title))
        for kind, facts, data, subject in items:
            names = briefing.names_in(facts, t.verifier.roster) + clubs
            t.state.counters["cues"] += 1
            cand = Candidate(f"brief:{subject}", kind, 0.0, 0, 0.9, facts, names, [],
                             {"template": kind, "data": data}, subject=f"brief:{subject}", must_show=True)
            cand.importance = 0.9
            draft = CueDraft(f"cue-{t.state.counters['cues']:03d}", cand, "high", 15, evidence_texts=d.evidence)
            await ctx.send_message(RenderJob(draft, phase="prematch"))


# ---------------------------------------------------------------------------- post-match

def recap_prompt(team: Team, d: RecapDraft) -> str:
    lines = ["Full-time fact sheet:"] + [f"- {f}" for f in d.facts]
    if team.state.brief:
        lines.append("The pre-match brief said: " + " | ".join(s["title"] + ": " + s["text"]
                                                              for s in team.state.brief["storylines"]))
    lines.append("Player of the match must be one of: " + ", ".join(x["name"] for x in d.top))
    if d.feedback:
        lines.append("The Verifier rejected your last recap. Fix exactly these problems:")
        lines += [f"- {x}" for x in d.feedback]
    return "\n".join(lines)


class RecapWriter(Executor):
    """LLM agent: writes the post-match recap from the fact sheet."""

    def __init__(self, team: Team, id: str = "recap"):
        super().__init__(id=id)
        self.team = team

    async def _run(self, d: RecapDraft, ctx) -> None:
        t = self.team
        if t.agents.recap is None:
            d.recap, d.source = briefing.offline_recap(d.facts, d.top, t.data), "template"
        else:
            res = await t.llm("recap", t.agents.recap, recap_prompt(t, d), Recap)
            d.recap = res.value
        await ctx.send_message(d)

    @handler
    async def start(self, req: PostmatchRequest, ctx: WorkflowContext[RecapDraft]) -> None:
        with self.team.data.lock:
            facts, top = briefing.recap_facts(self.team.data, self.team.state)
        await self._run(RecapDraft(facts=facts, top=top), ctx)

    @handler
    async def rewrite(self, d: RecapDraft, ctx: WorkflowContext[RecapDraft]) -> None:
        d.attempt += 1
        await self._run(d, ctx)


class RecapCheck(Executor):
    def __init__(self, team: Team, id: str = "recap_check", max_attempts: int = 2):
        super().__init__(id=id)
        self.team = team
        self.max_attempts = max_attempts

    @handler
    async def on_draft(self, d: RecapDraft, ctx: WorkflowContext[RecapDraft]) -> None:
        t = self.team
        if d.recap is None:
            d.recap, d.degraded, d.source, d.accepted = briefing.offline_recap(d.facts, d.top, t.data), True, "template", True
        else:
            probs = briefing.check_recap(d.recap, d.facts, d.top, t.verifier, [t.state.home, t.state.away])
            t.state.note("recap_check", "checked", attempt=d.attempt, problems=probs)
            if not probs:
                d.accepted = True
            elif d.attempt < self.max_attempts and d.source == "llm":
                t.state.counters["verifier_rejections"] += len(probs)
                d.feedback, d.accepted = probs, False
            else:
                d.recap, d.degraded, d.accepted = briefing.offline_recap(d.facts, d.top, t.data), True, True
        await ctx.send_message(d)


class RecapCues(Executor):
    def __init__(self, team: Team, id: str = "recap_cues"):
        super().__init__(id=id)
        self.team = team

    @handler
    async def on_recap(self, d: RecapDraft, ctx: WorkflowContext[RenderJob]) -> None:
        t = self.team
        r: Recap = d.recap
        out = json.loads(r.model_dump_json()) | {"facts": d.facts, "degraded": d.degraded, "source": d.source,
                                                  "cues_published": len(t.state.cues)}
        t.state.recap = out
        t.sink.json("recap.json", out)
        facts = [r.headline, r.summary, r.plan_vs_reality, f"Player of the match: {r.player_of_the_match}. {r.player_reason}"]
        names = briefing.names_in(facts + d.facts, t.verifier.roster) + [t.state.home, t.state.away]
        end = t.data.live.end_clock
        t.state.counters["cues"] += 1
        cand = Candidate("recap", "recap", end, 90, 1.0, facts, names, [],
                         {"template": "recap", "data": {"player_of_the_match": r.player_of_the_match}},
                         subject="recap", must_show=True)
        cand.importance = 1.0
        draft = CueDraft(f"cue-{t.state.counters['cues']:03d}", cand, "high", 30, evidence_texts=d.facts)
        await ctx.send_message(RenderJob(draft, phase="postmatch"))


__all__ = ["Tick", "TickDone", "PrematchRequest", "PostmatchRequest", "Gather", "TacticalAnalyst", "Director", "FanLens",
           "VerifierExec", "Publisher", "Scout", "BriefCheck", "BriefCues", "RecapWriter", "RecapCheck", "RecapCues"]
