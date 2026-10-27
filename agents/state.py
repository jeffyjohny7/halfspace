"""Shared state of one broadcast, read and written by every agent in the team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Candidate:
    """Something the stats engine thinks could go on screen, with the facts behind it."""

    cand_id: str
    kind: str
    clock_s: float
    minute: int
    base_priority: float
    facts: list[str]
    names: list[str]
    refs: list[dict]
    overlay: dict
    subject: str
    must_show: bool = False
    audience: str = "all"
    importance: float = 0.0
    angle: str = ""


@dataclass
class CueDraft:
    cue_id: str
    candidate: Candidate
    priority: str
    duration_s: float
    evidence_texts: list[str] = field(default_factory=list)   # tool results the analyst saw


@dataclass
class Variant:
    profile: str
    language: str
    headline: str
    body: str
    source: str = "llm"   # llm | template


@dataclass
class RenderJob:
    """One cue on its way through Fan Lens -> Verifier (-> Fan Lens ...) -> Publisher."""

    draft: CueDraft
    phase: str = "live"                                              # prematch | live | postmatch
    variants: dict[str, Variant] = field(default_factory=dict)       # viewer key -> text that passed
    pending: dict[str, Variant] = field(default_factory=dict)        # viewer key -> text waiting for checks
    attempt: int = 0
    problems: dict[str, list[str]] = field(default_factory=dict)     # viewer key -> problems from last check
    history: list[dict] = field(default_factory=list)                # every rejection, for the run log
    passed: bool = False
    final: bool = False
    degraded: bool = False


@dataclass
class BroadcastState:
    match_id: str
    home_id: str
    away_id: str
    home: str
    away: str
    viewers: list[Any]
    matchup: dict | None = None
    brief: dict | None = None
    recap: dict | None = None
    last_tick_clock: float = -1.0
    last_cue_clock: dict[str, float] = field(default_factory=dict)       # audience -> clock
    subject_shown: dict[str, float] = field(default_factory=dict)        # subject -> clock
    prediction_status: dict[str, str] = field(default_factory=dict)
    last_tempo: tuple | None = None                                     # (label, clock) last shown
    stat_marks_done: set = field(default_factory=set)
    periods_done: set = field(default_factory=set)
    cues: list[dict] = field(default_factory=list)
    game_reads: list[dict] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {
        "llm_calls": 0, "llm_failures": 0, "verifier_rejections": 0, "rewrites": 0, "template_fallbacks": 0,
        "cues": 0, "candidates": 0, "guardrail_blocks": 0})

    def note(self, agent: str, event: str, **kw) -> None:
        self.log.append({"agent": agent, "event": event, **kw})
