"""Configuration for the synthetic league universe."""

from __future__ import annotations

from dataclasses import dataclass, field

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
GOAL_Y = PITCH_WIDTH / 2
BOX_X = PITCH_LENGTH - 16.5  # attacking penalty box starts here
BOX_HALF_WIDTH = 20.16


@dataclass
class SimConfig:
    seed: int = 2026
    # League structure
    top_division_size: int = 20
    second_division_size: int = 24
    relegation_spots: int = 3          # bottom 3 go down
    automatic_promotion: int = 2       # top 2 of the second tier go up...
    playoff_places: tuple[int, int] = (3, 6)  # ...plus the winner of a 3rd-6th playoff
    # European places, decided by the top-division table.
    # 5 Champions League spots assumes the country earned a European Performance Spot;
    # set to 4 for a normal year.
    champions_league_spots: int = 5
    europa_league_spots: int = 1
    # Seasons
    previous_season: str = "2025-26"
    current_season: str = "2026-27"
    current_rounds_played: int = 10    # history available to the Scout this season
    showcase_round: int = 11           # the match streamed "live"
    showcase_variants: int = 20        # simulate N versions, keep the best story
    # Offseason
    transfers_per_summer: int = 18
    manager_changes: int = 3           # in addition to relegated clubs changing manager
    # Output
    out_dir: str = "data"
    workers: int = 0                   # 0 = use all CPU cores
    extra: dict = field(default_factory=dict)
