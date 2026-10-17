"""Read-only access to public and derived data, with a guard against hidden data."""

from __future__ import annotations

import json
from functools import cached_property, lru_cache
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# String columns stored as pandas categoricals to keep memory low.
EVENT_CATEGORICALS = ["match_id", "team_id", "player_id", "type", "outcome", "receiver_id",
                      "pass_type", "body_part", "set_piece", "play_pattern", "related_player_id", "card"]


class HiddenDataError(PermissionError):
    """Raised when code tries to read the hidden answer-key folder."""


def _guard(path: Path, allowed: list[Path]) -> Path:
    path = path.resolve()
    if "hidden" in {p.lower() for p in path.parts}:
        raise HiddenDataError(f"Refusing to read hidden data: {path}")
    if not any(path == a or a in path.parents for a in allowed):
        raise HiddenDataError(f"Path outside public/derived data: {path}")
    return path


def read_events(path: Path, columns: list[str] | None = None, filters=None) -> pd.DataFrame:
    schema_names = pq.read_schema(path).names
    cats = [c for c in EVENT_CATEGORICALS if c in schema_names and (columns is None or c in columns)]
    table = pq.read_table(path, columns=columns, filters=filters, read_dictionary=cats)
    return table.to_pandas()


class Store:
    """Loads public tables lazily and caches them for the life of the process."""

    def __init__(self, data_dir: str | Path = "data"):
        self.root = Path(data_dir).resolve()
        self.public = self.root / "public"
        self.derived = self.root / "derived"
        if not self.public.exists():
            raise FileNotFoundError(f"No public data at {self.public}. Run scripts/generate.py first.")

    # -- paths ---------------------------------------------------------------
    def public_path(self, *parts: str) -> Path:
        return _guard(self.public.joinpath(*parts), [self.public])

    def derived_path(self, *parts: str) -> Path:
        return _guard(self.derived.joinpath(*parts), [self.derived])

    # -- small public tables -------------------------------------------------
    @cached_property
    def league(self) -> dict:
        return json.loads(self.public_path("league.json").read_text(encoding="utf-8"))

    @property
    def seasons(self) -> list[str]:
        return list(self.league["seasons"])

    @property
    def previous_season(self) -> str:
        return self.seasons[0]

    @property
    def current_season(self) -> str:
        return self.seasons[-1]

    @cached_property
    def clubs(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("clubs.csv"))

    @cached_property
    def club_seasons(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("club_seasons.csv"))

    @cached_property
    def players(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("players.csv"))

    @cached_property
    def squads(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("squads.csv"))

    @cached_property
    def matches(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("matches.csv"))

    @cached_property
    def lineups(self) -> pd.DataFrame:
        df = pd.read_csv(self.public_path("lineups.csv"), low_memory=False)
        if "rested" in df.columns:
            df["rested"] = df["rested"].fillna(False).astype(bool)
        return df

    @cached_property
    def standings(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("standings.csv"))

    @cached_property
    def european_fixtures(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("european_fixtures.csv"))

    @cached_property
    def upcoming(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("upcoming_fixtures.csv"))

    @cached_property
    def offseason(self) -> dict:
        return json.loads(self.public_path("offseason.json").read_text(encoding="utf-8"))

    @cached_property
    def showcase_meta(self) -> dict:
        return json.loads(self.public_path("showcase", "showcase_match.json").read_text(encoding="utf-8"))

    @cached_property
    def showcase_lineups(self) -> pd.DataFrame:
        return pd.read_csv(self.public_path("showcase", "showcase_lineups.csv"))

    # -- events --------------------------------------------------------------
    def events_path(self, season: str) -> Path:
        return self.public_path("events", f"events_{season}.parquet")

    def events(self, season: str, columns: list[str] | None = None, match_ids: list[str] | None = None) -> pd.DataFrame:
        filters = [("match_id", "in", list(match_ids))] if match_ids else None
        return read_events(self.events_path(season), columns, filters)

    def showcase_events(self) -> pd.DataFrame:
        return read_events(self.public_path("showcase", "showcase_events.parquet"))

    # -- derived tables (built by scripts/build_stats.py) -------------------
    @lru_cache(maxsize=16)
    def table(self, name: str) -> pd.DataFrame:
        path = self.derived_path(f"{name}.parquet")
        if not path.exists():
            raise FileNotFoundError(f"Missing derived table {name}. Run scripts/build_stats.py first.")
        return pd.read_parquet(path)

    @cached_property
    def xt_grid(self) -> dict:
        return json.loads(self.derived_path("xt_grid.json").read_text(encoding="utf-8"))

    # -- lookups -------------------------------------------------------------
    @cached_property
    def club_names(self) -> dict[str, str]:
        return dict(zip(self.clubs.club_id, self.clubs.name))

    @cached_property
    def player_names(self) -> dict[str, str]:
        return dict(zip(self.players.player_id, self.players.name))

    @cached_property
    def player_positions(self) -> dict[str, str]:
        return dict(zip(self.players.player_id, self.players.position))

    def club_name(self, club_id: str) -> str:
        return self.club_names.get(club_id, club_id)

    def player_name(self, player_id: str | None) -> str | None:
        if player_id is None or (isinstance(player_id, float) and pd.isna(player_id)):
            return None
        return self.player_names.get(player_id, player_id)

    def club_season(self, club_id: str, season: str) -> dict | None:
        cs = self.club_seasons
        row = cs[(cs.club_id == club_id) & (cs.season == season)]
        return None if row.empty else row.iloc[0].to_dict()

    def division_of(self, club_id: str, season: str) -> int | None:
        row = self.club_season(club_id, season)
        return None if row is None else int(row["division"])

    def manager_changed(self, club_id: str, season: str) -> bool:
        idx = self.seasons.index(season)
        if idx == 0:
            return False
        a = self.club_season(club_id, self.seasons[idx - 1])
        b = self.club_season(club_id, season)
        return bool(a and b and a["manager_id"] != b["manager_id"])

    def player_club(self, player_id: str, season: str) -> str | None:
        sq = self.squads
        row = sq[(sq.player_id == player_id) & (sq.season == season)]
        return None if row.empty else row.iloc[0].club_id
