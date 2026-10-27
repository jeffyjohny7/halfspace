"""Team news, injuries, suspensions and line-ups."""

from __future__ import annotations

import pandas as pd

from .store import Store
from .util import clean


def _club_next_match(store: Store, club_id: str) -> dict | None:
    up = store.upcoming
    row = up[(up.home_id == club_id) | (up.away_id == club_id)]
    if row.empty:
        return None
    r = row.iloc[0]
    home = r.home_id == club_id
    return {"match_id": r.match_id, "date": r.date, "round": int(r["round"]), "venue": "home" if home else "away",
            "opponent_id": r.away_id if home else r.home_id,
            "opponent": store.club_name(r.away_id if home else r.home_id)}


def _starts(store: Store, club_id: str, season: str, last_n: int = 5) -> dict[str, int]:
    m = store.matches
    m = m[(m.season == season) & (m.stage == "league") & ((m.home_id == club_id) | (m.away_id == club_id))]
    ids = list(m.sort_values("date").match_id.tail(last_n))
    lu = store.lineups
    lu = lu[lu.match_id.isin(ids) & (lu.team_id == club_id) & (lu.started == True)]  # noqa: E712
    return lu.groupby("player_id").size().to_dict()


def _season_minutes(store: Store, club_id: str, season: str) -> dict[str, float]:
    lu = store.lineups
    lu = lu[(lu.season == season) & (lu.team_id == club_id)]
    return lu.groupby("player_id").minutes.sum().to_dict()


def team_news(store: Store, club_id: str, match_id: str | None = None) -> dict:
    """The club's published team news before a match (default: its next match)."""
    tn = store.team_news
    fixture = None
    if match_id is None:
        fixture = _club_next_match(store, club_id)
        match_id = fixture["match_id"] if fixture else None
    if tn.empty or match_id is None:
        return {"club": store.club_name(club_id), "match_id": match_id, "available": True, "unavailable": [],
                "doubtful": [], "note": "No team news published."}
    rows = tn[(tn.match_id == match_id) & (tn.club_id == club_id)]
    if fixture is None:
        mm = store.matches[store.matches.match_id == match_id]
        if len(mm):
            r = mm.iloc[0]
            home = r.home_id == club_id
            fixture = {"match_id": match_id, "date": r.date, "round": int(r["round"]),
                       "venue": "home" if home else "away",
                       "opponent": store.club_name(r.away_id if home else r.home_id)}
    season = rows.season.iloc[0] if len(rows) else store.current_season
    starts = _starts(store, club_id, season)
    mins = _season_minutes(store, club_id, season)
    out, doubt = [], []
    for r in rows.itertuples():
        item = {"player_id": r.player_id, "player": store.player_name(r.player_id),
                "position": store.player_positions.get(r.player_id), "reason": r.reason,
                "since": r.since, "expected_return": None if pd.isna(r.expected_return) else r.expected_return,
                "matches_remaining": None if pd.isna(r.matches_remaining) else int(r.matches_remaining),
                "starts_in_last_5": int(starts.get(r.player_id, 0)),
                "season_minutes": int(mins.get(r.player_id, 0))}
        item["regular_starter"] = item["starts_in_last_5"] >= 3
        (doubt if r.status == "doubtful" else out).append({**item, "status": r.status})
    out.sort(key=lambda x: (-x["starts_in_last_5"], -x["season_minutes"]))
    key = [x["player"] for x in out if x["regular_starter"]]
    summary = (f"{len(out)} out" + (f" ({', '.join(key)} regular starters)" if key else "")
               + (f", {len(doubt)} doubtful" if doubt else ""))
    return clean({"club": store.club_name(club_id), "club_id": club_id, "fixture": fixture, "summary": summary,
                  "unavailable": out, "doubtful": doubt,
                  "note": "Doubtful players face a late fitness test. Expected return dates are the club's estimate."})


def injuries(store: Store, club_id: str | None = None, player_id: str | None = None,
             season: str | None = None) -> dict:
    inj = store.injuries
    if inj.empty:
        return {"injuries": [], "count": 0}
    season = season or store.current_season
    df = inj[inj.season == season] if season != "all" else inj
    if club_id:
        df = df[df.club_id == club_id]
    if player_id:
        df = df[df.player_id == player_id] if season == "all" else inj[inj.player_id == player_id]
    df = df.sort_values("date", ascending=False)
    rows = [{"injury_id": r.injury_id, "date": r.date, "player": store.player_name(r.player_id),
             "club": store.club_name(r.club_id), "injury": r.injury, "severity": r.severity,
             "cause": {"contact": "in a match (challenge)", "non_contact": "in a match (muscle)",
                       "training": "training or illness"}.get(r.cause, r.cause),
             "match_id": None if pd.isna(r.match_id) else r.match_id,
             "minute": None if pd.isna(r.minute) else int(r.minute),
             "expected_return": r.expected_return,
             "returned": None if pd.isna(r.return_date) else r.return_date,
             "days_out": int(r.days_out) if not pd.isna(r.return_date) else None}
            for r in df.itertuples()]
    done = df[df.return_date.notna()]
    return clean({
        "season": season, "club": store.club_name(club_id) if club_id else None,
        "player": store.player_name(player_id) if player_id else None,
        "count": len(df),
        "by_type": df.injury.value_counts().head(8).to_dict(),
        "days_lost_completed": int(done.days_out.sum()) if len(done) else 0,
        "still_out": int(df.return_date.isna().sum()),
        "injuries": rows[:40],
    })


def suspensions(store: Store, club_id: str | None = None, season: str | None = None) -> list[dict]:
    s = store.suspensions
    if s.empty:
        return []
    season = season or store.current_season
    s = s[s.season == season]
    if club_id:
        s = s[s.club_id == club_id]
    return [{"player": store.player_name(r.player_id), "club": store.club_name(r.club_id), "date": r.date,
             "reason": r.reason, "matches": int(r.matches), "after_match": r.match_id} for r in s.itertuples()]


