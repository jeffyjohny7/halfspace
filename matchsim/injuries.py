"""Injuries, suspensions and team news.

In-match injuries come from the match engine (contact after fouls, and muscle
injuries that rise with tiredness); training injuries happen between matches.
Every player has a hidden injury proneness (older players and those with low
stamina break down more often).

Suspensions follow familiar rules: a straight red is a 3-match ban, a second
yellow 1 match; 5 league yellows before the halfway point cost 1 match, 10 before
the last six rounds 2 matches, and 15 at any time 3 matches.

The tracker is run in date order, so each match is picked from the players
actually available on that day, and it publishes the team news before every match.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import random
from dataclasses import dataclass, field

# Injury types: (name, share of contact injuries, share of non-contact, days median, spread)
INJURY_TYPES = [
    ("knock", 0.42, 0.10, 4, 0.45),
    ("ankle sprain", 0.20, 0.06, 16, 0.5),
    ("knee ligament", 0.10, 0.05, 35, 0.5),
    ("hamstring strain", 0.04, 0.32, 21, 0.45),
    ("calf strain", 0.03, 0.15, 16, 0.45),
    ("groin strain", 0.02, 0.12, 18, 0.45),
    ("thigh strain", 0.03, 0.12, 19, 0.45),
    ("back spasm", 0.02, 0.05, 7, 0.4),
    ("broken foot", 0.05, 0.0, 70, 0.3),
    ("shoulder injury", 0.06, 0.0, 24, 0.5),
    ("concussion", 0.03, 0.0, 9, 0.3),
    ("cruciate ligament", 0.0, 0.03, 220, 0.2),
]
TRAINING_TYPES = INJURY_TYPES + [("illness", 0.0, 0.25, 5, 0.4)]

TRAINING_INJURIES_PER_CLUB_PER_WEEK = 0.42
EUROPE_TRAINING_BOOST = 1.3
# yellows -> (ban, deadline as a share of the league season; after it the count no longer bans)
YELLOW_BANS = {5: (1, 0.5), 10: (2, 0.84), 15: (3, 1.01)}
ROUNDS = {1: 38, 2: 46}
STRAIGHT_RED_BAN = 3
SECOND_YELLOW_BAN = 1
DOUBTFUL_WINDOW_DAYS = 3


def _unit(*parts) -> float:
    h = hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def proneness(player, ref_year: int = 2026) -> float:
    """Hidden injury proneness (1.0 = average). Deterministic per player."""
    u = min(max(_unit("prone", player.player_id), 1e-6), 1 - 1e-6)
    z = math.sqrt(2) * _erfinv(2 * u - 1)
    base = math.exp(0.35 * z)
    age = ref_year - player.birth_year
    stamina = player.attrs.get("stamina", 65)
    return base * (1 + 0.05 * max(0, age - 29)) * (1 + 0.012 * max(0, 65 - stamina))


def _erfinv(y: float) -> float:
    a = 0.147
    ln = math.log(1 - y * y)
    t = 2 / (math.pi * a) + ln / 2
    return math.copysign(math.sqrt(math.sqrt(t * t - ln / a) - t), y)


def sample_injury(rng: random.Random, cause: str) -> tuple[str, int]:
    """(injury name, days out). cause: contact | non_contact | training."""
    table = TRAINING_TYPES if cause == "training" else INJURY_TYPES
    col = 1 if cause == "contact" else 2
    weights = [t[col] for t in table]
    name, _c, _n, median, spread = rng.choices(table, weights=weights)[0]
    days = int(round(median * math.exp(rng.gauss(0, spread))))
    return name, max(1, days)


def severity(days: int) -> str:
    return "knock" if days <= 7 else ("minor" if days <= 21 else ("moderate" if days <= 60 else "major"))


@dataclass
class Absence:
    player_id: str
    kind: str                      # injury | suspension
    reason: str
    since: dt.date
    until: dt.date | None = None   # injuries: first day available again
    matches_left: int = 0          # suspensions
    expected_return: dt.date | None = None
    injury_id: str | None = None


@dataclass
class Tracker:
    """Who is out, from when, until when. Run strictly in date order."""

    seed: int
    absences: dict[str, list[Absence]] = field(default_factory=dict)
    yellows: dict[str, int] = field(default_factory=dict)          # league yellows this season
    injuries: list[dict] = field(default_factory=list)
    suspensions: list[dict] = field(default_factory=list)
    team_news: list[dict] = field(default_factory=list)
    last_training_day: dict[str, dt.date] = field(default_factory=dict)
    season: str = ""

    # ------------------------------------------------------------------ queries
    def _active(self, pid: str, date: dt.date) -> list[Absence]:
        out = []
        for a in self.absences.get(pid, []):
            if a.kind == "injury" and a.since <= date < a.until:
                out.append(a)
            elif a.kind == "suspension" and a.matches_left > 0:
                out.append(a)
        return out

    def selection(self, club, date: dt.date) -> tuple[set[str], set[str]]:
        """(unavailable, doubtful) player ids for a club on a match day."""
        out, doubt = set(), set()
        for p in club.squad:
            act = self._active(p.player_id, date)
            if not act:
                continue
            if any(a.kind == "suspension" for a in act):
                out.add(p.player_id)
            elif max((a.until - date).days for a in act) <= DOUBTFUL_WINDOW_DAYS:
                doubt.add(p.player_id)          # back in training this week: a late fitness test
            else:
                out.add(p.player_id)
        return out, doubt

    def news(self, club, date: dt.date, fixture) -> list[dict]:
        """Team news published before a match (what a club would announce)."""
        rows = []
        for p in club.squad:
            for a in self._active(p.player_id, date):
                status = "suspended" if a.kind == "suspension" else (
                    "doubtful" if (a.until - date).days <= DOUBTFUL_WINDOW_DAYS else "injured")
                rows.append({
                    "season": fixture.season, "round": fixture.round, "match_id": fixture.match_id,
                    "date": date.isoformat(), "club_id": club.club_id, "player_id": p.player_id,
                    "status": status, "reason": a.reason, "since": a.since.isoformat(),
                    "expected_return": a.expected_return.isoformat() if a.expected_return else None,
                    "matches_remaining": a.matches_left if a.kind == "suspension" else None,
                    "injury_id": a.injury_id})
        return rows

    # ------------------------------------------------------------------ updates
    def new_season(self, season: str) -> None:
        self.season = season
        self.yellows = {}

    def add_injury(self, pid: str, club_id: str, date: dt.date, name: str, days: int, cause: str,
                   match_id: str | None = None, minute: int | None = None) -> None:
        rng = random.Random(f"{self.seed}:est:{pid}:{date}")
        estimate = max(1, int(round(days * math.exp(rng.gauss(0, 0.25)))))
        iid = f"INJ-{len(self.injuries) + 1:05d}"
        until = date + dt.timedelta(days=days)
        self.absences.setdefault(pid, []).append(Absence(pid, "injury", name, date, until=until,
                                                         expected_return=date + dt.timedelta(days=estimate),
                                                         injury_id=iid))
        self.injuries.append({"injury_id": iid, "season": self.season, "player_id": pid, "club_id": club_id,
                              "date": date.isoformat(), "match_id": match_id, "minute": minute, "cause": cause,
                              "injury": name, "severity": severity(days), "days_out": days,
                              "expected_return": (date + dt.timedelta(days=estimate)).isoformat(),
                              "return_date": until.isoformat()})

    def training(self, clubs: list, date: dt.date, europe_dates: dict[str, list[dt.date]]) -> None:
        """Training injuries for each club since it was last checked, up to `date`."""
        for c in clubs:
            last = self.last_training_day.get(c.club_id)
            self.last_training_day[c.club_id] = date
            if last is None or date <= last:
                continue
            days = min((date - last).days, 21)       # the summer break counts as pre-season only
            rate = TRAINING_INJURIES_PER_CLUB_PER_WEEK * days / 7.0
            if any(last < d <= date for d in europe_dates.get(c.club_id, [])):
                rate *= EUROPE_TRAINING_BOOST
            rng = random.Random(f"{self.seed}:train:{c.club_id}:{date}")
            n = _poisson(rng, rate)
            for _ in range(n):
                fit = [p for p in c.squad if not self._active(p.player_id, date)]
                if not fit:
                    break
                p = rng.choices(fit, weights=[proneness(p) for p in fit])[0]
                when = date - dt.timedelta(days=rng.randint(1, max(1, days - 1)))
                name, d = sample_injury(rng, "training")
                self.add_injury(p.player_id, c.club_id, when, name, d, "training")

    def after_match(self, fixture, result, date: dt.date, clubs: dict) -> None:
        """Cards -> bans, in-match injuries -> absences, and bans served."""
        league = fixture.stage == "league"
        played = {fixture.home_id, fixture.away_id}
        # Bans served: one match off every active suspension of players at these clubs.
        for cid in played:
            for p in clubs[cid].squad:
                for a in self.absences.get(p.player_id, []):
                    if a.kind == "suspension" and a.matches_left > 0 and a.since < date:
                        a.matches_left -= 1
        for row in result.lineups:
            pid, cid = row["player_id"], row["team_id"]
            red, yel = int(row.get("red") or 0), int(row.get("yellow") or 0)
            ban, reason = 0, None
            if red:
                if yel >= 2:
                    ban, reason = SECOND_YELLOW_BAN, "sent off (second yellow)"
                else:
                    ban, reason = STRAIGHT_RED_BAN, "sent off (straight red)"
            elif yel and league:
                before = self.yellows.get(pid, 0)
                n = before + yel
                self.yellows[pid] = n
                share = fixture.round / ROUNDS.get(fixture.division, 38)
                for limit, (length, deadline) in YELLOW_BANS.items():
                    if before < limit <= n and share <= deadline:
                        ban, reason = length, f"{limit} yellow cards"
            if ban:
                self.absences.setdefault(pid, []).append(Absence(pid, "suspension", reason, date, matches_left=ban))
                self.suspensions.append({"season": fixture.season, "player_id": pid, "club_id": cid,
                                         "match_id": fixture.match_id, "date": date.isoformat(),
                                         "reason": reason, "matches": ban})
        rng = random.Random(f"{self.seed}:inj:{fixture.match_id}")
        for inj in result.injuries:
            name, days = sample_injury(rng, inj["cause"])
            if inj["outcome"] == "played_on":
                name, days = "knock", rng.randint(1, 6)
            self.add_injury(inj["player_id"], inj["team_id"], date, name, days, inj["cause"],
                            match_id=fixture.match_id, minute=inj["minute"])


def _poisson(rng: random.Random, lam: float) -> int:
    k, p, L = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1
