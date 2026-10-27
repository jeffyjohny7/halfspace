"""Small helpers: JSON-safe values and formatting."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


# The league's two European competitions are fictional too (internal ids kept from generation).
COMPETITION_NAMES = {"champions_league": "Continental Cup", "europa_league": "Continental Shield"}


def competition_name(cid: str) -> str:
    return COMPETITION_NAMES.get(cid, str(cid).replace("_", " ").title())


def public_rules(rules: dict) -> dict:
    """League rules with the European places under the fictional competition names."""
    out = {k: v for k, v in rules.items() if k not in ("champions_league_spots", "europa_league_spots")}
    if "champions_league_spots" in rules:
        out["continental_cup_spots"] = rules["champions_league_spots"]
    if "europa_league_spots" in rules:
        out["continental_shield_spots"] = rules["europa_league_spots"]
    return out


def clean(obj: Any, nd: int = 3) -> Any:
    """Recursively convert numpy/pandas values to plain JSON-safe Python, rounding floats."""
    if isinstance(obj, dict):
        return {str(k): clean(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v, nd) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return [clean(r, nd) for r in obj.to_dict("records")]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, nd)
    if obj is pd.NA or obj is pd.NaT:
        return None
    return obj


def pct_rank(value: float, population) -> float | None:
    pop = pd.Series(population).dropna()
    if value is None or (isinstance(value, float) and math.isnan(value)) or pop.empty:
        return None
    return float((pop < value).mean() * 100 + (pop == value).mean() * 50)