def player_status(store: Store, player_id: str, club_id: str | None) -> dict:
    """Current availability for a player (from his club's latest team news)."""
    if not club_id:
        return {"status": "unknown"}
    news = team_news(store, club_id)
    for group in ("unavailable", "doubtful"):
        for x in news.get(group, []):
            if x["player_id"] == player_id:
                return {"status": x["status"], "reason": x["reason"], "expected_return": x.get("expected_return"),
                        "matches_remaining": x.get("matches_remaining")}
    return {"status": "available"}


def match_lineup(store: Store, club_id: str, match_id: str = "last", season: str | None = None) -> dict:
    """Starting XI, substitutions, cards and injuries for one of the club's matches."""
    m = store.matches
    m = m[(m.home_id == club_id) | (m.away_id == club_id)]
    if match_id == "last":
        season = season or store.current_season
        m = m[m.season == season].sort_values("date")
        if m.empty:
            return {"error": "No matches yet this season."}
        row = m.iloc[-1]
    else:
        m = m[m.match_id == match_id]
        if m.empty:
            return {"error": f"{store.club_name(club_id)} did not play match {match_id}."}
        row = m.iloc[0]
    mid = row.match_id
    home = row.home_id == club_id
    lu = store.lineups
    lu = lu[(lu.match_id == mid) & (lu.team_id == club_id)]
    start = lu[lu.started == True]  # noqa: E712
    subs = lu[(lu.started == False) & lu.minute_on.notna()]  # noqa: E712
    rested = lu[lu.get("rested", pd.Series(False, index=lu.index)).fillna(False).astype(bool)] if "rested" in lu else lu.iloc[0:0]
    inj = store.injuries
    inj = inj[(inj.match_id == mid) & (inj.club_id == club_id)] if not inj.empty else inj

    def name(pid):
        return store.player_name(pid)

    pr = store.player_ratings
    rated = dict(zip(pr[pr.match_id == mid].player_id.astype(str), pr[pr.match_id == mid].rating.round(1)))

    xi = [{"player": name(r.player_id), "slot": r.slot, "position": r.position,
           "minutes": int(r.minutes), "off_at": None if r.minutes >= 90 or pd.isna(r.minute_off) else int(r.minute_off),
           "yellow": int(r.yellow or 0), "red": bool(r.red), "rating": rated.get(str(r.player_id))}
          for r in start.itertuples()]
    bench = [{"player": name(r.player_id), "position": r.position, "on_at": int(r.minute_on),
              "replaced_in_slot": r.slot, "yellow": int(r.yellow or 0), "red": bool(r.red),
              "rating": rated.get(str(r.player_id))} for r in subs.itertuples()]
    gf, ga = (row.home_goals, row.away_goals) if home else (row.away_goals, row.home_goals)
    news = team_news(store, club_id, mid)
    return clean({
        "match_id": mid, "date": row.date, "season": row.season, "round": int(row["round"]),
        "venue": "home" if home else "away", "opponent": store.club_name(row.away_id if home else row.home_id),
        "score": f"{int(gf)}-{int(ga)}", "result": "W" if gf > ga else ("D" if gf == ga else "L"),
        "formation": row.home_formation if home else row.away_formation,
        "starting_xi": xi, "substitutes_used": bench,
        "rested": [name(r.player_id) for r in rested.itertuples()],
        "injured_in_match": [{"player": name(r.player_id), "minute": None if pd.isna(r.minute) else int(r.minute),
                              "injury": r.injury} for r in inj.itertuples()] if len(inj) else [],
        "missing_before_kickoff": [{"player": x["player"], "status": x["status"], "reason": x["reason"]}
                                   for x in news.get("unavailable", []) + news.get("doubtful", [])],
    })


def probable_xi(store: Store, club_id: str, season: str) -> dict:
    """Last league XI, with injured or suspended players replaced by the next man in that position."""
    tm = store.table("team_match")
    last = tm[(tm.team_id == club_id) & (tm.season == season) & (tm.stage == "league")].sort_values("date").tail(1)
    if last.empty:
        return {}
    mid = last.match_id.iloc[0]
    lu = store.lineups
    xi = lu[(lu.match_id == mid) & (lu.team_id == club_id) & (lu.started == True)]  # noqa: E712
    news = team_news(store, club_id)
    out = {x["player_id"]: x for x in news.get("unavailable", [])}
    doubt = {x["player_id"] for x in news.get("doubtful", [])}
    mins = _season_minutes(store, club_id, season)
    sq = store.squads
    squad = sq[(sq.club_id == club_id) & (sq.season == season)]
    used = set(xi.player_id)
    players, changes = [], []
    for r in xi.itertuples():
        pid = r.player_id
        if pid in out:
            options = [p for p in squad.itertuples() if p.position == r.position and p.player_id not in used
                       and p.player_id not in out]
            if not options:
                options = [p for p in squad.itertuples() if p.player_id not in used and p.player_id not in out
                           and (p.position == "GK") == (r.position == "GK")]
            if options:
                rep = max(options, key=lambda p: mins.get(p.player_id, 0))
                used.add(rep.player_id)
                changes.append({"out": store.player_name(pid), "reason": out[pid]["reason"],
                                "in": store.player_name(rep.player_id)})
                pid = rep.player_id
        players.append({"player_id": pid, "name": store.player_name(pid), "slot": r.slot,
                        "position": store.player_positions.get(pid, r.position),
                        "doubtful": pid in doubt})
    return {"based_on_match": mid, "formation": last.formation.iloc[0], "players": players, "changes": changes}
