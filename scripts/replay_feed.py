"""Replay the showcase match as a live feed.

Prints events as they "happen" and keeps data/runtime/live_clock.json up to
date, so the MCP live tools can never see past the current moment.

Usage:
    uv run scripts/replay_feed.py                  # 60x speed: one minute of play per second
    uv run scripts/replay_feed.py --speed 1        # real time
    uv run scripts/replay_feed.py --from-minute 70 --speed 30
    uv run scripts/replay_feed.py --reset          # remove the clock (live tools see everything)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.store import Store  # noqa: E402

SHOW = {"shot", "card", "substitution", "own_goal", "period_start", "period_end", "offside"}


def _ok(v) -> bool:
    return v is not None and not (isinstance(v, float) and v != v)


def write_clock(path: Path, match_id: str, clock_s: float, retries: int = 6) -> bool:
    """Atomically update the live clock."""
    data = json.dumps({"match_id": match_id, "clock_s": round(clock_s, 1)})
    tmp = path.with_suffix(".tmp")
    for attempt in range(retries):
        try:
            tmp.write_text(data, encoding="utf-8")
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.02 * (attempt + 1))
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--speed", type=float, default=60.0, help="seconds of play per real second")
    ap.add_argument("--from-minute", type=float, default=0.0)
    ap.add_argument("--all-events", action="store_true", help="print every event, not just the notable ones")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    store = Store(args.data)
    runtime = Path(args.data) / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    clock_file = runtime / "live_clock.json"
    if args.reset:
        clock_file.unlink(missing_ok=True)
        print("Live clock removed.")
        return
    meta = store.showcase_meta
    ev = store.showcase_events().sort_values("clock_s")
    names = store.club_names
    pnames = store.player_names
    start = args.from_minute * 60.0
    print(f"{meta['home']} vs {meta['away']} - replaying at {args.speed:g}x", flush=True)
    t0 = time.time()
    last_write = 0.0
    for r in ev.itertuples():
        if r.clock_s < start:
            continue
        due = (r.clock_s - start) / args.speed
        wait = due - (time.time() - t0)
        if wait > 0:
            time.sleep(wait)
        notable = r.type in SHOW
        # Update the clock at most 5 times a second (and always at notable events).
        if notable or time.time() - last_write >= 0.2:
            if write_clock(clock_file, meta["match_id"], r.clock_s):
                last_write = time.time()
        if args.all_events or notable:
            who = pnames.get(r.player_id, "") if _ok(r.player_id) else ""
            extra = f" {r.outcome}" if _ok(r.outcome) else ""
            if r.type == "shot":
                extra += f" xG {r.xg:.2f}"
            if _ok(r.card):
                extra += f" {r.card}"
            print(f"{int(r.minute):3d}:{int(r.second):02d}  {names.get(r.team_id, ''):22s} {r.type}{extra}  {who}",
                  flush=True)
    write_clock(clock_file, meta["match_id"], float(ev.clock_s.max()))
    print("Full time. Live clock left at the final whistle (use --reset to remove it).")


if __name__ == "__main__":
    main()
