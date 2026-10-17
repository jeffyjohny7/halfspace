"""Small helpers: JSON-safe values and formatting."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


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
