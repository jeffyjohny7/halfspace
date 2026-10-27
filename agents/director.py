"""The Director: decides what goes on screen, when, and for whom.

Pure policy code, so its decisions are predictable and explainable:
* goals, red cards, half-time and full-time always go out (must-show);
* everything else needs enough importance, a free slot (minimum gap between cues
  per audience) and novelty (the same subject is not repeated within 10 minutes);
* at most one regular cue per audience per tick, two when something is very important.
Every decision, including what was skipped and why, is written to the run log.
"""

from __future__ import annotations

from .state import BroadcastState, Candidate, CueDraft

NOVELTY_S = 600.0
MIN_IMPORTANCE = 0.35
DURATION_S = {"goal": 20, "red_card": 15, "prediction_confirmed": 18, "half_time": 20, "full_time": 25,
              "penalty_missed": 15, "player_focus": 14}


def _priority(c: Candidate) -> str:
    if c.must_show:
        return "breaking"
    return "high" if c.importance >= 0.75 else ("normal" if c.importance >= 0.45 else "low")


def apply_reading(candidates: list[Candidate], picks: dict[str, tuple[float, str]]) -> None:
    """Blend the analyst's importance with the engine's base priority.

    The analyst can raise or lower an item by at most 0.3, so one odd model judgement
    can neither bury a goal nor push a routine stat to the top.
    """
    for c in candidates:
        imp, angle = picks.get(c.cand_id, (None, ""))
        if imp is None:
            c.importance = c.base_priority
        else:
            c.importance = max(c.base_priority - 0.3, min(c.base_priority + 0.3, float(imp)))
        if c.must_show:
            c.importance = max(c.importance, c.base_priority)
        c.angle = angle or ""


def direct(state: BroadcastState, candidates: list[Candidate], clock_s: float, min_gap_s: float) -> list[CueDraft]:
    chosen: list[Candidate] = []
    order = sorted(candidates, key=lambda c: (not c.must_show, -c.importance, c.clock_s))
    taken_per_audience: dict[str, int] = {}
    for c in order:
        aud = c.audience
        reason = None
        if not c.must_show:
            last_subject = state.subject_shown.get(c.subject)
            last_cue = state.last_cue_clock.get(aud, -1e9)
            n = taken_per_audience.get(aud, 0)
            if c.importance < MIN_IMPORTANCE:
                reason = f"importance {c.importance:.2f} below {MIN_IMPORTANCE}"
            elif last_subject is not None and clock_s - last_subject < NOVELTY_S:
                reason = f"same subject shown {int((clock_s - last_subject) / 60)} min ago"
            elif n == 0 and clock_s - last_cue < min_gap_s and c.importance < 0.75:
                reason = f"screen busy (last cue {int(clock_s - last_cue)} s ago)"
            elif n >= (2 if c.importance >= 0.8 else 1):
                reason = "already one cue this tick"
        if reason:
            state.note("director", "skip", cand_id=c.cand_id, kind=c.kind, minute=c.minute, reason=reason,
                       importance=round(c.importance, 2))
            continue
        chosen.append(c)
        taken_per_audience[aud] = taken_per_audience.get(aud, 0) + 1
        state.subject_shown[c.subject] = clock_s
        state.last_cue_clock[aud] = clock_s
        state.note("director", "select", cand_id=c.cand_id, kind=c.kind, minute=c.minute,
                   importance=round(c.importance, 2), must_show=c.must_show)
    chosen.sort(key=lambda c: c.clock_s)
    drafts = []
    for c in chosen:
        state.counters["cues"] += 1
        drafts.append(CueDraft(cue_id=f"cue-{state.counters['cues']:03d}", candidate=c, priority=_priority(c),
                               duration_s=DURATION_S.get(c.kind, 12)))
    return drafts
