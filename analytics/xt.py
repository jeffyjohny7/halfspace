"""Expected threat (xT), learned from the league's own event data."""

from __future__ import annotations

import numpy as np
import pandas as pd

L, W = 105.0, 68.0
GX, GY = 16, 12
MOVE_TYPES = ("pass", "carry", "take_on")


def cell_index(x, y) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    cx = np.clip((x / L * GX).astype(int), 0, GX - 1)
    cy = np.clip((y / W * GY).astype(int), 0, GY - 1)
    return cx * GY + cy


def train(events: pd.DataFrame, iterations: int = 40) -> np.ndarray:
    n = GX * GY
    t = events["type"].astype(str)
    shots = events[(t == "shot") & (events["set_piece"].astype(str) != "penalty")]
    sc = cell_index(shots.x, shots.y)
    shot_n = np.bincount(sc, minlength=n).astype(float)
    goal_n = np.bincount(sc, weights=(shots.outcome.astype(str) == "goal").astype(float), minlength=n)

    moves = events[t.isin(MOVE_TYPES)]
    move_n = np.bincount(cell_index(moves.x, moves.y), minlength=n).astype(float)
    out = moves.outcome.astype(str)
    ok = moves[(out.isin(["complete", "success"])) & moves.end_x.notna()]
    a = cell_index(ok.x, ok.y)
    b = cell_index(ok.end_x, ok.end_y)
    trans = np.zeros((n, n))
    np.add.at(trans, (a, b), 1.0)

    total = shot_n + move_n
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.where(total > 0, shot_n / total, 0.0)
        m = np.where(total > 0, move_n / total, 0.0)
        g = np.where(shot_n > 0, goal_n / shot_n, 0.0)
        T = np.where(move_n[:, None] > 0, trans / move_n[:, None], 0.0)
    xt = np.zeros(n)
    for _ in range(iterations):
        xt = s * g + m * (T @ xt)
    return xt.reshape(GX, GY)


def lookup(grid: np.ndarray, x, y) -> np.ndarray:
    return grid.reshape(-1)[cell_index(x, y)]


def to_json(grid: np.ndarray, trained_on: str) -> dict:
    return {"grid_x": GX, "grid_y": GY, "pitch": [L, W], "trained_on": trained_on,
            "frame": "acting team attacks toward x = 105; row index = x cell, column = y cell",
            "values": [[round(float(v), 5) for v in row] for row in grid]}


def from_json(obj: dict) -> np.ndarray:
    return np.asarray(obj["values"], dtype=float)
