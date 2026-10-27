"""Fixtures, calendars, European midweeks, standings and parallel season runs."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import random
from dataclasses import asdict, dataclass, field
from multiprocessing import get_context

import pyarrow as pa
import pyarrow.parquet as pq

from .engine import MatchEngine, MatchResult, penalty_shootout
from .schema import EVENT_COLUMNS, EVENT_SCHEMA
from .universe import Club

# ---------------------------------------------------------------------------
# Fixtures and calendar
# ---------------------------------------------------------------------------


@dataclass
class Fixture:
    match_id: str
    season: str
    competition: str
    division: int
    stage: str           # league | playoff_semi_leg1 | playoff_semi_leg2 | playoff_final
    round: int
    date: dt.date
    home_id: str
    away_id: str
    neutral: bool = False
    # Filled in before simulation
    home_days_rest: int | None = None
    away_days_rest: int | None = None
    home_rotation: int = 0
    away_rotation: int = 0
    home_fatigue: float = 0.0
    away_fatigue: float = 0.0
    home_midweek_europe: bool = False
    away_midweek_europe: bool = False


def double_round_robin(club_ids: list[str], rng: random.Random,
                       feature: tuple[str, str, int] | None = None) -> list[list[tuple[str, str]]]:
    """Circle-method schedule. Returns rounds of (home, away) pairs.

    The first half is a single round robin; the second half replays it in the same order with
    venues swapped, so every club has exactly as many home games as away games. Venues in the
    first half are chosen round by round to alternate: a club that was away last time is at
    home next, and when both clubs were last at the same venue, the one with fewer home games
    (or the longer run away) gets the home game. A club rarely plays three in a row at home or
    away, and every club has 4-6 home games in the first ten rounds.

    feature = (home_id, away_id, round_no) puts that fixture in that round with that venue
    (the broadcaster's pick); the round holding the pairing swaps places with round_no.
    """
    ids = list(club_ids)
    rng.shuffle(ids)
    if len(ids) % 2:
        ids.append("BYE")
    n = len(ids)
    raw: list[list[tuple[str, str]]] = []
    arr = ids[:]
    for _r in range(n - 1):
        raw.append([(arr[i], arr[n - 1 - i]) for i in range(n // 2)
                    if "BYE" not in (arr[i], arr[n - 1 - i])])
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    forced: tuple[str, str] | None = None
    if feature is not None and feature[0] in ids and feature[1] in ids:
        fh, fa, fr = feature
        k = next(j for j, rnd in enumerate(raw) if any({a, b} == {fh, fa} for a, b in rnd))
        t = max(0, min(len(raw) - 1, fr - 1))
        raw[k], raw[t] = raw[t], raw[k]
        forced = (fh, fa)

    last: dict[str, str] = {}
    run: dict[str, int] = {c: 0 for c in ids}
    homes: dict[str, int] = {c: 0 for c in ids}

    def pull_home(c: str, r: int) -> float:
        streak = run[c] if last.get(c) == "A" else (-run[c] if last.get(c) == "H" else 0)
        return 2.0 * streak + (r / 2 - homes[c])

    first: list[list[tuple[str, str]]] = []
    for r, rnd in enumerate(raw):
        pairs = []
        for i, (a, b) in enumerate(rnd):
            if forced is not None and {a, b} == set(forced):
                h, aw = forced
            else:
                pa, pb = pull_home(a, r), pull_home(b, r)
                if pa == pb:
                    h, aw = (a, b) if (r + i) % 2 == 0 else (b, a)
                else:
                    h, aw = (a, b) if pa > pb else (b, a)
            pairs.append((h, aw))
            for c, v in ((h, "H"), (aw, "A")):
                run[c] = run[c] + 1 if last.get(c) == v else 1
                last[c] = v
            homes[h] += 1
        first.append(pairs)
    second = [[(a, h) for (h, a) in rnd] for rnd in first]
    return first + second


def _next_weekday(d: dt.date, weekday: int) -> dt.date:
    """Next date on or after d that falls on weekday (Mon=0)."""
    return d + dt.timedelta(days=(weekday - d.weekday()) % 7)


def league_calendar(n_rounds: int, start_year: int, rng: random.Random) -> list[dt.date]:
    """Saturdays from mid-August to late May, skipping international breaks,
    plus Tuesday rounds when more rounds are needed."""
    start = _next_weekday(dt.date(start_year, 8, 15), 5)
    end = dt.date(start_year + 1, 5, 23)
    breaks = []
    for (m, d) in [(9, 6), (10, 11), (11, 15), (3, 28)]:
        year = start_year if m >= 8 else start_year + 1
        breaks.append(_next_weekday(dt.date(year, m, d), 5))
    sats = []
    d = start
    while d <= end:
        if d not in breaks:
            sats.append(d)
        d += dt.timedelta(days=7)
    dates = sats[:n_rounds]
    if len(sats) < n_rounds:
        # Add midweek rounds: Christmas period first, then spread out.
        extra_needed = n_rounds - len(sats)
        candidates = []
        for s in sats[2:-1]:
            tue = s + dt.timedelta(days=3)
            prio = 0 if (tue.month in (12, 1)) else (1 if tue.month in (2, 4) else 2)
            candidates.append((prio, rng.random(), tue))
        candidates.sort()
        extra = [c[2] for c in candidates[:extra_needed]]
        dates = sorted(sats + extra)
    return dates


EURO_MATCHDAYS = {
    # competition -> list of (month, approx day). Continental Cup Tue/Wed,
    # Continental Shield Thursday.
    "champions_league": [(9, 16), (9, 30), (10, 21), (11, 4), (11, 25), (12, 9), (1, 20), (1, 28),
                         (2, 17), (2, 24), (3, 10), (3, 17), (4, 7), (4, 14), (4, 28), (5, 5)],
    "europa_league": [(9, 24), (10, 1), (10, 22), (11, 5), (11, 26), (12, 10), (1, 22), (1, 29),
                      (2, 19), (2, 26), (3, 12), (3, 19), (4, 9), (4, 16), (4, 30), (5, 7)],
}
_LEAGUE_PHASE = 8  # league-phase matchdays every qualified club plays


def european_calendar(qualifiers: dict[str, str], quality: dict[str, float], start_year: int,
                      rng: random.Random) -> list[dict]:
    """Midweek European fixtures for qualified clubs (results are not simulated;
    they only matter for rest days and rotation)."""
    rows = []
    for club_id, comp in qualifiers.items():
        days = EURO_MATCHDAYS[comp]
        weekday = rng.choice([1, 2]) if comp == "champions_league" else 3
        played = _LEAGUE_PHASE
        # Knockout progression: two legs per round, stronger clubs go further.
        p = min(0.85, max(0.25, 0.45 + 0.025 * (quality[club_id] - 72)))
        while played < len(days) and rng.random() < p:
            played += 2
        for i in range(min(played, len(days))):
            m, d = days[i]
            year = start_year if m >= 8 else start_year + 1
            date = _next_weekday(dt.date(year, m, d) - dt.timedelta(days=3), weekday)
            stage = "league_phase" if i < _LEAGUE_PHASE else "knockout"
            rows.append({"club_id": club_id, "competition": comp, "date": date,
                         "stage": stage, "matchday": i + 1})
    return rows


def apply_rest_and_rotation(fixtures: list[Fixture], euro: list[dict]) -> None:
    """Fill rest days, rotation and fatigue from each club's match calendar.

    Clubs that played in Europe on Thursday play their league game on Sunday.
    """
    euro_by_club: dict[str, list[dt.date]] = {}
    for row in euro:
        euro_by_club.setdefault(row["club_id"], []).append(row["date"])
    # Move Saturday fixtures to Sunday for Thursday-Europe clubs.
    for f in fixtures:
        for cid in (f.home_id, f.away_id):
            for ed in euro_by_club.get(cid, []):
                if ed.weekday() == 3 and 0 < (f.date - ed).days <= 3:
                    f.date = f.date + dt.timedelta(days=1)
    timeline: dict[str, list[tuple[dt.date, str]]] = {}
    for f in fixtures:
        timeline.setdefault(f.home_id, []).append((f.date, f.match_id))
        timeline.setdefault(f.away_id, []).append((f.date, f.match_id))
    for cid, dates in euro_by_club.items():
        timeline.setdefault(cid, []).extend((d, "EURO") for d in dates)
    for cid in timeline:
        timeline[cid].sort()
    prev: dict[tuple[str, str], tuple[int | None, bool]] = {}
    for cid, items in timeline.items():
        last = None
        last_was_euro = False
        for d, mid in items:
            if mid != "EURO":
                rest = (d - last).days if last else None
                prev[(cid, mid)] = (rest, last_was_euro and rest is not None and rest <= 4)
            last = d
            last_was_euro = mid == "EURO"
    for f in fixtures:
        for side in ("home", "away"):
            cid = f.home_id if side == "home" else f.away_id
            rest, euro_mid = prev.get((cid, f.match_id), (None, False))
            rotation, fatigue = 0, 0.0
            if rest is not None and rest <= 3:
                rotation, fatigue = 3, 0.07
            elif rest is not None and rest == 4:
                rotation, fatigue = 1, 0.04
            setattr(f, f"{side}_days_rest", rest)
            setattr(f, f"{side}_rotation", rotation)
            setattr(f, f"{side}_fatigue", fatigue)
            setattr(f, f"{side}_midweek_europe", euro_mid)


def league_fixtures(clubs: list[Club], season: str, competition: str, division: int,
                    start_year: int, rng: random.Random, rounds_limit: int | None = None,
                    feature: tuple[str, str, int] | None = None) -> list[Fixture]:
    ids = [c.club_id for c in clubs]
    rounds = double_round_robin(ids, rng, feature=feature)
    dates = league_calendar(len(rounds), start_year, rng)
    fixtures = []
    for r, (pairs, date) in enumerate(zip(rounds, dates), start=1):
        if rounds_limit is not None and r > rounds_limit:
            break
        for i, (h, a) in enumerate(pairs):
            fixtures.append(Fixture(
                match_id=f"{season.replace('-', '')}-D{division}-R{r:02d}-{i + 1:02d}",
                season=season, competition=competition, division=division, stage="league",
                round=r, date=date, home_id=h, away_id=a))
    return fixtures


# ---------------------------------------------------------------------------
# Running matches (in parallel) and writing events
# ---------------------------------------------------------------------------


def match_seed(base: int, match_id: str) -> int:
    h = hashlib.sha256(f"{base}:{match_id}".encode()).hexdigest()
    return int(h[:12], 16)


def _run_job(job: tuple) -> tuple[Fixture, MatchResult]:
    f, home, away, seed, home_out, away_out, home_doubt, away_doubt = job
    eng = MatchEngine(f.match_id, home, away, seed, home_fatigue=f.home_fatigue,
                      away_fatigue=f.away_fatigue, home_rotation=f.home_rotation,
                      away_rotation=f.away_rotation, neutral=f.neutral,
                      home_out=home_out, away_out=away_out, home_doubtful=home_doubt, away_doubtful=away_doubt)
    return f, eng.simulate()


class EventWriter:
    """Streams events to a Parquet file so memory stays flat."""

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.writer = pq.ParquetWriter(path, EVENT_SCHEMA, compression="zstd")
        self.rows = 0

    def write(self, events: list[dict]) -> None:
        cols = {c: [e.get(c) for e in events] for c in EVENT_COLUMNS}
        self.writer.write_table(pa.table(cols, schema=EVENT_SCHEMA))
        self.rows += len(events)

    def close(self) -> None:
        self.writer.close()


@dataclass
class SeasonResults:
    matches: list[dict] = field(default_factory=list)
    lineups: list[dict] = field(default_factory=list)
    team_news: list[dict] = field(default_factory=list)


def europe_dates(euro_rows: list[dict]) -> dict[str, list[dt.date]]:
    out: dict[str, list[dt.date]] = {}
    for r in euro_rows:
        out.setdefault(r["club_id"], []).append(r["date"])
    return out


def simulate_fixtures(fixtures: list[Fixture], clubs: dict[str, Club], base_seed: int,
                      writer: EventWriter | None, workers: int,
                      results: SeasonResults, progress: str = "", tracker=None,
                      europe: dict[str, list[dt.date]] | None = None) -> list[tuple[Fixture, MatchResult]]:
    """Simulate fixtures day by day. Matches on the same day run in parallel; between days
    the tracker updates injuries and suspensions, so each team is picked from the players
    actually available."""
    out: list[tuple[Fixture, MatchResult]] = []
    workers = workers or os.cpu_count() or 1
    by_day: dict[dt.date, list[Fixture]] = {}
    for f in sorted(fixtures, key=lambda f: (f.date, f.match_id)):
        by_day.setdefault(f.date, []).append(f)
    pool = get_context("spawn").Pool(workers) if workers > 1 and len(fixtures) > 8 else None
    done = 0
    try:
        for day, group in by_day.items():
            jobs = []
            if tracker is not None:
                tracker.training([clubs[c] for f in group for c in (f.home_id, f.away_id)], day, europe or {})
            for f in group:
                h, a = clubs[f.home_id], clubs[f.away_id]
                if tracker is not None:
                    ho, hd = tracker.selection(h, day)
                    ao, ad = tracker.selection(a, day)
                    results.team_news += tracker.news(h, day, f) + tracker.news(a, day, f)
                else:
                    ho = hd = ao = ad = set()
                jobs.append((f, h, a, match_seed(base_seed, f.match_id), ho, ao, hd, ad))
            done_group = pool.map(_run_job, jobs) if pool is not None and len(jobs) > 1 else [_run_job(j) for j in jobs]
            for f, r in done_group:
                _collect(f, r, writer, results)
                if tracker is not None:
                    tracker.after_match(f, r, day, clubs)
                out.append((f, _strip(r)))
                done += 1
                if progress and done % 50 == 0:
                    print(f"  {progress}: {done}/{len(fixtures)} matches", flush=True)
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    return out


def _strip(r: MatchResult) -> MatchResult:
    """Drop events after writing them, to save memory."""
    return MatchResult(r.match_id, r.home_id, r.away_id, r.home_goals, r.away_goals, [],
                       r.lineups, r.home_formation, r.away_formation, r.added_time, r.shootout,
                       injuries=r.injuries)


def _collect(f: Fixture, r: MatchResult, writer: EventWriter | None, results: SeasonResults) -> None:
    if writer is not None:
        writer.write(r.events)
    results.matches.append(match_row(f, r))
    for row in r.lineups:
        results.lineups.append({**row, "season": f.season})


def match_row(f: Fixture, r: MatchResult) -> dict:
    row = {k: v for k, v in asdict(f).items()}
    row["date"] = f.date.isoformat()
    row.update({"home_goals": r.home_goals, "away_goals": r.away_goals,
                "home_formation": r.home_formation, "away_formation": r.away_formation,
                "added_time_1h": r.added_time[0], "added_time_2h": r.added_time[1]})
    if r.shootout:
        row["shootout_home"] = r.shootout["home"]
        row["shootout_away"] = r.shootout["away"]
    return row


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------


def standings(match_rows: list[dict], club_ids: list[str], names: dict[str, str],
              up_to_round: int | None = None) -> list[dict]:
    t = {cid: {"club_id": cid, "club": names[cid], "played": 0, "won": 0, "drawn": 0,
               "lost": 0, "gf": 0, "ga": 0, "points": 0, "home_points": 0, "away_points": 0}
         for cid in club_ids}
    for m in match_rows:
        if m["stage"] != "league" or (up_to_round and m["round"] > up_to_round):
            continue
        h, a, hg, ag = m["home_id"], m["away_id"], m["home_goals"], m["away_goals"]
        if h not in t or a not in t:
            continue
        for cid, gf, ga, home in ((h, hg, ag, True), (a, ag, hg, False)):
            row = t[cid]
            row["played"] += 1
            row["gf"] += gf
            row["ga"] += ga
            pts = 3 if gf > ga else (1 if gf == ga else 0)
            row["points"] += pts
            row["home_points" if home else "away_points"] += pts
            row["won" if gf > ga else ("drawn" if gf == ga else "lost")] += 1
    table = sorted(t.values(), key=lambda r: (-r["points"], -(r["gf"] - r["ga"]), -r["gf"], r["club"]))
    for i, row in enumerate(table, 1):
        row["position"] = i
        row["gd"] = row["gf"] - row["ga"]
    return table


def run_playoffs(table: list[dict], clubs: dict[str, Club], season: str, start_year: int,
                 base_seed: int, writer: EventWriter | None, results: SeasonResults,
                 places: tuple[int, int], tracker=None) -> tuple[str, list[dict]]:
    """Two-legged semi-finals (3 v 6, 4 v 5) and a one-off neutral final."""
    lo, hi = places
    seeds = [row["club_id"] for row in table[lo - 1:hi]]
    pairs = [(seeds[0], seeds[3]), (seeds[1], seeds[2])]
    sid = season.replace("-", "")
    d1 = dt.date(start_year + 1, 5, 9)
    d2 = dt.date(start_year + 1, 5, 13)
    final_date = dt.date(start_year + 1, 5, 23)
    log = []
    winners = []
    for i, (high, low) in enumerate(pairs, 1):
        leg1 = Fixture(f"{sid}-D2-PO-SF{i}-L1", season, "Crown League Two Playoffs", 2,
                       "playoff_semi_leg1", 0, d1, low, high)
        leg2 = Fixture(f"{sid}-D2-PO-SF{i}-L2", season, "Crown League Two Playoffs", 2,
                       "playoff_semi_leg2", 0, d2, high, low, home_days_rest=4, away_days_rest=4)
        (_, r1), = simulate_fixtures([leg1], clubs, base_seed, writer, 1, results, tracker=tracker)
        (_, r2), = simulate_fixtures([leg2], clubs, base_seed, writer, 1, results, tracker=tracker)
        agg_high = r1.away_goals + r2.home_goals
        agg_low = r1.home_goals + r2.away_goals
        if agg_high == agg_low:
            so = penalty_shootout(clubs[high], clubs[low], base_seed + i)
            winner = high if so["winner"] == "home" else low
            results.matches[-1]["shootout_home"] = so["home"]
            results.matches[-1]["shootout_away"] = so["away"]
        else:
            winner = high if agg_high > agg_low else low
        winners.append(winner)
        log.append({"tie": f"SF{i}", "high_seed": high, "low_seed": low,
                    "aggregate": f"{agg_high}-{agg_low}", "winner": winner})
    final = Fixture(f"{sid}-D2-PO-F", season, "Crown League Two Playoffs", 2, "playoff_final", 0,
                    final_date, winners[0], winners[1], neutral=True, home_days_rest=10,
                    away_days_rest=10)
    (_, rf), = simulate_fixtures([final], clubs, base_seed, writer, 1, results, tracker=tracker)
    if rf.home_goals == rf.away_goals:
        so = penalty_shootout(clubs[winners[0]], clubs[winners[1]], base_seed + 99)
        champion = winners[0] if so["winner"] == "home" else winners[1]
        results.matches[-1]["shootout_home"] = so["home"]
        results.matches[-1]["shootout_away"] = so["away"]
    else:
        champion = winners[0] if rf.home_goals > rf.away_goals else winners[1]
    log.append({"tie": "Final", "home": winners[0], "away": winners[1],
                "score": f"{rf.home_goals}-{rf.away_goals}", "winner": champion})
    return champion, log
