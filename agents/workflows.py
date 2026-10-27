"""The three Agent Framework workflows of a broadcast.

Pre-match:   Scout <-> BriefCheck -> BriefCues -> FanLens <-> Verifier -> Publisher
Live tick:   Gather -> TacticalAnalyst -> Director -> FanLens <-> Verifier -> Publisher
Post-match:  Recap <-> RecapCheck -> RecapCues -> FanLens <-> Verifier -> Publisher

The <-> loops are conditional edges: the checker sends work back to the writer with
specific feedback until it passes, or the attempt limit hands over to a safe template.
"""

from __future__ import annotations

from agent_framework import WorkflowBuilder

from .executors import (BriefCheck, BriefCues, Director, FanLens, Gather, Publisher, RecapCheck, RecapCues, RecapWriter,
                        Scout, TacticalAnalyst, VerifierExec)
from .team import Team


def _needs_rewrite(job) -> bool:
    return not job.passed and not job.final


def _done(job) -> bool:
    return job.passed or job.final


def live_tick(team: Team):
    gather, analyst, director = Gather(team), TacticalAnalyst(team), Director(team)
    pub = Publisher(team)
    lens, check = FanLens(team), VerifierExec(team)
    b = WorkflowBuilder(name="live_tick", start_executor=gather, output_from=[gather, director, pub])
    (b.add_edge(gather, analyst)
      .add_edge(analyst, director)
      .add_edge(director, lens)
      .add_edge(lens, check)
      .add_edge(check, lens, condition=_needs_rewrite)
      .add_edge(check, pub, condition=_done))
    return b.build()


def prematch(team: Team):
    scout, brief_check, brief_cues = Scout(team), BriefCheck(team), BriefCues(team)
    pub = Publisher(team)
    lens, check = FanLens(team), VerifierExec(team)
    b = WorkflowBuilder(name="prematch", start_executor=scout, output_from=[pub])
    (b.add_edge(scout, brief_check)
      .add_edge(brief_check, scout, condition=lambda d: not d.accepted)
      .add_edge(brief_check, brief_cues, condition=lambda d: d.accepted)
      .add_edge(brief_cues, lens)
      .add_edge(lens, check)
      .add_edge(check, lens, condition=_needs_rewrite)
      .add_edge(check, pub, condition=_done))
    return b.build()


def postmatch(team: Team):
    recap, recap_check, recap_cues = RecapWriter(team), RecapCheck(team), RecapCues(team)
    pub = Publisher(team)
    lens, check = FanLens(team), VerifierExec(team)
    b = WorkflowBuilder(name="postmatch", start_executor=recap, output_from=[pub])
    (b.add_edge(recap, recap_check)
      .add_edge(recap_check, recap, condition=lambda d: not d.accepted)
      .add_edge(recap_check, recap_cues, condition=lambda d: d.accepted)
      .add_edge(recap_cues, lens)
      .add_edge(lens, check)
      .add_edge(check, lens, condition=_needs_rewrite)
      .add_edge(check, pub, condition=_done))
    return b.build()
