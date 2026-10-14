# Inside the Game — synthetic league engine (`matchsim`)

A fictional, football-realistic league universe for the Microsoft × Premier League
*Inside the Game* hackathon. It generates two seasons of event-level match data,
complete with promotion and relegation, European midweeks, transfers and manager
changes, plus a hidden **answer key** of planted strengths and weaknesses so we
can score whether our AI agents actually discover them.

All clubs, players, managers and competitions are invented. No real names,
logos or match data are used.

## Quick start

```powershell
uv add numpy pandas pyarrow
uv add --dev pytest
uv run scripts/generate.py      # about 1-2 minutes, uses all CPU cores
uv run pytest -q                # 11 tests
```

Options: `--seed 7` (a different universe), `--workers 4`, `--rounds-played 10`,
`--cl-spots 4` (no European Performance Spot that year).

## What gets generated

```
data/
  public/                      what agents and the app may read
    league.json                rules, seasons, coordinate system
    clubs.csv                  44 clubs: name, town, stadium, kit colours
    club_seasons.csv           division, manager, philosophy, formation per season
    players.csv / squads.csv   players and which club they were at each season
    matches.csv                every match: score, formations, rest days, Europe midweek flags
    lineups.csv                starters, subs, minutes, cards, rotated players
    standings.csv              final 2025-26 tables (both divisions) + 2026-27 after round 10
    european_fixtures.csv      Champions League / Europa League midweek dates
    upcoming_fixtures.csv      round 11
    offseason.json             relegations, promotions, playoffs, transfers, manager changes
    events/events_<season>.parquet   ~2.1 million events
    showcase/                  the round-11 "live" match feed (stream it in clock order)
  hidden/                      NEVER expose to agents
    answer_key.json            planted traits per season (the ground truth)
    player_attributes.csv      hidden player ratings
    team_styles.csv            hidden team style parameters
    showcase_selection.json    how the showcase match was chosen
  reports/
    realism_report.md / .json  realism checks + trait detectability
    run_summary.json
```

## The universe

| | |
|---|---|
| Leagues | **Crown League** (20 clubs, 38 rounds) and **Crown League Two** (24 clubs, 46 rounds) |
| Seasons | **2025-26** complete; **2026-27** played to round 10, round 11 is the showcase |
| Promotion / relegation | Bottom 3 go down; top 2 go up plus the winner of a 3rd–6th playoff (two-legged semis, neutral final, penalties if level) |
| Europe | Top 5 → Champions League, 6th → Europa League. Five CL places assumes the country earned a UEFA European Performance Spot (set `--cl-spots 4` otherwise). European results are not simulated; the midweek games drive rest days, rotation and tiredness |
| Summer | Ageing and development, retirements, youth call-ups, ~10–18 transfers to stronger clubs, promoted clubs sign players, relegated and underperforming clubs change manager (new formation and style) |

## How a match is played

The engine plays possession by possession and emits professional-style events:
passes (with a context-only **pass difficulty rating**), carries, take-ons,
pressures, tackles, interceptions, blocks, clearances, aerial duels, shots with
**xG** and **shot speed**, saves, fouls, cards, offsides, substitutions,
corners, free kicks, penalties and throw-ins.

Outcomes come from hidden player attributes and team style, so patterns emerge
from the numbers instead of being scripted:

- **Team style**: directness, tempo, pressing intensity and height, defensive line, crossing, counter-attacking, preferred flank
- **Game state**: teams chasing a game take more risks; teams protecting a lead sit deeper
- **Fatigue**: players tire, low-fitness teams fade late, pressing costs energy, substitutes are fresh, and clubs that played in Europe midweek rotate and start tired
- **Home advantage** (stronger for some clubs), red cards, set-piece quality, formations

## Hidden truths and the answer key

Each club gets one or two planted team traits (for example *poor at defending
set pieces*, *fades after 75 minutes*, *attacks mostly down the left*) and one
or two planted player traits (*loses the ball under pressure*, *weak in the
air*, *clinical finisher*, *goalkeeper weak on crosses*, ...). Planted weaknesses
never drop a player out of the team: his other ratings are raised to keep his
overall level.

`answer_key.json` lists every truth with the statistic that should reveal it.
The realism report checks that each one is actually visible in the data
(robust z-score against peers). Agents only ever read `data/public`; the answer
key is used to score their claims afterwards.

## Realism (default seed)

27 of 27 league-level checks fall inside real-football ranges, including
goals per match (≈2.9), home/draw/away split (≈45/26/29%), shots (≈26),
xG per shot (≈0.11), pass completion (≈80%), corners, fouls, cards,
penalties, offsides, set-piece goal share, late-goal share, added time and the
shape of the final table. About three quarters of planted traits are
detectable after one full season; the rest are subtle, like in real football.
See `data/reports/realism_report.md` after a run.

## Event coordinates

Every event is in the **acting team's frame**: `x` 0 → 105 from own goal line
to the opponent's, `y` 0 → 68 from the team's right touchline to its left.
`matchsim.schema.to_absolute(x, y, team_is_home, period)` converts to a fixed
broadcast frame. `minute` follows the football clock (the second half starts at
45:00); `clock_s` is monotonic across both halves, so sort by it to replay a feed.

## The showcase match

Round 11's fixture with the richest matchup (one side's planted weakness
against the other side's strength) is simulated 20 times and the most watchable
version is kept. This is disclosed in `hidden/showcase_selection.json`; every
historical match is a single, unselected simulation.

## Code map

| File | What it does |
|---|---|
| `matchsim/universe.py` | Clubs, players, managers, formations, trait planting, offseason |
| `matchsim/engine.py` | The match engine |
| `matchsim/season.py` | Fixtures, calendar, European midweeks, rest and rotation, standings, playoffs, parallel runs |
| `matchsim/pipeline.py` | End-to-end generation, showcase selection, file output |
| `matchsim/realism.py` | Realism checks and trait-detectability report |
| `matchsim/schema.py` | Event schema and coordinate helpers |
| `scripts/generate.py` | Command-line entry point |
| `tests/test_matchsim.py` | Determinism, schema, scheduling and pipeline tests |
