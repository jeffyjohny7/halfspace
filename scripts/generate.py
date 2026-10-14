"""Generate the full synthetic league universe.

Usage (from the project folder):
    uv run scripts/generate.py               # full run with defaults
    uv run scripts/generate.py --seed 7      # a different universe
    uv run scripts/generate.py --workers 4   # limit CPU cores
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchsim.config import SimConfig  # noqa: E402
from matchsim.pipeline import generate  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=SimConfig.seed)
    ap.add_argument("--out", default=SimConfig.out_dir)
    ap.add_argument("--workers", type=int, default=0, help="0 = all CPU cores")
    ap.add_argument("--rounds-played", type=int, default=SimConfig.current_rounds_played)
    ap.add_argument("--cl-spots", type=int, default=SimConfig.champions_league_spots)
    ap.add_argument("--showcase-variants", type=int, default=SimConfig.showcase_variants)
    args = ap.parse_args()
    cfg = SimConfig(seed=args.seed, out_dir=args.out, workers=args.workers,
                    current_rounds_played=args.rounds_played,
                    showcase_round=args.rounds_played + 1,
                    champions_league_spots=args.cl_spots,
                    showcase_variants=args.showcase_variants)
    summary = generate(cfg)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
