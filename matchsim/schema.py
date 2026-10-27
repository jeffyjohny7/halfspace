"""Event schema and helpers shared by the generator and future consumers
(stats engine, MCP server, agents, broadcast renderer)."""

from __future__ import annotations

import pyarrow as pa

from .config import PITCH_LENGTH, PITCH_WIDTH

EVENT_SCHEMA = pa.schema([
    ("match_id", pa.string()),
    ("event_id", pa.int32()),
    ("possession_id", pa.int32()),
    ("period", pa.int8()),
    ("minute", pa.int16()),
    ("second", pa.int8()),
    ("clock_s", pa.float32()),
    ("team_id", pa.string()),
    ("player_id", pa.string()),
    ("type", pa.string()),
    ("outcome", pa.string()),
    ("x", pa.float32()),
    ("y", pa.float32()),
    ("end_x", pa.float32()),
    ("end_y", pa.float32()),
    ("receiver_id", pa.string()),
    ("under_pressure", pa.bool_()),
    ("pass_type", pa.string()),
    ("pass_length", pa.float32()),
    ("difficulty", pa.float32()),
    ("body_part", pa.string()),
    ("xg", pa.float32()),
    ("ball_speed_kmh", pa.float32()),
    ("set_piece", pa.string()),
    ("play_pattern", pa.string()),
    ("set_piece_phase", pa.bool_()),
    ("related_player_id", pa.string()),
    ("card", pa.string()),
    ("score_home", pa.int8()),
    ("score_away", pa.int8()),
])

EVENT_COLUMNS = [f.name for f in EVENT_SCHEMA]

COLUMN_NOTES = {
    "minute": "Football clock: the second half starts at 45:00; stoppage time continues past 45/90",
    "clock_s": "Seconds of play since kick-off, monotonic across both halves (use it to replay the feed)",
}

EVENT_TYPES = {
    "pass": "Any pass, cross, throw-in or restart. outcome: complete / incomplete / out / offside",
    "carry": "Player moves with the ball",
    "take_on": "Dribble past an opponent. outcome: success / fail / fouled",
    "pressure": "Defender closes down the ball carrier (related_player_id = carrier)",
    "dispossessed": "Carrier loses the ball to a challenge while pressed",
    "tackle": "Defender wins the ball in a challenge",
    "interception": "Defender cuts out a pass",
    "ball_recovery": "Player picks up a loose ball",
    "block": "Defender blocks a pass or shot",
    "clearance": "Defensive clearance (foot or head)",
    "aerial_duel": "Header contest. outcome: won / lost",
    "shot": "Shot. outcome: goal / saved / off_target / blocked; xg is the location model",
    "own_goal": "Defender scores against own team",
    "gk_save": "Goalkeeper save",
    "gk_claim": "Goalkeeper catches a cross",
    "foul": "Foul committed (related_player_id = fouled player)",
    "foul_won": "Foul suffered",
    "card": "card: yellow / second_yellow / red",
    "offside": "Player caught offside",
    "substitution": "player_id goes off, related_player_id comes on. outcome: off (tactical) / injury",
    "injury": "Player hurt. outcome: off (replaced) / played_on (carries a knock). Details in injuries.csv",
    "period_start": "Half starts",
    "period_end": "Half ends",
}


def to_absolute(x: float, y: float, team_is_home: bool, period: int) -> tuple[float, float]:
    """Convert an event's team-relative coordinates to a fixed broadcast frame.

    Broadcast frame: the home team attacks toward x = 105 in the first half and
    toward x = 0 in the second half; y = 0 is the touchline nearest the camera.
    """
    home_attacks_right = period == 1
    attacks_right = home_attacks_right if team_is_home else not home_attacks_right
    if attacks_right:
        return x, y
    return PITCH_LENGTH - x, PITCH_WIDTH - y
