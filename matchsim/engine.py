"""Event-level football match engine.

The engine plays a match possession by possession. Every on-ball action
(pass, carry, take-on, cross, shot) and every defensive action (pressure,
tackle, interception, block, clearance, aerial duel) is emitted as an event,
in the same spirit as professional event data.

Coordinates: every event is stored in the *acting team's* attacking frame.
x runs 0 -> 105 (own goal line -> opponent goal line), y runs 0 -> 68 (the
team's right touchline -> its left touchline). `schema.to_absolute` converts to
a fixed broadcast frame.

Outcomes come from hidden player attributes and team style, so patterns such as
"this left-back loses the ball under pressure" emerge statistically rather than
being scripted.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .config import BOX_HALF_WIDTH, BOX_X, GOAL_Y, PITCH_LENGTH as L, PITCH_WIDTH as W
from .injuries import proneness
from .universe import FORMATIONS, Club, Player, best_xi, RELATED_POSITIONS

MAX_SUBS = 5
NON_CONTACT_INJURY_RATE = 1.2e-6     # per player per second of play, before tiredness and proneness
CONTACT_INJURY_AFTER_FOUL = 0.012    # chance the fouled player is hurt (more if the foul was booked)

HALF = 45 * 60


def _sig(v: float) -> float:
    if v < -30:
        return 0.0
    if v > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-v))


def _logit(p: float) -> float:
    p = min(0.999, max(0.001, p))
    return math.log(p / (1.0 - p))


# Role in possession: (how far the player follows the ball forward, furthest x he goes,
# how often he offers himself for a pass). Calibrated so passes per 90 by position match
# real top-flight football: centre-backs and midfielders on the ball most, strikers least.
REF_BALL_X = 40.0
ROLES = {
    "GK": (0.18, 22.0, 1.1),
    "CB": (0.62, 66.0, 1.9),
    "RB": (0.95, 88.0, 1.15), "LB": (0.95, 88.0, 1.15),
    "DM": (0.72, 80.0, 1.1),
    "CM": (0.78, 92.0, 0.9),
    "AM": (0.62, 95.0, 0.8),
    "RW": (0.55, 97.0, 0.65), "LW": (0.55, 97.0, 0.65),
    "ST": (0.45, 97.0, 0.42),
}


# Shot conversion and shot choice (calibrated so a league's top scorer lands around 25-35 goals).
FIN_SLOPE = 0.006      # logit per finishing point, around xG
FIN_ELITE = 0.006      # extra per point above 88
GK_SLOPE = 0.02        # logit per shot-stopping point
SHOT_BASE = 0.27       # with the terms below centred on the average shooter, goals = xG league-wide
BOX_SHOT = 10.5        # base shot-choice weight inside the box (was 5.4)
SHOT_FIN_BOX = 0.08    # shot-choice weight per finishing point inside the box (was 0.55)
SHOT_FIN_OUT = 0.05    # ...and outside it (was 0.1)
WIDE_SHOT = 1.0        # wide forwards and No. 10s cutting inside the area edge (was 0.6)
POS_SHOT = {"ST": 0.85, "RW": 1.4, "LW": 1.4, "AM": 1.25}
HEADER_PEN = -0.35     # logit, on every header
WIDE_BOX_SHOT = 0.6    # ...and shooting from wide in the box instead of crossing (others 0.35)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


def in_box(x: float, y: float) -> bool:
    return x >= BOX_X and abs(y - GOAL_Y) <= BOX_HALF_WIDTH


def xg_model(x: float, y: float, header: bool = False) -> float:
    """Location-based expected goals (the 'public' xG model)."""
    dx = L - x
    dy = abs(y - GOAL_Y)
    dist = math.hypot(dx, dy)
    # Angle subtended by the goal mouth (7.32 m wide).
    a1 = math.atan2(GOAL_Y + 3.66 - y, max(dx, 0.1))
    a2 = math.atan2(GOAL_Y - 3.66 - y, max(dx, 0.1))
    angle = abs(a1 - a2)
    v = 0.75 - 0.24 * dist + 0.0025 * dist * dist + 0.5 * angle
    if header:
        v -= 1.0
    return round(_sig(v), 4)


@dataclass
class Slot:
    slot: str
    player: Player
    bx: float
    by: float
    on_at: float          # match seconds when the player entered
    pre_fatigue: float    # tiredness carried in (midweek games)


@dataclass
class Side:
    club: Club
    is_home: bool
    style: dict
    slots: list[Slot]
    bench: list[Player]
    sub_plan: list[float]
    rested: list[str]
    goals: int = 0
    reds: int = 0
    yellows: dict = field(default_factory=dict)
    lineup: dict = field(default_factory=dict)
    subs_used: int = 0
    injuries: list = field(default_factory=list)
    missing: list = field(default_factory=list)      # unavailable + doubtful players left out

    def outfield(self) -> list[Slot]:
        return [s for s in self.slots if s.player.position != "GK"]

    def gk(self) -> Slot:
        for s in self.slots:
            if s.player.position == "GK":
                return s
        return self.slots[0]


@dataclass
class MatchResult:
    match_id: str
    home_id: str
    away_id: str
    home_goals: int
    away_goals: int
    events: list[dict]
    lineups: list[dict]
    home_formation: str
    away_formation: str
    added_time: tuple[int, int]
    shootout: dict | None = None
    injuries: list = field(default_factory=list)


class MatchEngine:
    def __init__(self, match_id: str, home: Club, away: Club, seed: int,
                 home_fatigue: float = 0.0, away_fatigue: float = 0.0,
                 home_rotation: int = 0, away_rotation: int = 0,
                 neutral: bool = False, home_out: set | None = None, away_out: set | None = None,
                 home_doubtful: set | None = None, away_doubtful: set | None = None):
        """home_out / away_out: injured or suspended players; *_doubtful: late fitness tests
        (each one passes with probability 0.5)."""
        self.rng = random.Random(seed)
        self.match_id = match_id
        self.neutral = neutral
        self.home = self._make_side(home, True, home_rotation, home_fatigue, home_out or set(), home_doubtful or set())
        self.away = self._make_side(away, False, away_rotation, away_fatigue, away_out or set(), away_doubtful or set())
        self._last_injury_check = 0.0
        self.events: list[dict] = []
        self.eid = 0
        self.poss_id = 0
        self.period = 1
        self.t = 0.0
        self.added = [0, 0]
        self._p1_len = float(HALF)
        self._added_decided = False
        self.stoppages = 0

    # ------------------------------------------------------------------ setup
    def _make_side(self, club: Club, is_home: bool, rotation: int, fatigue: float,
                   out: set, doubtful: set) -> Side:
        rng = self.rng
        missing = set(out)
        for pid in sorted(doubtful):
            if rng.random() < 0.5:             # failed the late fitness test
                missing.add(pid)
        first_choice = best_xi(club, exclude=missing)
        xi = first_choice
        rested: list[str] = []
        if rotation > 0:
            outfield = [p for _s, p in xi if p.position != "GK"]
            # Rest the most tired-prone players (low stamina) with some randomness.
            outfield.sort(key=lambda p: p.attrs["stamina"] + rng.gauss(0, 8))
            rested = [p.player_id for p in outfield[:rotation]]
            xi = best_xi(club, exclude=missing | set(rested))
        coords = {slot: (x, y) for slot, _pos, x, y in FORMATIONS[club.formation]}
        slots = []
        first_ids = {q.player_id for _s, q in first_choice}
        for slot, p in xi:
            fresh = rotation > 0 and p.player_id not in first_ids
            bx, by = coords[slot]
            slots.append(Slot(slot, p, bx, by, 0.0, 0.0 if fresh else fatigue))
        used = {s.player.player_id for s in slots}
        bench_pool = sorted([p for p in club.squad if p.player_id not in used and p.player_id not in missing],
                            key=lambda p: -p.overall)
        bench_gk = [p for p in bench_pool if p.position == "GK"][:1]
        bench = bench_gk + [p for p in bench_pool if p.position != "GK"][:8]
        n_subs = rng.choices([3, 4, 5], weights=[3, 4, 3])[0]
        plan = sorted(rng.uniform(55, 88) for _ in range(n_subs))
        side = Side(club, is_home, club.style(), slots, bench, plan, rested)
        side.missing = sorted(missing)
        for s in slots:
            side.lineup[s.player.player_id] = {
                "player_id": s.player.player_id, "slot": s.slot, "position": s.player.position,
                "started": True, "minute_on": 0, "minute_off": None, "yellow": 0, "red": 0}
        return side

    def other(self, side: Side) -> Side:
        return self.away if side is self.home else self.home

    # ------------------------------------------------------------------ clock
    def match_seconds(self) -> float:
        return (0.0 if self.period == 1 else HALF) + self.t

    def _elapsed(self) -> float:
        """Seconds of play since kick-off, monotonic across halves."""
        return self.t if self.period == 1 else self._p1_len + self.t

    def _tick(self, secs: float) -> None:
        self.t += secs

    # ------------------------------------------------------------------ events
    def _emit(self, side: Side, etype: str, player: Player | None, x: float, y: float,
              frame: Side, **kw) -> dict:
        """Record an event. x, y are given in `frame`'s attacking frame and
        stored in the acting side's frame."""
        if frame is not side:
            x, y = L - x, W - y
        total = self.match_seconds()
        elapsed = self._elapsed()
        self.eid += 1
        ev = {
            "match_id": self.match_id,
            "event_id": self.eid,
            "possession_id": self.poss_id,
            "period": self.period,
            "minute": int(total // 60),
            "second": int(total % 60),
            "clock_s": round(elapsed, 1),
            "team_id": side.club.club_id,
            "player_id": player.player_id if player else None,
            "type": etype,
            "outcome": kw.pop("outcome", None),
            "x": round(_clamp(x, 0, L), 1),
            "y": round(_clamp(y, 0, W), 1),
            "end_x": None,
            "end_y": None,
            "receiver_id": None,
            "under_pressure": kw.pop("under_pressure", False),
            "pass_type": None,
            "pass_length": None,
            "difficulty": None,
            "body_part": None,
            "xg": None,
            "ball_speed_kmh": None,
            "set_piece": None,
            "play_pattern": self._pattern,
            "set_piece_phase": (self._pattern in ("from_corner", "from_free_kick", "penalty", "from_throw_in")
                                and total - self._poss_start <= 12.0),
            "related_player_id": None,
            "card": None,
            "score_home": self.home.goals,
            "score_away": self.away.goals,
        }
        end = kw.pop("end", None)
        if end is not None:
            ex, ey = end
            if frame is not side:
                ex, ey = L - ex, W - ey
            ev["end_x"] = round(_clamp(ex, 0, L), 1)
            ev["end_y"] = round(_clamp(ey, 0, W), 1)
        rel = kw.pop("related", None)
        if rel is not None:
            ev["related_player_id"] = rel.player_id
        rec = kw.pop("receiver", None)
        if rec is not None:
            ev["receiver_id"] = rec.player_id
        ev.update(kw)
        self.events.append(ev)
        return ev

    # ------------------------------------------------------------------ helpers
    def _fatigue(self, side: Side, slot: Slot) -> float:
        played = (self.match_seconds() - slot.on_at) / 60.0
        stamina = slot.player.attrs["stamina"]
        fit = side.style.get("fitness", 0.5)
        f = (played / 90.0 * (1.15 - 0.55 * stamina / 100.0) * (1.35 - 0.7 * fit)
             * (1.0 + 0.3 * (side.style.get("press_intensity", 0.5) - 0.5)))
        return f + slot.pre_fatigue

    def _fat_pen(self, side: Side, slot: Slot) -> float:
        return 0.9 * max(0.0, self._fatigue(side, slot) - 0.5)

    def _in_transition(self) -> bool:
        return (self._poss_kind == "turnover" and self._poss_start_x < 52.5
                and self.match_seconds() - self._poss_start <= 9.0)

    def _def_tired(self, side: Side) -> float:
        """How tired a defending side is (0 = fresh). Opponents benefit."""
        if not side.slots:
            return 0.0
        avg = sum(self._fatigue(side, s) for s in side.slots) / len(side.slots)
        return max(0.0, avg - 0.45)

    def _aggr(self, side: Side) -> float:
        """Game-state attacking intent: >0 chasing the game, <0 protecting a lead."""
        diff = side.goals - self.other(side).goals
        mins = self.match_seconds() / 60.0
        if diff == 0:
            # Level late on: both sides go for the win, the home side more.
            late = _clamp((mins - 65.0) / 25.0, 0.0, 1.0)
            return (0.25 if side.is_home and not self.neutral else 0.17) * late
        w = min(1.0, (mins / 90.0)) ** 1.5
        return _clamp(-0.15 * diff * w, -0.5, 0.5)

    def _side_bonus(self, side: Side) -> float:
        bonus = 0.0
        if not self.neutral:
            boost = self.home.style.get("home_boost", 0.5) - 0.5
            if side.is_home:
                bonus += 0.045 + 0.3 * boost
            else:
                bonus -= 0.045 + 0.2 * boost
        bonus -= 0.3 * side.reds
        bonus += 0.12 * self.other(side).reds
        return bonus

    def _pos_att(self, side: Side, s: Slot, bx_ball: float, by_ball: float) -> tuple[float, float]:
        """Where a player stands when his team has the ball.

        Each role follows the ball by a different amount: full-backs push on, centre-backs
        hold the halfway line, strikers stay on the last line, so the team keeps a
        realistic 35-45 m block instead of everyone sliding together."""
        pos = s.player.position
        follow, cap, _avail = ROLES.get(pos, ROLES["CM"])
        lh = (side.style.get("line_height", 0.5) - 0.5) * 10
        x = s.bx + follow * (bx_ball - REF_BALL_X) + (lh if pos in ("GK", "CB", "RB", "LB", "DM") else 0.5 * lh)
        if pos == "GK":
            return _clamp(x, 1, cap), 34.0
        by = s.by
        if pos in ("RW", "LW") and bx_ball > 66:
            by += (GOAL_Y - by) * 0.35          # wide forwards come inside; full-backs give the width
        return _clamp(x, 2, cap), _clamp(by + (by_ball - 34) * 0.25, 1, 67)

    def _pos_def(self, dfn: Side, s: Slot, x: float, y: float) -> tuple[float, float]:
        """Defender position, returned in the attacking frame.

        The back line sits 12-20 m behind the ball (higher for high-line teams),
        and the team stays compact (about 35 m from back line to forwards)."""
        bxd = L - x                      # ball position in the defending team's own frame
        lh = dfn.style.get("line_height", 0.5)
        line = _clamp(bxd - 14 + (lh - 0.5) * 14, 6, 48 + 10 * (lh - 0.5))
        if s.player.position == "GK":
            px, py = 4.0 + max(0.0, line - 30) * 0.3, 34.0
        else:
            px = _clamp(line + (s.bx - 20) * 0.7, 3, 100)
            py = _clamp(s.by * 0.8 + (W - y) * 0.2, 1, 67)
        return L - px, W - py

    def _pick_receiver(self, att: Side, tx: float, ty: float, exclude: Player,
                       ball_x: float, ball_y: float) -> Slot:
        rng = self.rng
        cands, weights = [], []
        for s in att.slots:
            if s.player is exclude:
                continue
            if s.player.position == "GK" and tx > 30:
                continue
            px, py = self._pos_att(att, s, ball_x, ball_y)
            d2 = (px - tx) ** 2 + (py - ty) ** 2
            cands.append(s)
            avail = ROLES.get(s.player.position, ROLES["CM"])[2]
            weights.append(avail * math.exp(-d2 / 288.0) + 1e-4)
        return rng.choices(cands, weights=weights)[0]

    def _pick_defender(self, dfn: Side, x: float, y: float, allow_gk: bool = False) -> Slot:
        rng = self.rng
        cands, weights = [], []
        for s in dfn.slots:
            if s.player.position == "GK" and not allow_gk:
                continue
            px, py = self._pos_def(dfn, s, x, y)
            d2 = (px - x) ** 2 + (py - y) ** 2
            cands.append(s)
            weights.append(math.exp(-d2 / 162.0) + 1e-4)
        return rng.choices(cands, weights=weights)[0]

    def _slot_of(self, side: Side, player: Player) -> Slot:
        for s in side.slots:
            if s.player is player:
                return s
        return side.slots[0]

    def _lane_target_y(self, att: Side, y: float, spread: float) -> float:
        """Pull target y toward the team's preferred flank."""
        rng = self.rng
        lb = att.style.get("left_bias", 0.45)
        rb = att.style.get("right_bias", 0.45)
        r = rng.random()
        p_left = _clamp(0.18 + (lb - 0.45) * 0.9, 0.03, 0.6)
        p_right = _clamp(0.18 + (rb - 0.45) * 0.9, 0.03, 0.6)
        if r < p_left:
            return _clamp(rng.gauss(58, 6), 2, 66)
        if r < p_left + p_right:
            return _clamp(rng.gauss(10, 6), 2, 66)
        return _clamp(y + rng.gauss(0, spread), 2, 66)

    # ------------------------------------------------------------------ main loop
    def simulate(self) -> MatchResult:
        self._pattern = "regular"
        self._poss_start = 0.0
        self._poss_kind = "kick_off"
        self._poss_start_x = 52.5
        for period in (1, 2):
            self.period = period
            self.t = 0.0
            self._added_decided = False
            self.stoppages = 0
            kicker = self.home if period == 1 else self.away
            self._emit(self.home, "period_start", None, 52.5, 34, self.home)
            restart = ("kick_off", kicker, 52.5, 34.0, None)
            while True:
                if self.t >= HALF and not self._added_decided:
                    self._decide_added()
                if self._added_decided and self.t >= HALF + self.added[period - 1] * 60:
                    break
                self._maybe_subs()
                restart = self._possession(*restart)
                if restart is None:
                    break
            self._emit(self.home, "period_end", None, 52.5, 34, self.home)
            if period == 1:
                self._p1_len = self.t
        lineups = []
        for side in (self.home, self.away):
            for rec in side.lineup.values():
                off = rec["minute_off"] if rec["minute_off"] is not None else 90 + self.added[1]
                lineups.append({"match_id": self.match_id, "team_id": side.club.club_id,
                                **rec, "minute_off": off,
                                "minutes": max(0, off - rec["minute_on"])})
            for pid in side.rested:
                lineups.append({"match_id": self.match_id, "team_id": side.club.club_id,
                                "player_id": pid, "slot": None, "position": None,
                                "started": False, "minute_on": None, "minute_off": None,
                                "yellow": 0, "red": 0, "minutes": 0, "rested": True})
        return MatchResult(self.match_id, self.home.club.club_id, self.away.club.club_id,
                           self.home.goals, self.away.goals, self.events, lineups,
                           self.home.club.formation, self.away.club.formation,
                           (self.added[0], self.added[1]),
                           injuries=self.home.injuries + self.away.injuries)

    def _decide_added(self) -> None:
        evs = [e for e in self.events if e["period"] == self.period]
        goals = sum(1 for e in evs if e["outcome"] == "goal")
        subs = sum(1 for e in evs if e["type"] == "substitution")
        cards = sum(1 for e in evs if e["type"] == "card")
        pens = sum(1 for e in evs if e["set_piece"] == "penalty")
        injuries = sum(1 for e in evs if e["type"] == "injury")
        extra = (0.8 * goals + 0.45 * subs + 0.35 * cards + 1.0 * pens + 1.0 * injuries
                 + self.rng.uniform(0.3, 2.4))
        if self.period == 1:
            self.added[0] = int(min(6, 1 + extra))
        else:
            self.added[1] = int(min(10, 3 + extra))
        self._added_decided = True

    def _time_up(self) -> bool:
        return self._added_decided and self.t >= HALF + self.added[self.period - 1] * 60

    # ------------------------------------------------------------------ substitutions
    def _maybe_subs(self) -> None:
        mins = self.match_seconds() / 60.0
        for side in (self.home, self.away):
            while side.sub_plan and mins >= side.sub_plan[0] and side.bench and side.subs_used < MAX_SUBS:
                side.sub_plan.pop(0)
                self._substitute(side)
        self._maybe_injury()

    # ------------------------------------------------------------------ injuries
    def _maybe_injury(self) -> None:
        """Muscle injuries: a small hazard per player, higher when tired or injury-prone."""
        now = self._elapsed()
        dt_s = now - self._last_injury_check
        self._last_injury_check = now
        if dt_s <= 0:
            return
        for side in (self.home, self.away):
            for s in list(side.slots):
                hurt = {i["player_id"] for i in side.injuries}
                if s.player.player_id in hurt:
                    continue
                rate = NON_CONTACT_INJURY_RATE * (1 + 2.5 * self._fatigue(side, s)) * proneness(s.player)
                if self.rng.random() < rate * dt_s:
                    self._injure(side, s.player, "non_contact", 52.5, 34.0, side)

    def _injure(self, side: Side, player: Player, cause: str, x: float, y: float, frame: Side) -> None:
        if any(i["player_id"] == player.player_id for i in side.injuries):
            return
        rng = self.rng
        can_sub = bool(side.bench) and side.subs_used < MAX_SUBS
        if player.position == "GK":
            can_sub = can_sub and any(p.position == "GK" for p in side.bench)
        outcome = "off" if can_sub and rng.random() < 0.72 else "played_on"
        self._emit(side, "injury", player, x, y, frame, outcome=outcome)
        side.injuries.append({"player_id": player.player_id, "team_id": side.club.club_id, "cause": cause,
                              "minute": int(self.match_seconds() // 60), "outcome": outcome})
        self._tick(rng.uniform(40, 110))      # treatment on the pitch
        self.stoppages += 1
        if outcome == "off":
            if side.sub_plan:
                side.sub_plan.pop()          # the forced change uses up one of the planned ones
            self._substitute(side, forced=player, reason="injury")
        else:
            for s in side.slots:
                if s.player is player:
                    s.pre_fatigue += 0.12     # carrying a knock

    def _substitute(self, side: Side, forced: Player | None = None, reason: str = "off") -> None:
        rng = self.rng
        outfield = [s for s in side.slots if s.player.position != "GK"]
        if forced is not None:
            off_slot = next((s for s in side.slots if s.player is forced), None)
            if off_slot is None:
                return
        else:
            if not outfield:
                return
            # Take off the most tired, with some noise.
            outfield.sort(key=lambda s: -(self._fatigue(side, s) + rng.gauss(0, 0.08)))
            off_slot = outfield[0]
        chasing = side.goals < self.other(side).goals
        pos = off_slot.player.position
        pool = [p for p in side.bench if p.position == pos]
        if pos == "GK":
            pool = pool or [p for p in side.bench if p.position == "GK"]
        elif forced is None and chasing and pos in ("CB", "DM", "RB", "LB") and self.match_seconds() > 70 * 60:
            pool = [p for p in side.bench if p.position in ("ST", "AM", "RW", "LW")] or pool
        if not pool and pos != "GK":
            pool = [p for p in side.bench if p.position in RELATED_POSITIONS.get(pos, [])]
        if not pool and pos != "GK":
            pool = [p for p in side.bench if p.position != "GK"]
        if not pool:
            return
        on = max(pool, key=lambda p: p.overall)
        side.bench.remove(on)
        side.subs_used += 1
        minute = int(self.match_seconds() // 60)
        self._emit(side, "substitution", off_slot.player, 52.5, 34, side,
                   related=on, outcome=reason)
        side.lineup[off_slot.player.player_id]["minute_off"] = minute
        side.lineup[on.player_id] = {"player_id": on.player_id, "slot": off_slot.slot,
                                     "position": on.position, "started": False,
                                     "minute_on": minute, "minute_off": None,
                                     "yellow": 0, "red": 0}
        off_slot.player = on
        off_slot.on_at = self.match_seconds()
        off_slot.pre_fatigue = 0.0
        self._tick(rng.uniform(20, 35))
        self.stoppages += 1

    # ------------------------------------------------------------------ possession
    PATTERNS = {"kick_off": "from_kick_off", "throw_in": "from_throw_in",
                "goal_kick": "from_goal_kick", "corner": "from_corner",
                "free_kick": "from_free_kick", "penalty": "penalty",
                "turnover": "regular", "gk_hold": "from_keeper"}

    def _possession(self, kind: str, att: Side, x: float, y: float,
                    player: Player | None):
        rng = self.rng
        dfn = self.other(att)
        self.poss_id += 1
        self._pattern = self.PATTERNS[kind]
        self._poss_start = self.match_seconds()
        self._poss_kind = kind
        self._poss_start_x = x
        start_idx = len(self.events)
        start_t = self._elapsed()
        start_x = x

        if kind == "penalty":
            return self._penalty(att, dfn)
        if kind == "corner":
            res = self._corner(att, dfn, y)
            if res[0] == "restart":
                return res[1]
            _, carrier, x, y = res
        elif kind == "free_kick":
            res = self._free_kick(att, dfn, x, y, player)
            if res[0] == "restart":
                return res[1]
            _, carrier, x, y = res
        elif kind == "goal_kick":
            res = self._goal_kick(att, dfn)
            if res[0] == "restart":
                return res[1]
            _, carrier, x, y = res
        elif kind == "kick_off":
            st = [s for s in att.slots if s.player.position in ("ST", "AM")] or att.outfield()
            taker = st[0].player
            mid = [s for s in att.slots if s.player.position in ("CM", "DM")] or att.outfield()
            rec = rng.choice(mid).player
            self._emit(att, "pass", taker, 52.5, 34, att, outcome="complete",
                       end=(44.0, 34 + rng.gauss(0, 6)), receiver=rec, pass_type="short",
                       pass_length=9.0, difficulty=0.02, set_piece="kick_off",
                       ball_speed_kmh=30.0)
            self._tick(2.0)
            carrier, x, y = rec, 44.0, 34.0
        elif kind == "throw_in":
            carrier = player or self._nearest_player(att, x, y)
            res = self._throw_in(att, dfn, carrier, x, y)
            if res[0] == "restart":
                return res[1]
            _, carrier, x, y = res
        else:  # turnover / gk_hold
            carrier = player or self._nearest_player(att, x, y)

        n_pass = 0
        while True:
            if self._time_up() and x < 70:
                self._tag_counter(start_idx, start_t, start_x, n_pass, kind)
                return None
            if self.t >= HALF and not self._added_decided:
                self._decide_added()
            res = self._action(att, dfn, carrier, x, y)
            if res[0] == "continue":
                if res[4]:
                    n_pass += 1
                carrier, x, y = res[1], res[2], res[3]
                continue
            self._tag_counter(start_idx, start_t, start_x, n_pass, kind)
            return res[1]

    def _tag_counter(self, start_idx: int, start_t: float, start_x: float, n_pass: int,
                     kind: str) -> None:
        if kind != "turnover" or start_x > 52.5:
            return
        evs = self.events[start_idx:]
        for ev in evs:
            if ev["type"] == "shot" and ev["clock_s"] - start_t <= 15 and n_pass <= 5:
                for e in evs:
                    if e["play_pattern"] == "regular":
                        e["play_pattern"] = "counter"
                return

    def _nearest_player(self, side: Side, x: float, y: float) -> Player:
        best, bd = None, 1e9
        for s in side.slots:
            if s.player.position == "GK" and x > 25:
                continue
            px, py = self._pos_att(side, s, x, y)
            d = (px - x) ** 2 + (py - y) ** 2
            if d < bd:
                best, bd = s, d
        return best.player if best else side.slots[0].player

    # ------------------------------------------------------------------ one action
    def _action(self, att: Side, dfn: Side, carrier: Player, x: float, y: float):
        rng = self.rng
        st = att.style
        ds = dfn.style
        cslot = self._slot_of(att, carrier)
        a = carrier.attrs
        aggr_att = self._aggr(att)
        aggr_def = self._aggr(dfn)
        is_gk = carrier.position == "GK"

        # --- pressure
        if x < 35:
            base = 0.20 * (1.0 + 0.9 * (ds.get("press_height", 0.5) - 0.5))
        elif x < 70:
            base = 0.26
        elif in_box(x, y):
            base = 0.40
        else:
            base = 0.32
        def_fat = sum(self._fatigue(dfn, s) for s in dfn.slots) / 11.0
        press = base * (0.55 + 0.9 * ds.get("press_intensity", 0.5)) * (1 + 0.5 * aggr_def)
        press *= (1.0 - 0.45 * max(0.0, def_fat - 0.4)) * (1 - 0.15 * dfn.reds)
        if is_gk:
            press *= 0.5
        up = False
        if rng.random() < press:
            up = True
            pslot = self._pick_defender(dfn, x, y)
            presser = pslot.player
            self._emit(dfn, "pressure", presser, x, y, att, related=carrier)
            self._tick(0.5)
            disc = presser.attrs["discipline"] * 0.6 + 100 * dfn.style.get("discipline", 0.5) * 0.4
            if dfn.yellows.get(presser.player_id, 0):
                disc += 35  # booked players hold back
            p_disp = (0.085 * math.exp(-0.032 * (a["press_resistance"] - 62))
                      * math.exp(0.02 * (presser.attrs["tackling"] - 62))
                      * (1 + self._fat_pen(att, cslot)) * (1.15 if x < 35 else 1.0))
            if is_gk:
                p_disp *= 0.25
            p_disp *= 1.0 + 0.6 * (st.get("directness", 0.5) - 0.5)
            if rng.random() < p_disp:
                if rng.random() < 0.19 * math.exp(-0.03 * (disc - 55)) * (0.13 if in_box(x, y) else 1.0):
                    return ("restart", self._foul(dfn, att, presser, carrier, x, y, up=True))
                self._emit(att, "dispossessed", carrier, x, y, att, related=presser,
                           under_pressure=True)
                self._emit(dfn, "tackle", presser, x, y, att, outcome="won", related=carrier)
                self._tick(rng.uniform(0.5, 1.5))
                return ("restart", ("turnover", dfn, L - x, W - y, presser))
            if rng.random() < 0.066 * math.exp(-0.03 * (disc - 55)) * (0.1 if in_box(x, y) else 1.0):
                return ("restart", self._foul(dfn, att, presser, carrier, x, y, up=True))

        # --- transition: just won the ball in our own half?
        transition = (self._poss_kind == "turnover" and self._poss_start_x < 52.5
                      and self.match_seconds() - self._poss_start <= 9.0)
        # --- choose an action
        box = in_box(x, y)
        wide = abs(y - GOAL_Y) > 14
        directness = st.get("directness", 0.5)
        crossing = st.get("crossing", 0.5)
        shoot = st.get("shot_propensity", 0.5)
        pos = carrier.position
        w: dict[str, float] = {}
        if x < 35:
            w["short"] = 62
            w["long"] = 7 + 20 * directness + (10 if is_gk else 0) + (8 if up else 0) - 6 * aggr_att
            w["carry"] = 0 if is_gk else 16
            w["take_on"] = 0 if is_gk or pos == "CB" else 0.4
            w["clear"] = (9 if up else 1.2) if pos in ("CB", "RB", "LB", "DM", "GK") else 0
            w["back"] = 0 if is_gk else 8 - 6 * aggr_att
            w["recycle"] = (20 + 16 * (0.5 - directness) - 6 * aggr_att) * (0.6 if up else 1.0)
        elif x < 70:
            w["short"] = 58
            w["long"] = 3 + 9 * directness
            w["through"] = 0.25 + 0.5 * directness + 0.6 * max(0.0, aggr_att)
            w["switch"] = 3.5 if not up else 1
            w["carry"] = 17
            w["take_on"] = max(0.2, 0.9 + 0.035 * (a["dribbling"] - 60))
            w["back"] = 13 - 8 * aggr_att + 3 * up
            if x < 55:
                w["recycle"] = max(1.0, 11 + 12 * (0.5 - directness) - 6 * aggr_att)
            if x > 62 and abs(y - GOAL_Y) < 15:
                w["shot"] = 0.5 + 1.0 * shoot
        elif not box:
            w["short"] = 46
            w["through"] = 0.9 + 1.1 * directness
            w["cross"] = (8 + 12 * crossing + 4 * aggr_att) if wide else 0.5
            w["carry"] = 9
            w["take_on"] = max(0.4, 2.3 + 0.06 * (a["dribbling"] - 60))
            w["back"] = 10 - 6 * aggr_att
            if x > 76 and not wide:
                w["shot"] = max(0.8, 6.4 + 5.0 * shoot + SHOT_FIN_OUT * (a["finishing"] - 60) + 3 * aggr_att)
            elif x > 76 and pos in ("RW", "LW", "AM") and abs(y - GOAL_Y) < 25:
                w["shot"] = max(0.5, WIDE_SHOT * (5.6 + 5.0 * shoot + SHOT_FIN_OUT * (a["finishing"] - 60) + 3 * aggr_att))
        else:
            w["shot"] = max(1.5, BOX_SHOT + 6.5 * shoot + SHOT_FIN_BOX * (a["finishing"] - 60) + 4 * aggr_att)
            if abs(y - GOAL_Y) > 12:
                w["shot"] *= WIDE_BOX_SHOT if pos in ("RW", "LW", "AM") else 0.35
                w["cross"] = 12
            w["short"] = 36
            w["take_on"] = max(0.4, 3.3 + 0.08 * (a["dribbling"] - 60))
            w["carry"] = 3
            w["back"] = 12
        if pos in ("CB", "GK"):
            w["take_on"] = w.get("take_on", 0) * 0.3
            if "shot" in w and not box:
                w["shot"] *= 0.25
        elif pos in ("RW", "LW", "AM"):
            w["take_on"] = w.get("take_on", 0) * 1.6
        if "shot" in w:
            # Goals are shared: inside forwards and No. 10s shoot more, the striker a little less.
            w["shot"] *= POS_SHOT.get(pos, 1.0)
        if up:
            w["carry"] = w.get("carry", 0) * 0.6
        if transition:
            cf = st.get("counter_focus", 0.5)
            w["through"] = w.get("through", 0) + 3 * cf
            w["long"] = w.get("long", 0) * (1 + cf)
            w["carry"] = w.get("carry", 0) * (1 + 1.2 * cf)
            w["back"] = w.get("back", 0) * (1 - 0.7 * cf)
        acts = [k for k, v in w.items() if v > 0]
        choice = rng.choices(acts, weights=[w[k] for k in acts])[0]

        if choice == "shot":
            if box:
                x = _clamp(x - rng.uniform(0, 2.5), BOX_X - 1, L - 3)
            return ("restart", self._shot(att, dfn, carrier, x, y, up, header=False))
        if choice == "cross":
            return self._cross(att, dfn, carrier, x, y, up)
        if choice == "clear":
            return self._clearance(att, dfn, carrier, x, y, up)
        if choice in ("carry", "take_on"):
            return self._carry(att, dfn, carrier, cslot, x, y, up, take_on=(choice == "take_on"))
        return self._pass(att, dfn, carrier, cslot, x, y, up, choice)

    # ------------------------------------------------------------------ passing
    def _pass(self, att: Side, dfn: Side, carrier: Player, cslot: Slot, x: float, y: float,
              up: bool, kind: str):
        rng = self.rng
        st = att.style
        a = carrier.attrs
        aggr = self._aggr(att)
        directness = st.get("directness", 0.5)
        if kind == "short":
            # Build-up passes in the own third go sideways more; further up they go forward.
            fwd = (0.5 + 4 * directness + 3 * aggr) if x < 35 else (3.0 + 5 * directness + 4 * aggr)
            dx = rng.gauss(fwd, 8.5)
            dy = rng.gauss(0, 10)
            if x > 40 and rng.random() < 0.35:
                dy = self._lane_target_y(att, y, 10) - y
            length = math.hypot(dx, dy)
            if length < 5:
                s = 5 / max(length, 0.1)
                dx, dy = dx * s, dy * s
            if length > 26:
                s = 26 / length
                dx, dy = dx * s, dy * s
            ptype = "short" if math.hypot(dx, dy) < 18 else "medium"
        elif kind == "back":
            dx = -abs(rng.gauss(12, 6)) if x >= 35 else -abs(rng.gauss(9, 5))
            dy = rng.gauss(0, 9)
            ptype = "back"
        elif kind == "long":
            dx = rng.gauss(30, 8)
            ty = self._lane_target_y(att, y, 15)
            dy = ty - y
            ptype = "long"
        elif kind == "through":
            dx = rng.gauss(17, 5)
            dy = rng.gauss(0, 6)
            ptype = "through"
        elif kind == "recycle":
            # Keep the ball: find a defender or the keeper and play it to him.
            px, py = self._recycle_target(att, carrier, x, y, up)
            dx, dy = px - x + rng.gauss(0, 2), py - y + rng.gauss(0, 2)
            ln = math.hypot(dx, dy)
            ptype = "back" if dx < -4 else ("short" if ln < 18 else "medium")
        else:  # switch
            dx = rng.gauss(4, 6)
            dy = (58 if y < 34 else 10) - y + rng.gauss(0, 4)
            ptype = "switch"
        tx = _clamp(x + dx, 1, 104)
        if ptype in ("short", "medium", "back") and tx > 99.5:
            tx = 99.5 - rng.uniform(0, 3)
        ty = y + dy
        length = math.hypot(tx - x, ty - y)

        # Offside on balls in behind.
        if ptype in ("through", "long") and tx > 80 and rng.random() < (
                0.08 + 0.12 * dfn.style.get("line_height", 0.5)) * (1.0 if ptype == "through" else 0.9):
            rec = self._pick_receiver(att, tx, _clamp(ty, 2, 66), carrier, x, y)
            self._emit(att, "pass", carrier, x, y, att, outcome="offside", end=(tx, _clamp(ty, 0, W)),
                       receiver=rec.player, pass_type=ptype, pass_length=round(length, 1),
                       under_pressure=up, difficulty=None, ball_speed_kmh=self._ball_speed(length))
            self._emit(att, "offside", rec.player, tx, _clamp(ty, 0, W), att)
            self._tick(rng.uniform(15, 28))
            self.stoppages += 1
            return ("restart", ("free_kick", dfn, L - tx, W - _clamp(ty, 0, W), None))

        # Out of play by design (overhit)
        out_side = ty < 0 or ty > W
        ty_c = _clamp(ty, 0.5, W - 0.5)

        base = {"short": 3.15, "medium": 2.45, "back": 3.9, "long": 0.85, "through": 0.1,
                "switch": 1.15}[ptype]
        v = base + 0.06 * (a["passing"] - 65)
        if ptype in ("through", "long", "switch"):
            v += 0.025 * (a["vision"] - 65)
        v -= 0.045 * max(0.0, length - 12)
        v -= 0.75 if up else 0.0
        if ptype in ("short", "medium", "back"):
            v += 1.0 * (0.5 - directness)
        if self._in_transition() and ptype in ("through", "long", "medium"):
            v += 0.5 * att.style.get("counter_focus", 0.5)
        if in_box(tx, ty):
            v -= 1.3 + (1.2 if tx > 96 and abs(ty - GOAL_Y) < 10 else 0.0)
        elif tx > 75:
            v -= 0.3
        dslot = self._pick_defender(dfn, tx, ty_c)
        dpl = dslot.player
        v -= 0.02 * (dpl.attrs["positioning"] - 62)
        v -= 0.25 * (dfn.style.get("press_intensity", 0.5) - 0.5)
        if out_side:
            v -= 2.5
        # Public pass-difficulty rating uses context only (an average passer),
        # so 'completion over expected' reveals passing skill.
        skill = 0.06 * (a["passing"] - 65)
        if ptype in ("through", "long", "switch"):
            skill += 0.025 * (a["vision"] - 65)
        difficulty = round(1 - _sig(v - skill), 3)
        v += self._side_bonus(att) - self._fat_pen(att, cslot) + 0.9 * self._def_tired(dfn)
        p = _sig(v)
        receiver = self._pick_receiver(att, tx, ty_c, carrier, x, y)

        # Long balls are contested in the air.
        duel_won = None
        if ptype == "long" and not out_side and rng.random() < 0.4:
            duel_won = self._aerial(att, dfn, receiver.player, dpl, tx, ty_c)
            if not duel_won:
                p *= 0.55
        success = rng.random() < p
        dur = 1.0 + length / 14.0 + rng.uniform(0.4, 1.8) * (1.25 - 0.5 * att.style.get("tempo", 0.5))
        speed = self._ball_speed(length)
        if success:
            self._emit(att, "pass", carrier, x, y, att, outcome="complete", end=(tx, ty_c),
                       receiver=receiver.player, pass_type=ptype, pass_length=round(length, 1),
                       under_pressure=up, difficulty=difficulty, ball_speed_kmh=speed)
            self._tick(dur)
            nx = tx + rng.gauss(0, 1.0)
            return ("continue", receiver.player, _clamp(nx, 1, 104), ty_c, True)

        # Failed pass
        if out_side:
            self._emit(att, "pass", carrier, x, y, att, outcome="out", end=(tx, _clamp(ty, 0, W)),
                       receiver=receiver.player, pass_type=ptype, pass_length=round(length, 1),
                       under_pressure=up, difficulty=difficulty, ball_speed_kmh=speed)
            self._tick(dur + rng.uniform(10, 22))
            self.stoppages += 1
            return ("restart", ("throw_in", dfn, L - tx, (W - 0.5) if ty < 0 else 0.5, None))
        if tx >= 101.5 and rng.random() < 0.75:
            self._emit(att, "pass", carrier, x, y, att, outcome="out", end=(L, ty_c),
                       receiver=receiver.player, pass_type=ptype, pass_length=round(length, 1),
                       under_pressure=up, difficulty=difficulty, ball_speed_kmh=speed)
            self._tick(dur + rng.uniform(15, 30))
            self.stoppages += 1
            if rng.random() < 0.45:
                return ("restart", ("corner", att, 104.5, 0.5 if ty_c < GOAL_Y else W - 0.5, None))
            return ("restart", ("goal_kick", dfn, 5.5, 34, None))
        self._emit(att, "pass", carrier, x, y, att, outcome="incomplete", end=(tx, ty_c),
                   receiver=receiver.player, pass_type=ptype, pass_length=round(length, 1),
                   under_pressure=up, difficulty=difficulty, ball_speed_kmh=speed)
        self._tick(dur)
        r = rng.random()
        if r < 0.3:
            self._emit(dfn, "interception", dpl, tx, ty_c, att, outcome="won", related=carrier)
            return ("restart", ("turnover", dfn, L - tx, W - ty_c, dpl))
        if r < 0.72:
            self._emit(dfn, "ball_recovery", dpl, tx, ty_c, att)
            return ("restart", ("turnover", dfn, L - tx, W - ty_c, dpl))
        if r < 0.86:
            self._emit(dfn, "block", dpl, (x + tx) / 2, (y + ty_c) / 2, att, related=carrier)
            if rng.random() < 0.55:
                return ("restart", ("turnover", dfn, L - (x + tx) / 2, W - (y + ty_c) / 2, dpl))
            return ("continue", carrier, x, y, False)
        # Loose ball recovered by whoever is closer.
        if rng.random() < 0.6:
            self._emit(dfn, "ball_recovery", dpl, tx, ty_c, att)
            return ("restart", ("turnover", dfn, L - tx, W - ty_c, dpl))
        self._emit(att, "ball_recovery", receiver.player, tx, ty_c, att)
        return ("continue", receiver.player, tx, ty_c, False)

    def _recycle_target(self, att: Side, carrier: Player, x: float, y: float, up: bool) -> tuple[float, float]:
        """Position of a team-mate in the back line (or the keeper) to keep possession with."""
        opts, wts = [], []
        for s in att.slots:
            pos = s.player.position
            if s.player is carrier or pos not in ("GK", "CB", "RB", "LB", "DM"):
                continue
            if pos == "GK" and x > 45:
                continue
            px, py = self._pos_att(att, s, x, y)
            if px > x + 6:
                continue
            d = math.hypot(px - x, py - y)
            w = {"GK": 0.9 if up else 0.4, "CB": 1.5, "DM": 0.9}.get(pos, 0.8)
            opts.append((px, py))
            wts.append(w * math.exp(-max(0.0, d - 10) / 14))
        if not opts:
            return x - 8, y
        return self.rng.choices(opts, weights=wts)[0]

    def _cut_inside(self, carrier: Player, x: float, y: float) -> float:
        """Wide attackers in the final third often drive inside onto their stronger foot."""
        if carrier.position not in ("RW", "LW", "AM") or x < 66 or abs(y - GOAL_Y) < 10:
            return 0.0
        if self.rng.random() > 0.55:
            return 0.0
        return math.copysign(self.rng.uniform(4, 9), GOAL_Y - y)

    def _ball_speed(self, length: float) -> float:
        return round(_clamp(22 + 1.35 * length + self.rng.gauss(0, 6), 15, 110), 1)

    # ------------------------------------------------------------------ carrying / dribbling
    def _carry(self, att: Side, dfn: Side, carrier: Player, cslot: Slot, x: float, y: float,
               up: bool, take_on: bool):
        rng = self.rng
        aggr = self._aggr(att)
        if take_on:
            dslot = self._pick_defender(dfn, x, y)
            d = dslot.player
            a = carrier.attrs
            v = (0.15 + 0.05 * (a["dribbling"] - d.attrs["tackling"])
                 + 0.02 * (a["pace"] - d.attrs["pace"]) + self._side_bonus(att)
                 - self._fat_pen(att, cslot) - (0.25 if up else 0) + 1.1 * self._def_tired(dfn))
            p = _sig(v)
            nx = _clamp(x + rng.uniform(4, 10), 1, 104)
            ny = _clamp(y + rng.gauss(0, 4) + self._cut_inside(carrier, x, y), 1, 67)
            if rng.random() < p:
                self._emit(att, "take_on", carrier, x, y, att, outcome="success", end=(nx, ny),
                           related=d, under_pressure=up, difficulty=round(1 - p, 3))
                self._tick(rng.uniform(1.5, 3.0))
                return ("continue", carrier, nx, ny, False)
            disc = d.attrs["discipline"] * 0.6 + 100 * dfn.style.get("discipline", 0.5) * 0.4
            if dfn.yellows.get(d.player_id, 0):
                disc += 35
            if rng.random() < 0.3 * math.exp(-0.03 * (disc - 55)) * (0.27 if in_box(x, y) else 1.0):
                self._emit(att, "take_on", carrier, x, y, att, outcome="fouled", related=d,
                           under_pressure=up, difficulty=round(1 - p, 3))
                return ("restart", self._foul(dfn, att, d, carrier, x, y, up=up))
            self._emit(att, "take_on", carrier, x, y, att, outcome="fail", related=d,
                       under_pressure=up, difficulty=round(1 - p, 3))
            self._emit(dfn, "tackle", d, x, y, att, outcome="won", related=carrier)
            self._tick(rng.uniform(1.0, 2.0))
            return ("restart", ("turnover", dfn, L - x, W - y, d))
        dist = _clamp(rng.gauss(6 + 4 * aggr, 3.5), 1.5, 18)
        ty = self._lane_target_y(att, y, 5) if rng.random() < 0.3 else y + rng.gauss(0, 3)
        ty += self._cut_inside(carrier, x, y)
        ang = math.atan2(ty - y, 10)
        nx = _clamp(x + dist * math.cos(ang), 1, 104)
        ny = _clamp(y + dist * math.sin(ang), 1, 67)
        self._emit(att, "carry", carrier, x, y, att, outcome="complete", end=(nx, ny),
                   under_pressure=up)
        self._tick(dist / 4.5 + rng.uniform(0.3, 1.2))
        return ("continue", carrier, nx, ny, False)

    def _clearance(self, att: Side, dfn: Side, carrier: Player, x: float, y: float, up: bool):
        rng = self.rng
        tx = _clamp(x + rng.gauss(38, 9), 20, 100)
        ty = _clamp(y + rng.gauss(0, 18), 0, W)
        self._emit(att, "clearance", carrier, x, y, att, end=(tx, ty), under_pressure=up,
                   body_part="foot")
        self._tick(rng.uniform(2.0, 3.5))
        if ty <= 0.5 or ty >= W - 0.5:
            self.stoppages += 1
            self._tick(rng.uniform(10, 20))
            return ("restart", ("throw_in", dfn, L - tx, W - ty, None))
        if rng.random() < 0.58:
            d = self._pick_defender(dfn, tx, ty).player
            self._emit(dfn, "ball_recovery", d, tx, ty, att)
            return ("restart", ("turnover", dfn, L - tx, W - ty, d))
        rec = self._pick_receiver(att, tx, ty, carrier, x, y).player
        self._emit(att, "ball_recovery", rec, tx, ty, att)
        return ("continue", rec, tx, ty, False)

    # ------------------------------------------------------------------ aerial duels
    def _aerial(self, att: Side, dfn: Side, attacker: Player, defender: Player,
                x: float, y: float, set_piece_edge: float = 0.0) -> bool:
        rng = self.rng
        h = (attacker.height_cm - defender.height_cm) / 4.0
        v = 0.06 * (attacker.attrs["aerial"] - defender.attrs["aerial"]) + 0.1 * h + set_piece_edge
        won = rng.random() < _sig(v)
        self._emit(att, "aerial_duel", attacker, x, y, att, outcome="won" if won else "lost",
                   related=defender)
        self._emit(dfn, "aerial_duel", defender, x, y, att, outcome="lost" if won else "won",
                   related=attacker)
        return won

    # ------------------------------------------------------------------ crosses
    def _cross(self, att: Side, dfn: Side, carrier: Player, x: float, y: float, up: bool,
               set_piece: str | None = None, sp_edge: float = 0.0):
        rng = self.rng
        a = carrier.attrs
        tx = _clamp(rng.gauss(95.5, 3.2), 88, 103)
        ty = _clamp(rng.gauss(GOAL_Y, 6.5), 22, 46)
        length = math.hypot(tx - x, ty - y)
        # Who attacks the ball: at set pieces the five best in the air (centre-backs come up);
        # in open play the forwards and midfielders who arrive in the box. Spread over several
        # players, so no one heads in a season's worth of goals.
        targets = [s for s in att.slots if s.player is not carrier and s.player.position != "GK"]
        if not set_piece:
            targets = [s for s in targets if s.player.position in ("ST", "RW", "LW", "AM", "CM")] or targets
        targets.sort(key=lambda s: -(s.player.attrs["aerial"] + (12 if s.player.position == "ST" else 0)
                                     + (8 if set_piece and s.player.position == "CB" else 0)))
        pool = targets[:5] if set_piece else targets[:4]
        weights = (0.28, 0.24, 0.2, 0.16, 0.12) if set_piece else (0.4, 0.25, 0.2, 0.15)
        tgt = rng.choices(pool, weights=weights[:len(pool)])[0].player
        gk = dfn.gk().player
        dfd = self._pick_defender(dfn, tx, ty).player
        if set_piece:
            # Zonal/man marking: one of the taller defenders, and set-piece
            # routines hunt for the weakest of them.
            markers = sorted(dfn.outfield(), key=lambda s: -(s.player.attrs["aerial"] + 0.5 * s.player.height_cm))[:5]
            if rng.random() < 0.35:
                dfd = min(markers, key=lambda s: s.player.attrs["aerial"]).player
            else:
                dfd = rng.choice(markers).player
        # Keeper claims?
        p_claim = _sig(-2.3 + 0.05 * (gk.attrs["gk_claiming"] - 65) - 0.02 * (a["crossing"] - 65))
        speed = self._ball_speed(length)
        if rng.random() < p_claim:
            self._emit(att, "pass", carrier, x, y, att, outcome="incomplete", end=(tx, ty),
                       receiver=tgt, pass_type="cross", pass_length=round(length, 1),
                       under_pressure=up, difficulty=round(1 - (1 - p_claim) * 0.35, 3),
                       set_piece=set_piece, ball_speed_kmh=speed)
            self._emit(dfn, "gk_claim", gk, tx, ty, att, outcome="success")
            self._tick(rng.uniform(4, 9))
            return ("restart", ("gk_hold", dfn, 10.0, 34.0, gk))
        edge = (0.045 * (a["crossing"] - 65)
                + 2.4 * (att.style.get("set_piece_attack", 0.5) - 0.5) * (1 if set_piece else 0)
                - 3.0 * (dfn.style.get("set_piece_defense", 0.5) - 0.5) * (1 if set_piece else 0)
                + sp_edge - (0.3 if up else 0) + self._side_bonus(att) + 0.8 * self._def_tired(dfn))
        if rng.random() < 0.06 * (1.6 - gk.attrs["gk_claiming"] / 100):
            # Keeper flaps / spills - big chance follows.
            edge += 0.8
        won = self._aerial(att, dfn, tgt, dfd, tx, ty,
                           set_piece_edge=edge - (1.7 if set_piece else 1.85))
        if won:
            self._emit(att, "pass", carrier, x, y, att, outcome="complete", end=(tx, ty),
                       receiver=tgt, pass_type="cross", pass_length=round(length, 1),
                       under_pressure=up, difficulty=0.7, set_piece=set_piece, ball_speed_kmh=speed)
            self._tick(1.5 + length / 20)
            if rng.random() < 0.45:   # a won header goes at goal; otherwise it is knocked down
                return ("restart", self._shot(att, dfn, tgt, tx, ty, False, header=True))
            return ("continue", tgt, tx - rng.uniform(0, 4), ty, True)
        self._emit(att, "pass", carrier, x, y, att, outcome="incomplete", end=(tx, ty),
                   receiver=tgt, pass_type="cross", pass_length=round(length, 1),
                   under_pressure=up, difficulty=0.75, set_piece=set_piece, ball_speed_kmh=speed)
        self._tick(1.5 + length / 20)
        if rng.random() < 0.0035:
            return ("restart", self._own_goal(att, dfn, dfd, tx, ty))
        cx = _clamp(tx - rng.gauss(22, 8), 55, 100)
        cy = _clamp(ty + rng.gauss(0, 16), 0, W)
        self._emit(dfn, "clearance", dfd, tx, ty, att, end=(cx, cy), body_part="head")
        r = rng.random()
        if r < 0.2:
            self.stoppages += 1
            self._tick(rng.uniform(20, 35))
            return ("restart", ("corner", att, 104.5, 0.5 if rng.random() < 0.5 else W - 0.5, None))
        if r < 0.52:
            d2 = self._pick_defender(dfn, cx, cy).player
            self._emit(dfn, "ball_recovery", d2, cx, cy, att)
            return ("restart", ("turnover", dfn, L - cx, W - cy, d2))
        rec = self._pick_receiver(att, cx, cy, carrier, x, y).player
        self._emit(att, "ball_recovery", rec, cx, cy, att)
        return ("continue", rec, cx, cy, False)

    def _own_goal(self, att: Side, dfn: Side, defender: Player, x: float, y: float):
        self._emit(dfn, "own_goal", defender, x, y, att, outcome="goal")
        att.goals += 1
        self._tick(self.rng.uniform(50, 80))
        self.stoppages += 2
        return ("kick_off", dfn, 52.5, 34.0, None)

    # ------------------------------------------------------------------ shooting
    def _shot(self, att: Side, dfn: Side, shooter: Player, x: float, y: float, up: bool,
              header: bool, set_piece: str | None = None, xg_override: float | None = None):
        rng = self.rng
        a = shooter.attrs
        gk_slot = dfn.gk()
        gk = gk_slot.player
        xg = xg_override if xg_override is not None else xg_model(x, y, header)
        sslot = self._slot_of(att, shooter)
        # Finishing skill moves conversion a little around the xG model, as in real data: an
        # ordinary shooter converts at about xG, an elite finisher at roughly 1.2-1.3x, a centre-back
        # at about 0.8x. Above 88 the effect steepens, so genuinely clinical finishers stand out.
        fin = a["finishing"]
        v = (_logit(xg) + FIN_SLOPE * (fin - 72) + FIN_ELITE * max(0.0, fin - 88)
             + 0.002 * (a["composure"] - 75)
             - GK_SLOPE * (gk.attrs["gk_shot_stopping"] - 75) - (0.25 if up else 0.0) + SHOT_BASE
             + 0.3 * self._side_bonus(att) - 0.6 * self._fat_pen(att, sslot)
             + 0.5 * self._def_tired(dfn))
        if header:
            # Headers are hard to place: about one goal in six is headed in a top league.
            v += 0.012 * (a["aerial"] - 72) + HEADER_PEN
        p_goal = _sig(v)
        p_block = 0.0 if set_piece in ("penalty", "free_kick") else (0.33 if not in_box(x, y) else 0.2)
        if header:
            p_block *= 0.4
        p_block *= 1.25 if up else 1.0
        speed = round(_clamp(rng.gauss(55 if header else 92 + 0.25 * (a["finishing"] - 70), 9 if header else 12),
                             30, 132), 1)
        body = "head" if header else ("left_foot" if shooter.preferred_foot == "left" else "right_foot")
        base_kw = dict(xg=xg, body_part=body, under_pressure=up, ball_speed_kmh=speed,
                       set_piece=set_piece)
        self._tick(1.0)
        if rng.random() < p_block:
            blocker = self._pick_defender(dfn, (x + L) / 2, (y + GOAL_Y) / 2).player
            self._emit(att, "shot", shooter, x, y, att, outcome="blocked", related=blocker,
                       end=(x + 2, y), **base_kw)
            self._emit(dfn, "block", blocker, x + 2, y, att, related=shooter)
            r = rng.random()
            if r < 0.3:
                self.stoppages += 1
                self._tick(rng.uniform(20, 35))
                return ("corner", att, 104.5, 0.5 if y < GOAL_Y else W - 0.5, None)
            if r < 0.78:
                return ("turnover", dfn, L - (x + 3), W - y, blocker)
            rec = self._nearest_player(att, x - 4, y)
            self._emit(att, "ball_recovery", rec, x - 4, y, att)
            return ("turnover", att, x - 4, y, rec)
        p_goal_unblocked = min(0.97, p_goal / max(0.05, 1 - p_block))
        gy = _clamp(rng.gauss(GOAL_Y, 2.2), GOAL_Y - 3.5, GOAL_Y + 3.5)
        if rng.random() < p_goal_unblocked:
            self._emit(att, "shot", shooter, x, y, att, outcome="goal", end=(L, gy),
                       related=gk, **base_kw)
            att.goals += 1
            self._tick(rng.uniform(50, 80))
            self.stoppages += 2
            return ("kick_off", dfn, 52.5, 34.0, None)
        p_save = _clamp(0.30 + 0.45 * xg, 0.2, 0.75)
        if rng.random() < p_save:
            self._emit(att, "shot", shooter, x, y, att, outcome="saved", end=(L, gy),
                       related=gk, **base_kw)
            self._emit(dfn, "gk_save", gk, L, gy, att, outcome="saved", related=shooter, xg=xg)
            r = rng.random()
            if r < 0.5:
                self._tick(rng.uniform(4, 10))
                return ("gk_hold", dfn, 6.0, 34.0, gk)
            if r < 0.78:
                self.stoppages += 1
                self._tick(rng.uniform(20, 35))
                return ("corner", att, 104.5, 0.5 if rng.random() < 0.5 else W - 0.5, None)
            # Rebound
            rx, ry = _clamp(L - rng.uniform(5, 12), 85, 100), _clamp(GOAL_Y + rng.gauss(0, 6), 20, 48)
            if rng.random() < 0.38:
                rec = self._nearest_player(att, rx, ry)
                self._emit(att, "ball_recovery", rec, rx, ry, att)
                return self._shot(att, dfn, rec, rx, ry, False, header=False)
            d = self._pick_defender(dfn, rx, ry).player
            self._emit(dfn, "ball_recovery", d, rx, ry, att)
            return ("turnover", dfn, L - rx, W - ry, d)
        ex = L
        ey = _clamp(GOAL_Y + rng.choice([-1, 1]) * rng.uniform(3.8, 9), 0, W)
        self._emit(att, "shot", shooter, x, y, att, outcome="off_target", end=(ex, ey), **base_kw)
        self.stoppages += 1
        self._tick(rng.uniform(18, 32))
        return ("goal_kick", dfn, 5.5, 34.0, None)

    # ------------------------------------------------------------------ fouls and cards
    def _foul(self, offenders: Side, victims: Side, offender: Player, victim: Player,
              x: float, y: float, up: bool):
        """x, y in the victims' attacking frame. Returns the restart."""
        rng = self.rng
        self._emit(offenders, "foul", offender, x, y, victims, related=victim)
        self._emit(victims, "foul_won", victim, x, y, victims, related=offender)
        disc = offender.attrs["discipline"] * 0.65 + 100 * offenders.style.get("discipline", 0.5) * 0.35
        tactical = x > 55 and self._aggr(victims) >= 0
        p_yellow = _clamp(0.19 * math.exp(-0.028 * (disc - 55)) + (0.07 if tactical else 0.0)
                          + (0.03 if not offenders.is_home else 0.0), 0.02, 0.6)
        p_red = 0.0016 * math.exp(-0.02 * (disc - 55))
        if offenders.yellows.get(offender.player_id, 0) >= 1:
            p_yellow *= 0.3
        rec = offenders.lineup.get(offender.player_id)
        r = rng.random()
        if r < p_red:
            self._send_off(offenders, offender, x, y, victims, "red")
        elif r < p_red + p_yellow:
            n = offenders.yellows.get(offender.player_id, 0) + 1
            offenders.yellows[offender.player_id] = n
            if rec is not None:
                rec["yellow"] = n
            if n >= 2:
                self._send_off(offenders, offender, x, y, victims, "second_yellow")
            else:
                self._emit(offenders, "card", offender, x, y, victims, card="yellow")
                self._tick(rng.uniform(15, 30))
        self.stoppages += 1
        self._tick(rng.uniform(18, 40))
        booked = r < p_red + p_yellow
        if any(s.player is victim for s in victims.slots) and \
                rng.random() < CONTACT_INJURY_AFTER_FOUL * (2.2 if booked else 1.0) * proneness(victim) ** 0.5:
            self._injure(victims, victim, "contact", x, y, victims)
        if in_box(x, y):
            return ("penalty", victims, 94.0, 34.0, None)
        return ("free_kick", victims, x, y, victim)

    def _send_off(self, side: Side, player: Player, x: float, y: float, frame: Side, kind: str):
        self._emit(side, "card", player, x, y, frame, card=kind)
        side.reds += 1
        rec = side.lineup.get(player.player_id)
        if rec is not None:
            rec["red"] = 1
            rec["minute_off"] = int(self.match_seconds() // 60)
        side.slots = [s for s in side.slots if s.player is not player]
        self._tick(self.rng.uniform(40, 70))

    # ------------------------------------------------------------------ set pieces
    def _taker(self, side: Side, positions: tuple[str, ...] = ()) -> Player:
        """The main set-piece taker most of the time, his deputy otherwise (other foot, other side)."""
        pool = [s.player for s in side.slots if s.player.position != "GK"
                and (not positions or s.player.position in positions)] or [s.player for s in side.outfield()]
        ranked = sorted(pool, key=lambda p: -p.attrs["set_piece"])
        return ranked[1] if len(ranked) > 1 and self.rng.random() < 0.35 else ranked[0]

    def _corner(self, att: Side, dfn: Side, y: float):
        rng = self.rng
        taker = self._taker(att, ("RW", "LW", "AM", "CM", "RB", "LB"))
        cy = 0.5 if y < GOAL_Y else W - 0.5
        cx = 104.5
        if rng.random() < 0.2:
            rec = self._pick_receiver(att, 98, abs(cy - 8), taker, cx, cy)
            self._emit(att, "pass", taker, cx, cy, att, outcome="complete",
                       end=(98, abs(cy - 8) if cy < 34 else cy - 8), receiver=rec.player,
                       pass_type="short", pass_length=9.0, difficulty=0.05, set_piece="corner",
                       ball_speed_kmh=30.0)
            self._tick(2.5)
            return ("continue", rec.player, 98.0, 9.0 if cy < 34 else 59.0)
        sp_edge = 0.025 * (taker.attrs["set_piece"] - 65)
        res = self._cross(att, dfn, taker, cx, cy, False, set_piece="corner", sp_edge=sp_edge)
        if res[0] == "continue":
            return ("continue", res[1], res[2], res[3])
        return res

    def _free_kick(self, att: Side, dfn: Side, x: float, y: float, fouled: Player | None):
        rng = self.rng
        dist = math.hypot(L - x, GOAL_Y - y)
        central = abs(y - GOAL_Y) < 16
        if x > 75 and dist < 32 and central and rng.random() < 0.45:
            # Direct free kicks: about one in sixteen goes in.
            taker = self._taker(att, ("AM", "CM", "RW", "LW", "ST", "LB", "RB"))
            xg = round(_clamp(0.085 - 0.0025 * (dist - 18), 0.025, 0.085), 4)
            return ("restart", self._shot(att, dfn, taker, x, y, False, header=False,
                                          set_piece="free_kick", xg_override=xg))
        if x > 70 and not central or (x > 82):
            taker = self._taker(att, ("RW", "LW", "AM", "CM", "RB", "LB"))
            res = self._cross(att, dfn, taker, x, y, False, set_piece="free_kick",
                              sp_edge=0.02 * (taker.attrs["set_piece"] - 65) - 0.15)
            if res[0] == "continue":
                return ("continue", res[1], res[2], res[3])
            return res
        taker = fouled or self._nearest_player(att, x, y)
        tx, ty = _clamp(x + rng.gauss(4, 8), 1, 100), _clamp(y + rng.gauss(0, 10), 1, 67)
        rec = self._pick_receiver(att, tx, ty, taker, x, y)
        self._emit(att, "pass", taker, x, y, att, outcome="complete", end=(tx, ty),
                   receiver=rec.player, pass_type="short", pass_length=round(math.hypot(tx - x, ty - y), 1),
                   difficulty=0.05, set_piece="free_kick", ball_speed_kmh=self._ball_speed(10))
        self._tick(2.0)
        return ("continue", rec.player, tx, ty)

    def _penalty(self, att: Side, dfn: Side):
        rng = self.rng
        taker = max(att.outfield(), key=lambda s: s.player.attrs["finishing"] * 0.6
                    + s.player.attrs["composure"] * 0.4).player
        gk = dfn.gk().player
        # Centred on a typical taker (a club's best finisher): about four in five go in.
        v = (_logit(0.79) + 0.03 * (taker.attrs["composure"] - 82) + 0.02 * (taker.attrs["finishing"] - 86)
             - 0.035 * (gk.attrs["gk_shot_stopping"] - 75))
        p = _sig(v)
        speed = round(_clamp(rng.gauss(95, 10), 60, 125), 1)
        body = "left_foot" if taker.preferred_foot == "left" else "right_foot"
        gy = _clamp(rng.gauss(GOAL_Y, 2.4), GOAL_Y - 3.5, GOAL_Y + 3.5)
        if rng.random() < p:
            self._emit(att, "shot", taker, 94.0, 34.0, att, outcome="goal", end=(L, gy), xg=0.76,
                       body_part=body, set_piece="penalty", ball_speed_kmh=speed, related=gk)
            att.goals += 1
            self._tick(rng.uniform(55, 85))
            self.stoppages += 2
            return ("kick_off", dfn, 52.5, 34.0, None)
        if rng.random() < 0.7:
            self._emit(att, "shot", taker, 94.0, 34.0, att, outcome="saved", end=(L, gy), xg=0.76,
                       body_part=body, set_piece="penalty", ball_speed_kmh=speed, related=gk)
            self._emit(dfn, "gk_save", gk, L, gy, att, outcome="saved", related=taker, xg=0.76)
            self._tick(rng.uniform(15, 25))
            return ("corner", att, 104.5, 0.5, None) if rng.random() < 0.35 else ("gk_hold", dfn, 6.0, 34.0, gk)
        self._emit(att, "shot", taker, 94.0, 34.0, att, outcome="off_target",
                   end=(L, GOAL_Y + rng.choice([-5, 5])), xg=0.76, body_part=body,
                   set_piece="penalty", ball_speed_kmh=speed)
        self._tick(rng.uniform(20, 30))
        return ("goal_kick", dfn, 5.5, 34.0, None)

    def _goal_kick(self, att: Side, dfn: Side):
        rng = self.rng
        gk = att.gk().player
        directness = att.style.get("directness", 0.5)
        press = dfn.style.get("press_height", 0.5)
        if rng.random() < 0.25 + 0.55 * directness + 0.2 * (press - 0.5):
            tx = rng.gauss(60, 8)
            ty = _clamp(rng.gauss(34, 14), 3, 65)
            rec = self._pick_receiver(att, tx, ty, gk, 5.5, 34)
            dpl = self._pick_defender(dfn, tx, ty).player
            won = self._aerial(att, dfn, rec.player, dpl, tx, ty)
            length = math.hypot(tx - 5.5, ty - 34)
            out = "complete" if won and rng.random() < 0.8 else "incomplete"
            self._emit(att, "pass", gk, 5.5, 34, att, outcome=out, end=(tx, ty), receiver=rec.player,
                       pass_type="long", pass_length=round(length, 1), difficulty=0.55,
                       set_piece="goal_kick", ball_speed_kmh=self._ball_speed(length))
            self._tick(3.0)
            if out == "complete":
                return ("continue", rec.player, tx, ty)
            self._emit(dfn, "ball_recovery", dpl, tx, ty, att)
            return ("restart", ("turnover", dfn, L - tx, W - ty, dpl))
        cb = [s for s in att.slots if s.player.position in ("CB", "DM")] or att.outfield()
        rec = rng.choice(cb).player
        tx, ty = 12.0, rng.choice([18.0, 50.0])
        self._emit(att, "pass", gk, 5.5, 34, att, outcome="complete", end=(tx, ty), receiver=rec,
                   pass_type="short", pass_length=round(math.hypot(tx - 5.5, ty - 34), 1),
                   difficulty=0.04, set_piece="goal_kick", ball_speed_kmh=self._ball_speed(15))
        self._tick(2.5)
        return ("continue", rec, tx, ty)

    def _throw_in(self, att: Side, dfn: Side, thrower: Player, x: float, y: float):
        rng = self.rng
        tx = _clamp(x + rng.gauss(2, 6), 1, 104)
        ty = _clamp(y + (rng.uniform(6, 14) if y < GOAL_Y else -rng.uniform(6, 14)), 1, 67)
        rec = self._pick_receiver(att, tx, ty, thrower, x, y)
        p = 0.88 if x < 80 else 0.72
        if rng.random() < p:
            self._emit(att, "pass", thrower, x, y, att, outcome="complete", end=(tx, ty),
                       receiver=rec.player, pass_type="throw_in",
                       pass_length=round(math.hypot(tx - x, ty - y), 1), difficulty=round(1 - p, 3),
                       set_piece="throw_in", body_part="hands")
            self._tick(2.0)
            return ("continue", rec.player, tx, ty)
        d = self._pick_defender(dfn, tx, ty).player
        self._emit(att, "pass", thrower, x, y, att, outcome="incomplete", end=(tx, ty),
                   receiver=rec.player, pass_type="throw_in",
                   pass_length=round(math.hypot(tx - x, ty - y), 1), difficulty=round(1 - p, 3),
                   set_piece="throw_in", body_part="hands")
        self._emit(dfn, "interception", d, tx, ty, att, outcome="won", related=thrower)
        return ("restart", ("turnover", dfn, L - tx, W - ty, d))


def penalty_shootout(home: Club, away: Club, seed: int) -> dict:
    """Simple shootout for drawn knockout ties (e.g. the playoff final)."""
    rng = random.Random(seed)

    def takers(c: Club) -> list[Player]:
        xi = [p for _s, p in best_xi(c) if p.position != "GK"]
        return sorted(xi, key=lambda p: -(p.attrs["composure"] + p.attrs["finishing"]))

    def gk(c: Club) -> Player:
        return next(p for _s, p in best_xi(c) if p.position == "GK")

    goals = {"home": 0, "away": 0}
    kicks = []
    ht, at = takers(home), takers(away)
    for i in range(20):
        for side, tk, keeper in (("home", ht, gk(away)), ("away", at, gk(home))):
            p = tk[i % len(tk)]
            v = (_logit(0.76) + 0.03 * (p.attrs["composure"] - 70) - 0.03 * (keeper.attrs["gk_shot_stopping"] - 70))
            scored = rng.random() < _sig(v)
            goals[side] += int(scored)
            kicks.append({"side": side, "player_id": p.player_id, "scored": scored})
        if i >= 4 and goals["home"] != goals["away"]:
            break
        if i < 4:
            rem = 4 - i
            if goals["home"] > goals["away"] + rem or goals["away"] > goals["home"] + rem:
                break
    return {"home": goals["home"], "away": goals["away"], "kicks": kicks,
            "winner": "home" if goals["home"] > goals["away"] else "away"}
