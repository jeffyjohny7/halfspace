"""Run the AI broadcast team on the showcase match.

    uv run scripts/run_broadcast.py                         # Foundry (gpt-5-mini), English + Spanish + Arabic + Hindi + Malayalam
    uv run scripts/run_broadcast.py --offline               # no model: safe templates only (tests, fallback)
    uv run scripts/run_broadcast.py --dry-run               # scripted model + real MCP tools + real workflows
    uv run scripts/run_broadcast.py --favourite-club Oxmere --focus-player "Yannick Fallund"
    uv run scripts/run_broadcast.py --until-minute 30       # quick partial run
    uv run scripts/run_broadcast.py --speed 20              # paced: 20x real time, for a live demo
    uv run scripts/run_broadcast.py --trace                 # also send traces to the Foundry Tracing page
    uv run scripts/run_broadcast.py --trace-content         # ... including prompts, replies and tool results

Output: data/runtime/broadcast/ (brief.json, cues.jsonl, recap.json, run_log.json)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.config import LANGUAGES, BroadcastConfig  # noqa: E402
from agents.runner import Broadcast  # noqa: E402


def main() -> None:
    for stream in (sys.stdout, sys.stderr):        # never crash on a console that cannot print a character
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="no model calls; deterministic templates")
    ap.add_argument("--dry-run", action="store_true",
                    help="scripted stand-in model (makes deliberate mistakes); checks the whole pipeline without Azure")
    ap.add_argument("--languages", default="es,ar,hi,ml", help=f"extra languages, comma separated ({', '.join(LANGUAGES)}); '' for none")
    ap.add_argument("--favourite-club", help="adds a supporter's view for this club (id or name)")
    ap.add_argument("--focus-player", help="adds a player-focus stream for this player (id or name)")
    ap.add_argument("--until-minute", type=float, help="stop the live part at this minute")
    ap.add_argument("--speed", type=float, default=0.0, help="pace the feed at N x real time (0 = as fast as possible)")
    ap.add_argument("--tick", type=float, default=180.0, help="seconds of play between regular check-ins")
    ap.add_argument("--no-prematch", action="store_true")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", help="output folder (default <data>/runtime/broadcast)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--trace", action="store_true",
                    help="send traces to the Foundry project (Tracing page); needs Application Insights connected")
    ap.add_argument("--trace-content", action="store_true",
                    help="like --trace, and record prompts, replies and tool results too (synthetic data only)")
    a = ap.parse_args()
    langs = tuple(x.strip() for x in a.languages.split(",") if x.strip())
    bad = [x for x in langs if x not in LANGUAGES]
    if bad:
        ap.error(f"unknown language codes: {bad}")
    cfg = BroadcastConfig(data_dir=a.data, mode="offline" if a.offline else "foundry", languages=langs,
                          favourite_club=a.favourite_club, focus_player=a.focus_player, tick_every_s=a.tick,
                          out_dir=a.out, verbose=not a.quiet)
    if a.trace or a.trace_content:
        cfg.trace = True
    if a.trace_content:
        cfg.trace_content = True
    client = None
    if a.dry_run:
        from agents.dryrun import dry_run_client
        client, cfg.mode = dry_run_client(), "dry-run"
    asyncio.run(Broadcast(cfg, client=client).run(until_minute=a.until_minute, speed=a.speed,
                                                  prematch=not a.no_prematch))


if __name__ == "__main__":
    main()
