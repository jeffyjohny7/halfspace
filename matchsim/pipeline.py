"""End-to-end generation of the league universe.

Steps
-----
1. Build clubs, squads and managers; plant hidden traits (the answer key).
2. Simulate the previous season: top division + second tier, European
   midweeks, second-tier playoffs.
3. Offseason: relegation/promotion, ageing, transfers, signings, manager changes.
4. Simulate the current season up to the configured round.
5. Pick the showcase fixture and its most watchable realistic simulation.
6. Write public data, hidden truths and the realism report.
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
from dataclasses import asdict


from . import realism
from .config import SimConfig
from .engine import MatchEngine
from .names import LEAGUE_NAMES
from .season import (EventWriter, SeasonResults, apply_rest_and_rotation,
                     european_calendar, league_fixtures, match_seed, run_playoffs,
                     simulate_fixtures, standings)
from .universe import (Truth, Universe, build_universe, natural_extremes,
                       plant_traits, refresh_truths, run_offseason)


def _write_csv(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        open(path, "w").close()
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=str)


def _snapshot(u: Universe, season: str) -> dict[str, list[dict]]:
    """Public + hidden tables describing every club at the start of a season."""
    club_seasons, squads, attrs, styles = [], [], [], []
    for c in u.clubs:
        club_seasons.append({"season": season, "club_id": c.club_id, "division": c.division,
                             "competition": LEAGUE_NAMES[c.division],
                             "manager_id": c.manager.manager_id, "manager": c.manager.name,
                             "manager_philosophy": c.manager.philosophy,
                             "formation": c.formation})
        styles.append({"season": season, "club_id": c.club_id, "club": c.name,
                       "division": c.division, "quality": c.quality, **c.style()})
        for p in c.squad:
            squads.append({"season": season, "club_id": c.club_id, "player_id": p.player_id,
                           "shirt": p.shirt, "position": p.position})
            attrs.append({"season": season, "club_id": c.club_id, "player_id": p.player_id,
                          "name": p.name, "position": p.position,
                          "overall": round(p.overall, 1), **p.attrs})
    return {"club_seasons": club_seasons, "squads": squads, "attrs": attrs, "styles": styles}


def _players_public(u: Universe, seen: dict[str, dict]) -> None:
    for c in u.clubs:
        for p in c.squad:
            seen.setdefault(p.player_id, {"player_id": p.player_id, "name": p.name,
                                          "position": p.position, "birth_year": p.birth_year,
                                          "height_cm": p.height_cm,
                                          "preferred_foot": p.preferred_foot})


# ---------------------------------------------------------------------------
# Showcase selection
# ---------------------------------------------------------------------------

# (weakness on one team, things on the other team that exploit it)
_EXPLOITS = {
    "set_piece_defense_weak": {"team": ["set_piece_attack_strong"], "player": ["elite_crosser"]},
    "goalkeeper_weak_on_crosses": {"team": ["set_piece_attack_strong"], "player": ["elite_crosser"]},
    "weak_in_the_air": {"team": ["set_piece_attack_strong"], "player": ["elite_crosser"]},
    "loses_ball_under_pressure": {"team": [], "player": [], "style": "press"},
    "error_prone_passer": {"team": [], "player": [], "style": "press"},
    "high_line_exposed": {"team": [], "player": ["clinical_finisher"], "style": "counter"},
    "late_fade": {"team": [], "player": [], "style": None},
    "poor_discipline": {"team": ["set_piece_attack_strong"], "player": []},
}


def storyline_score(home, away, truths: list[Truth]) -> tuple[float, list[str]]:
    by_club: dict[str, list[Truth]] = {}
    for t in truths:
        by_club.setdefault(t.club_id, []).append(t)
    score, notes = 0.0, []
    for weak_c, strong_c in ((away, home), (home, away)):
        for t in by_club.get(weak_c.club_id, []):
            if t.direction != "weakness":
                continue
            ex = _EXPLOITS.get(t.trait, {})
            strong_traits = {s.trait for s in by_club.get(strong_c.club_id, [])}
            hit = False
            for trait in ex.get("team", []) + ex.get("player", []):
                if trait in strong_traits:
                    hit = True
                    notes.append(f"{weak_c.name}: {t.trait} vs {strong_c.name}: {trait}")
            style = ex.get("style")
            st = strong_c.style()
            if style == "press" and st.get("press_intensity", 0) > 0.7:
                hit = True
                notes.append(f"{weak_c.name}: {t.trait} vs {strong_c.name}'s high press")
            if style == "counter" and st.get("counter_focus", 0) > 0.7:
                hit = True
                notes.append(f"{weak_c.name}: {t.trait} vs {strong_c.name}'s counter-attacks")
            if t.trait == "loses_ball_under_pressure" and t.position in ("LB", "RB"):
                flank = "right_flank_focus" if t.position == "LB" else "left_flank_focus"
                if flank in strong_traits:
                    hit = True
                    notes.append(f"{weak_c.name}: {t.player_name} ({t.position}) vs "
                                 f"{strong_c.name} attacking that flank")
            score += 2.0 if hit else 0.4
    return score, notes


def narrative_score(events: list[dict], home_id: str, away_id: str, truths: list[Truth]) -> tuple[float, dict]:
    goals = [e for e in events if e["outcome"] == "goal" and e["type"] in ("shot", "own_goal")]
    hg = sum(1 for g in goals if (g["team_id"] == home_id) != (g["type"] == "own_goal"))
    ag = len(goals) - hg
    score = 0.0
    detail: dict = {"score": f"{hg}-{ag}"}
    if 2 <= len(goals) <= 5:
        score += 2
    if abs(hg - ag) <= 1:
        score += 1.5
    # Lead changes / comebacks
    lead, changes = 0, 0
    for g in goals:
        scorer_home = (g["team_id"] == home_id) != (g["type"] == "own_goal")
        new = lead + (1 if scorer_home else -1)
        if (lead > 0 > new) or (lead < 0 < new) or (lead != 0 and new == 0):
            changes += 1
        lead = new
    score += 1.5 * min(changes, 2)
    if any(g["minute"] >= 75 for g in goals):
        score += 1
    # Do the planted weaknesses actually show up in this match?
    shown = []
    for t in truths:
        if t.club_id not in (home_id, away_id) or t.direction != "weakness":
            continue
        if t.scope == "player":
            n = sum(1 for e in events if e["player_id"] == t.player_id and e["type"] == "dispossessed")
            if t.trait == "loses_ball_under_pressure" and n >= 3:
                shown.append(f"{t.player_name} dispossessed {n} times")
        elif t.trait == "set_piece_defense_weak":
            n = sum(1 for g in goals if g["team_id"] != t.club_id and g["set_piece_phase"])
            if n >= 1:
                shown.append("set-piece goal conceded")
        elif t.trait == "late_fade":
            n = sum(1 for g in goals if g["team_id"] != t.club_id and g["minute"] >= 75)
            if n >= 1:
                shown.append("late goal conceded")
    score += 1.5 * min(len(shown), 3)
    detail["weaknesses_shown"] = shown
    detail["lead_changes"] = changes
    return score, detail


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def generate(cfg: SimConfig) -> dict:
    t0 = time.time()
    out = cfg.out_dir
    pub, hid, rep = (os.path.join(out, d) for d in ("public", "hidden", "reports"))
    rng = random.Random(cfg.seed + 1)
    prev, cur = cfg.previous_season, cfg.current_season
    prev_year, cur_year = int(prev[:4]), int(cur[:4])

    print("Building universe...", flush=True)
    u = build_universe(cfg.seed, cfg.top_division_size, cfg.second_division_size)
    truths_prev = plant_traits(u.clubs, 1, prev, rng)
    truths_prev += plant_traits(u.clubs, 2, prev, rng, team_traits_per_club=(0, 1),
                                player_traits_per_club=(1, 1))
    players_seen: dict[str, dict] = {}
    _players_public(u, players_seen)
    snap_prev = _snapshot(u, prev)
    clubs = {c.club_id: c for c in u.clubs}
    names = {c.club_id: c.name for c in u.clubs}

    # ---------------- previous season
    div1 = u.division(1)
    div2 = u.division(2)
    euro_prev_q = {}
    for i, c in enumerate(sorted(div1, key=lambda c: -c.quality)[: cfg.champions_league_spots + cfg.europa_league_spots]):
        euro_prev_q[c.club_id] = "champions_league" if i < cfg.champions_league_spots else "europa_league"
    euro_prev = european_calendar(euro_prev_q, {c.club_id: c.quality for c in div1}, prev_year, rng)
    fx1 = league_fixtures(div1, prev, LEAGUE_NAMES[1], 1, prev_year, rng)
    fx2 = league_fixtures(div2, prev, LEAGUE_NAMES[2], 2, prev_year, rng)
    apply_rest_and_rotation(fx1, euro_prev)
    apply_rest_and_rotation(fx2, [])
    res_prev = SeasonResults()
    w_prev = EventWriter(os.path.join(pub, "events", f"events_{prev}.parquet"))
    print(f"Simulating {prev}: {len(fx1)} top-division + {len(fx2)} second-tier matches...", flush=True)
    simulate_fixtures(fx1 + fx2, clubs, cfg.seed, w_prev, cfg.workers, res_prev, progress=prev)
    table1 = standings(res_prev.matches, [c.club_id for c in div1], names)
    table2 = standings(res_prev.matches, [c.club_id for c in div2], names)
    po_winner, po_log = run_playoffs(table2, clubs, prev, prev_year, cfg.seed, w_prev, res_prev,
                                     cfg.playoff_places)
    w_prev.close()

    relegated = [r["club_id"] for r in table1[-cfg.relegation_spots:]]
    promoted = [r["club_id"] for r in table2[: cfg.automatic_promotion]] + [po_winner]
    # Underperformers: biggest gap between expected rank (by quality) and actual rank.
    exp_rank = {c.club_id: i for i, c in enumerate(sorted(div1, key=lambda c: -c.quality), 1)}
    gaps = sorted(((r["position"] - exp_rank[r["club_id"]], r["club_id"]) for r in table1
                   if r["club_id"] not in relegated), reverse=True)
    underperformers = [cid for _g, cid in gaps[: cfg.manager_changes]]

    # ---------------- offseason
    print("Offseason: promotion, relegation, transfers, manager changes...", flush=True)
    off_log, style_truths = run_offseason(u, relegated, promoted, underperformers, cur_year,
                                          cfg.transfers_per_summer, rng)
    for t in style_truths:
        t.season = cur
        t.truth_id = t.truth_id.replace(str(cur_year), cur, 1)
    truths_cur = refresh_truths(truths_prev, u.clubs, cur) + style_truths
    planted_ids = {t.player_id for t in truths_cur if t.player_id}
    truths_cur += natural_extremes(u.clubs, cur, planted_ids)
    _players_public(u, players_seen)
    snap_cur = _snapshot(u, cur)

    # ---------------- current season
    div1 = u.division(1)
    euro_cur_q = {}
    for r in table1[: cfg.champions_league_spots]:
        if r["club_id"] in {c.club_id for c in div1}:
            euro_cur_q[r["club_id"]] = "champions_league"
    for r in table1[cfg.champions_league_spots: cfg.champions_league_spots + cfg.europa_league_spots]:
        euro_cur_q[r["club_id"]] = "europa_league"
    euro_cur = european_calendar(euro_cur_q, {c.club_id: c.quality for c in div1}, cur_year, rng)
    fx_cur_all = league_fixtures(div1, cur, LEAGUE_NAMES[1], 1, cur_year, rng,
                                 rounds_limit=cfg.showcase_round)
    apply_rest_and_rotation(fx_cur_all, euro_cur)
    played = [f for f in fx_cur_all if f.round <= cfg.current_rounds_played]
    upcoming = [f for f in fx_cur_all if f.round == cfg.showcase_round]
    res_cur = SeasonResults()
    w_cur = EventWriter(os.path.join(pub, "events", f"events_{cur}.parquet"))
    print(f"Simulating {cur} rounds 1-{cfg.current_rounds_played}: {len(played)} matches...", flush=True)
    simulate_fixtures(played, clubs, cfg.seed, w_cur, cfg.workers, res_cur, progress=cur)
    w_cur.close()
    table_cur = standings(res_cur.matches, [c.club_id for c in div1], names)

    # ---------------- showcase
    print("Choosing the showcase match...", flush=True)
    scored = []
    for f in upcoming:
        s, notes = storyline_score(clubs[f.home_id], clubs[f.away_id], truths_cur)
        pos = {r["club_id"]: r["position"] for r in table_cur}
        s += 1.0 if pos[f.home_id] <= 8 and pos[f.away_id] <= 8 else 0.0
        scored.append((s, f, notes))
    scored.sort(key=lambda t: -t[0])
    _s, show_fx, show_notes = scored[0]
    variants = []
    best = None
    for k in range(cfg.showcase_variants):
        seed = match_seed(cfg.seed + 7919 * (k + 1), show_fx.match_id)
        eng = MatchEngine(show_fx.match_id, clubs[show_fx.home_id], clubs[show_fx.away_id], seed,
                          home_fatigue=show_fx.home_fatigue, away_fatigue=show_fx.away_fatigue,
                          home_rotation=show_fx.home_rotation, away_rotation=show_fx.away_rotation)
        r = eng.simulate()
        ns, detail = narrative_score(r.events, show_fx.home_id, show_fx.away_id, truths_cur)
        variants.append({"variant": k, "seed": seed, "narrative_score": ns, **detail})
        if best is None or ns > best[0]:
            best = (ns, r, k)
    _ns, show_res, show_k = best
    show_dir = os.path.join(pub, "showcase")
    sw = EventWriter(os.path.join(show_dir, "showcase_events.parquet"))
    sw.write(show_res.events)
    sw.close()
    show_meta = {
        "match_id": show_fx.match_id, "season": cur, "round": show_fx.round,
        "date": show_fx.date.isoformat(), "home_id": show_fx.home_id, "away_id": show_fx.away_id,
        "home": names[show_fx.home_id], "away": names[show_fx.away_id],
        "home_formation": show_res.home_formation, "away_formation": show_res.away_formation,
        "home_days_rest": show_fx.home_days_rest, "away_days_rest": show_fx.away_days_rest,
        "home_midweek_europe": show_fx.home_midweek_europe,
        "away_midweek_europe": show_fx.away_midweek_europe,
        "note": "Stream showcase_events.parquet in clock order to simulate the live feed. "
                "Do not show it to the Scout before kick-off.",
    }
    show_lineups = [{**row, "season": cur} for row in show_res.lineups]

    # ---------------- write public data
    print("Writing data...", flush=True)
    _write_json(os.path.join(pub, "league.json"), {
        "leagues": {str(k): v for k, v in LEAGUE_NAMES.items()},
        "seasons": [prev, cur],
        "rules": {"points_for_win": 3, "relegation_spots": cfg.relegation_spots,
                  "automatic_promotion": cfg.automatic_promotion,
                  "playoff_places": list(cfg.playoff_places),
                  "champions_league_spots": cfg.champions_league_spots,
                  "europa_league_spots": cfg.europa_league_spots},
        "coordinates": "Events use the acting team's frame: x 0->105 own goal to opponent goal, "
                       "y 0->68 right touchline to left touchline. See matchsim.schema.to_absolute.",
        "current_round_completed": cfg.current_rounds_played,
        "showcase_round": cfg.showcase_round,
    })
    _write_csv(os.path.join(pub, "clubs.csv"), [
        {"club_id": c.club_id, "name": c.name, "short_name": c.short_name, "town": c.town,
         "stadium": c.stadium, "kit_primary": c.colours[0], "kit_secondary": c.colours[1]}
        for c in u.clubs])
    _write_csv(os.path.join(pub, "club_seasons.csv"), snap_prev["club_seasons"] + snap_cur["club_seasons"])
    _write_csv(os.path.join(pub, "players.csv"), list(players_seen.values()))
    _write_csv(os.path.join(pub, "squads.csv"), snap_prev["squads"] + snap_cur["squads"])
    _write_csv(os.path.join(pub, "matches.csv"), res_prev.matches + res_cur.matches)
    _write_csv(os.path.join(pub, "lineups.csv"), res_prev.lineups + res_cur.lineups)
    st_rows = ([{"season": prev, "division": 1, "after_round": 38, **r} for r in table1]
               + [{"season": prev, "division": 2, "after_round": 46, **r} for r in table2]
               + [{"season": cur, "division": 1, "after_round": cfg.current_rounds_played, **r}
                  for r in table_cur])
    _write_csv(os.path.join(pub, "standings.csv"), st_rows)
    _write_csv(os.path.join(pub, "european_fixtures.csv"),
               [{"season": prev, **r} for r in euro_prev] + [{"season": cur, **r} for r in euro_cur])
    _write_csv(os.path.join(pub, "upcoming_fixtures.csv"),
               [{"match_id": f.match_id, "season": f.season, "round": f.round, "date": f.date.isoformat(),
                 "home_id": f.home_id, "away_id": f.away_id, "home_days_rest": f.home_days_rest,
                 "away_days_rest": f.away_days_rest} for f in upcoming])
    _write_json(os.path.join(pub, "offseason.json"), {
        "season_from": prev, "season_to": cur,
        "relegated": [{"club_id": c, "club": names[c]} for c in relegated],
        "promoted": [{"club_id": c, "club": names[c],
                      "route": "playoffs" if c == po_winner else "automatic"} for c in promoted],
        "playoffs": po_log,
        "european_places": [{"club_id": c, "club": names[c], "competition": comp}
                            for c, comp in euro_cur_q.items()],
        **asdict(off_log),
    })
    _write_json(os.path.join(show_dir, "showcase_match.json"), show_meta)
    _write_csv(os.path.join(show_dir, "showcase_lineups.csv"), show_lineups)

    # ---------------- write hidden truths
    _write_json(os.path.join(hid, "answer_key.json"), {
        "warning": "HIDDEN. Never expose this folder to agents. Used only to score their insights.",
        "seasons": {prev: [asdict(t) for t in truths_prev], cur: [asdict(t) for t in truths_cur]},
    })
    _write_csv(os.path.join(hid, "player_attributes.csv"), snap_prev["attrs"] + snap_cur["attrs"])
    _write_csv(os.path.join(hid, "team_styles.csv"), snap_prev["styles"] + snap_cur["styles"])
    _write_json(os.path.join(hid, "showcase_selection.json"), {
        "fixture_candidates": [{"match_id": f.match_id, "home": names[f.home_id], "away": names[f.away_id],
                                "storyline_score": round(s, 2), "matchups": n} for s, f, n in scored],
        "chosen_fixture": show_fx.match_id, "matchups": show_notes,
        "chosen_variant": show_k, "variants": variants,
        "disclosure": "The showcase match is the most watchable of N realistic simulations of the same "
                      "fixture. All historical matches are single, unselected simulations.",
    })

    # ---------------- realism report
    print("Building realism report...", flush=True)
    report = realism.build_report(out, prev, cur, truths_prev, truths_cur)
    elapsed = time.time() - t0
    summary = {
        "elapsed_s": round(elapsed, 1),
        "matches": len(res_prev.matches) + len(res_cur.matches),
        "events": w_prev.rows + w_cur.rows,
        "champion": table1[0]["club"], "champion_points": table1[0]["points"],
        "relegated": [names[c] for c in relegated],
        "promoted": [names[c] for c in promoted],
        "showcase": f"{names[show_fx.home_id]} vs {names[show_fx.away_id]} "
                    f"(round {show_fx.round}, variant {show_k})",
        "truths": {prev: len(truths_prev), cur: len(truths_cur)},
        "realism_checks_passed": f"{report['passed']}/{report['total']}",
    }
    _write_json(os.path.join(rep, "run_summary.json"), summary)
    return summary
