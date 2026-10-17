"""Build the derived statistics tables used by the MCP server and agents.

Usage (from the project folder, after scripts/generate.py):
    uv run scripts/build_stats.py
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.build import build_all  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    args = ap.parse_args()
    build_all(args.data)


if __name__ == "__main__":
    main()
