"""One facade over the analytics package. The MCP server and the agents call this.

All methods return JSON-safe dicts/lists. Clubs and players can be passed by id
("C02", "P00032") or by name ("Dunvarrow", "Emil Varailo").
"""

from __future__ import annotations

import difflib
import threading

from . import availability, profiles
from .live import LiveMatch, _event_rows
from .matchup import matchup_report
from .metrics import PLAYER_METRICS, TEAM_METRICS
from .profiles import POSITION_KEY_METRICS
from .scout import PLAYER_CHECKS, TEAM_CHECKS, Scout
from .store import Store
from .util import clean, competition_name, public_rules


class NotFound(ValueError):
    pass


class Analyst:
    def __init__(self, data_dir: str = "data"):
        self.store = Store(data_dir)
        self.scout = Scout(self.store)
        self._live: LiveMatch | None = None
        self._showcase_report: dict | None = None
        self.lock = threading.RLock()

    # ------------------------------------------------------------------ resolution
    def club_id(self, club: str) -> str:
        names = self.store.club_names
        if club in names:
            return club
        q = club.strip().lower()
        hits = [cid for cid, n in names.items() if q == n.lower()] or \
               [cid for cid, n in names.items() if q in n.lower()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise NotFound(f"'{club}' matches several clubs: {', '.join(names[h] for h in hits)}")
        close = difflib.get_close_matches(club, list(names.values()), n=3)
        raise NotFound(f"No club '{club}'." + (f" Did you mean: {', '.join(close)}?" if close else ""))

    def player_id(self, player: str) -> str:
        names = self.store.player_names
        if player in names:
            return player
        q = player.strip().lower()
        hits = [pid for pid, n in names.items() if q == n.lower()] or \
               [pid for pid, n in names.items() if q in n.lower()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise NotFound(f"'{player}' matches several players: "
                           + ", ".join(f"{names[h]} ({h})" for h in hits[:8]))
        close = difflib.get_close_matches(player, list(names.values()), n=3)
        raise NotFound(f"No player '{player}'." + (f" Did you mean: {', '.join(close)}?" if close else ""))

    def season(self, season: str | None) -> str:
        """Accepts 'current', 'previous'/'last', '2026-27', '2026/27', '2026-2027', '26-27', '2026'."""
        s = (season or "").strip().lower().replace("/", "-").replace(" season", "")
        if s in ("", "current", "this", "now", "latest", "none", "null"):
            return self.store.current_season
        if s in ("previous", "last", "prev"):
            return self.store.previous_season
        for full in self.store.seasons:
            a, b = full.split("-")
            if s in (full, f"{a}-20{b}", f"{a[2:]}-{b}", a):
                return full
        if season not in self.store.seasons:
            raise NotFound(f"Unknown season {season}. Seasons: {', '.join(self.store.seasons)}")
        return season

    # ------------------------------------------------------------------ league
    def overview(self) -> dict:
        s = self.store
        cur = s.current_season
        table = profiles.league_table(s, cur, 1)["table"]
        off = s.offseason
        meta = s.showcase_meta
        changes = [{"club": s.club_name(m["club_id"]), "new_manager": m["new_manager"], "old_manager": m["old_manager"],
                    "formation": f"{m['old_formation']} -> {m['new_formation']}"} for m in off["manager_changes"]]
        return clean({
            "leagues": s.league["leagues"], "seasons": s.seasons, "current_season": cur,
            "rounds_played": s.league["current_round_completed"], "rules": public_rules(s.league["rules"]),
            "top_of_table": table[:6], "bottom_of_table": table[-3:],
            "last_summer": {"relegated": [r["club"] for r in off["relegated"]],
                            "promoted": [f"{r['club']} ({r['route']})" for r in off["promoted"]],
                            "european_places": [f"{r['club']} ({competition_name(r['competition'])})"
                                                for r in off["european_places"]],
                            "manager_changes": changes, "transfers": len(off["transfers"])},
            "showcase_fixture": {"match_id": meta["match_id"], "home": meta["home"], "away": meta["away"],
                                 "date": meta["date"], "round": meta["round"]},
            "note": "All clubs, players and competitions are fictional and synthetic.",
        })

    def league_table(self, season: str | None = None, division: int = 1, after_round: int | None = None) -> dict:
        return clean(profiles.league_table(self.store, self.season(season), division, after_round))

    def search(self, query: str, limit: int = 10) -> dict:
        q = query.strip().lower()
        clubs = [{"club_id": c, "name": n} for c, n in self.store.club_names.items() if q in n.lower()]
        pl = self.store.players
        hits = pl[pl.name.str.lower().str.contains(q, regex=False)].head(limit)
        players = []
        for r in hits.itertuples():
            players.append({"player_id": r.player_id, "name": r.name, "position": r.position,
                            "club": self.store.club_name(self.store.player_club(r.player_id, self.store.current_season)
                                                         or self.store.player_club(r.player_id, self.store.previous_season) or "")})
        return {"clubs": clubs[:limit], "players": players}

    def upcoming_fixtures(self) -> list[dict]:
        up = self.store.upcoming
        return clean([{"match_id": r.match_id, "round": int(r.round), "date": r.date, "home": self.store.club_name(r.home_id),
                       "home_id": r.home_id, "away": self.store.club_name(r.away_id), "away_id": r.away_id,
                       "showcase": r.match_id == self.store.showcase_meta["match_id"]} for r in up.itertuples()])

    # ------------------------------------------------------------------ clubs and players
    def club_profile(self, club: str, season: str | None = None, venue: str = "all", last_n: int | None = None) -> dict:
        return profiles.club_profile(self.store, self.club_id(club), self.season(season), venue, last_n)

    def goals_breakdown(self, club: str, side: str = "conceded", season: str | None = None, venue: str = "all",
                        max_goals_listed: int = 25) -> dict:
        out = profiles.goals_breakdown(self.store, self.club_id(club), side, self.season(season), venue)
        out["goals_list"] = out["goals_list"][-max_goals_listed:]
        return out

    def player_profile(self, player: str, season: str | None = None) -> dict:
        pid = self.player_id(player)
        out = profiles.player_profile(self.store, self.scout.player_cmp, pid, self.season(season))
        club = self.store.player_club(pid, self.store.current_season)
        out["availability"] = availability.player_status(self.store, pid, club)
        inj = availability.injuries(self.store, player_id=pid, season="all")
        out["injury_record"] = {"injuries": inj.get("count", 0), "by_type": inj.get("by_type", {}),
                                "latest": (inj.get("injuries") or [None])[0]}
        out["match_ratings"] = self.rating_summary(pid)
        return out

    def rating_summary(self, pid: str) -> dict:
        """A player's match ratings per season: average, best, last five (rating.py explains the scale)."""
        pr = self.store.player_ratings
        me = pr[pr.player_id.astype(str) == pid]
        if me.empty:
            return {}
        m = self.store.matches.set_index("match_id")
        out = {}
        for season, g in me.groupby("season"):
            g = g.join(m[["date", "home_id", "away_id"]], on="match_id").sort_values("date")
            opp = [self.store.club_name(h if t != h else a) for t, h, a in zip(g.team_id, g.home_id, g.away_id)]
            rows = [{"date": d, "opponent": o, "rating": round(float(r), 1)} for d, o, r in zip(g.date, opp, g.rating)]
            best = max(rows, key=lambda x: x["rating"])
            out[season] = {"matches": len(rows), "average": round(float(g.rating.mean()), 2), "best": best,
                           "last_5": rows[-5:]}
        return out

    # ------------------------------------------------------------------ team news, injuries, line-ups
    def team_news(self, club: str, match_id: str | None = None) -> dict:
        return availability.team_news(self.store, self.club_id(club), match_id)

    def injuries(self, club: str | None = None, player: str | None = None, season: str | None = None) -> dict:
        season = "all" if season == "all" else self.season(season)
        out = availability.injuries(self.store, self.club_id(club) if club else None,
                                    self.player_id(player) if player else None, season)
        if club:
            out["suspensions"] = availability.suspensions(self.store, self.club_id(club),
                                                          None if season == "all" else season)
        return out

    def match_lineup(self, club: str, match_id: str = "last", season: str | None = None) -> dict:
        out = availability.match_lineup(self.store, self.club_id(club), match_id or "last",
                                        self.season(season) if season else None)
        if "error" in out:
            raise NotFound(out["error"])
        return out

    def player_event_map(self, player: str, season: str | None = None,
                         kinds: tuple[str, ...] = ("dispossessed", "turnover")) -> dict:
        return profiles.player_event_map(self.store, self.player_id(player), self.season(season), kinds)

    def squad_report(self, club: str, season: str | None = None) -> dict:
        cid, season = self.club_id(club), self.season(season)
        ps = self.scout.ps
        sq = ps[(ps.season == season) & (ps.team_id == cid)].sort_values("minutes", ascending=False)
        players = []
        for r in sq.itertuples():
            metrics = {}
            for m in POSITION_KEY_METRICS.get(r.position, []):
                cmp_ = self.scout.player_cmp(m)
                if (season, r.player_id) in cmp_.index:
                    c = cmp_.loc[(season, r.player_id)]
                    metrics[m] = {"value": c.raw, "percentile": c.percentile}
            players.append({"player_id": r.player_id, "name": r.name, "position": r.position, "minutes": r.minutes,
                            "starts": r.starts, "goals": r.goals, "assists": r.assists, "key_metrics": metrics})
        return clean({"club": self.store.club_name(cid), "season": season, "players": players,
                      "note": "Percentiles compare with the same position in the same division."})

    def scout_findings(self, club: str, season: str | None = None, kind: str = "all",
                       min_confidence: str = "medium", limit: int = 15) -> dict:
        cid, season = self.club_id(club), self.season(season)
        f = self.scout.findings(cid, season, kind=kind, min_confidence=min_confidence)
        return clean({"club": self.store.club_name(cid), "season": season, "count": len(f), "findings": f[:limit],
                      "confidence_guide": {"high": "headline: safe to state on screen",
                                           "medium": "watch list: frame as something to watch, verify live",
                                           "low": "weak signal: do not state as fact"}})

    def head_to_head(self, club_a: str, club_b: str) -> dict:
        return clean(profiles.head_to_head(self.store, self.club_id(club_a), self.club_id(club_b)))

    def matchup(self, home: str, away: str, season: str | None = None, match_id: str | None = None,
                compact: bool = False) -> dict:
        h, a = self.club_id(home), self.club_id(away)
        rep = matchup_report(self.store, self.scout, h, a, self.season(season), match_id)
        return compact_matchup(rep) if compact else rep

    # ------------------------------------------------------------------ live (showcase match)
    @property
    def live(self) -> LiveMatch:
        if self._live is None:
            self._live = LiveMatch.showcase(self.store)
        return self._live

    def showcase_report(self) -> dict:
        if self._showcase_report is None:
            m = self.store.showcase_meta
            self._showcase_report = self.matchup(m["home_id"], m["away_id"], match_id=m["match_id"])
        return self._showcase_report

    def live_state(self, clock_s: float) -> dict:
        return self.live.state(clock_s)

    def live_key_moments(self, clock_s: float, since_s: float = 0.0, min_importance: float = 0.3) -> list[dict]:
        return self.live.key_moments(clock_s, since_s, min_importance)

    def live_predictions(self, clock_s: float) -> list[dict]:
        return self.live.track(self.showcase_report()["predictions_to_track"], clock_s)

    def live_player(self, player: str, clock_s: float) -> dict:
        return self.live.player(self.player_id(player), clock_s)

    def live_ratings(self, clock_s: float) -> dict:
        return self.live.ratings(clock_s)

    # ------------------------------------------------------------------ evidence
    def get_events(self, match_id: str, event_ids: list[int], clock_s: float | None = None) -> list[dict]:
        if match_id == self.store.showcase_meta["match_id"]:
            if clock_s is None:
                raise NotFound("For the live match pass clock_s (events after the current clock are not available).")
            return self.live.events(event_ids, clock_s)
        prefix = match_id.split("-")[0]
        season = next((s for s in self.store.seasons if s.replace("-", "") == prefix), None)
        if season is None:
            raise NotFound(f"Unknown match {match_id}")
        ev = self.store.events(season, match_ids=[match_id])
        ev = ev[ev.event_id.isin([int(e) for e in event_ids])]
        if ev.empty:
            raise NotFound(f"No such events in {match_id}")
        return _event_rows(self.store, ev)

    def glossary(self) -> dict:
        return {
            "player_metrics": {k: {"label": m.label, "better": m.better, "adjusted_for_team": m.team_adjust}
                               for k, m in PLAYER_METRICS.items()},
            "team_metrics": {k: {"label": v[0], "better": v[1]} for k, v in TEAM_METRICS.items()},
            "finding_categories": sorted({c.category for c in PLAYER_CHECKS} | {c.category for c in TEAM_CHECKS}
                                         | {"style_change_press_intensity", "style_change_directness"}),
            "terms": {
                "xG": "Expected goals: chance a shot from that spot becomes a goal (location model).",
                "xT": "Expected threat: how much a pass or carry raises the chance of scoring soon, learned from last "
                      "season's league data.",
                "PPDA": "Opponent passes per defensive action in their own 60% of the pitch. Lower = more pressing.",
                "field tilt": "Share of final-third passes. Who is camped in whose half.",
                "match rating": "0-10 player rating. Everyone starts at 6.0 and each action adds or removes a fixed "
                                "amount: goal +1.0, assist +0.6, key pass +0.12, misplaced pass -0.035, tackle +0.1, "
                                "save +0.2 plus the shot's xG... An ordinary game is 6.5-7, a standout one 8.5+.",
                "pass difficulty": "Chance an average passer would fail that pass in that context (0-1).",
                "z": "Robust z-score vs peers (same position and division): how unusual the player or team is.",
                "chaos index": "0-100. How end-to-end the last 10 minutes were vs every 10-minute spell last season.",
            },
            "phases": profiles.PHASE_LABELS,
            "coordinates": self.store.league["coordinates"],
        }


def _form_string(rows: list[dict]) -> str:
    return "".join(r["result"] for r in rows)


def compact_matchup(rep: dict) -> dict:
    """A smaller matchup report for agent context windows (about a quarter of the full size)."""
    fx = rep["fixture"]
    home, away = fx["home"], fx["away"]
    style = [{"metric": r["label"], home: r["home"], f"{home} pct": r["home_percentile"],
              away: r["away"], f"{away} pct": r["away_percentile"], "league median": r["league_median"]}
             for r in rep["style_comparison"]]
    return clean({
        "fixture": fx,
        "context": rep["context"],
        "form": {f"{home} last 5": _form_string(rep["form"]["home_overall"]),
                 f"{home} last 5 at home": _form_string(rep["form"]["home_at_home"]),
                 f"{away} last 5": _form_string(rep["form"]["away_overall"]),
                 f"{away} last 5 away": _form_string(rep["form"]["away_on_the_road"])},
        "head_to_head": [f"{m['season']} {m['home']} {m['score']} {m['away']} (xG {m['xg']})" for m in rep["head_to_head"]],
        "style_comparison": style,
        "edges": [{"edge_id": e["edge_id"], "beneficiary": e["beneficiary"], "title": e["title"],
                   "strength": e["strength"], "explanation": e["explanation"],
                   "supporting_findings": e["supporting_findings"],
                   **({"team_news_note": e["team_news_note"]} if e.get("team_news_note") else {})}
                  for e in rep["edges"]],
        "team_news": {club: {"summary": n.get("summary"),
                             "out": [f"{x['player']} ({x['position']}, {x['status']}: {x['reason']})"
                                     for x in n.get("unavailable") or []],
                             "doubtful": [f"{x['player']} ({x['position']}: {x['reason']})"
                                          for x in n.get("doubtful") or []]}
                      for club, n in rep.get("team_news", {}).items()},
        "edges_dropped_for_team_news": rep.get("edges_dropped_for_team_news", []),
        "predictions_to_track": [{"prediction_id": p["prediction_id"], "text": p["text"]}
                                 for p in rep["predictions_to_track"]],
        "key_players": {club: sorted({f"{k['name']} ({k['position']})" for k in ks})
                        for club, ks in rep["key_players"].items()},
        "probable_lineups": {club: {"formation": x.get("formation"),
                                    "players": [f"{p['name']} ({p['slot']}{', doubtful' if p.get('doubtful') else ''})"
                                                for p in x.get("players", [])],
                                    "changes": [f"{c['in']} for {c['out']} ({c['reason']})" for c in x.get("changes", [])]}
                             for club, x in rep["probable_lineups"].items()},
        "findings": {club: [f"[{f['confidence']}] {f['summary']}" for f in fs] for club, fs in rep["findings"].items()},
        "note": "Compact view. Use scout_findings / goals_breakdown / player_profile for evidence and detail.",
    })

