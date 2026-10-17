# Inside the Game — match intelligence for a synthetic league

Built for the Microsoft × Premier League *Inside the Game* hackathon.

1. **`matchsim`** generates a fictional, football-realistic league: two seasons of
   event-level data with promotion and relegation, European midweeks, transfers,
   manager changes and a hidden **answer key** of planted strengths and weaknesses.
2. **`analytics`** turns raw events into explainable statistics: xG, expected threat
   (xT), pressing, set-piece and late-game splits, scouting findings with
   confidence levels, pre-match matchup edges, and live match intelligence.
3. **`mcp_server`** exposes those statistics to AI agents as 18 MCP tools. Agents never
   touch files or the answer key.
4. **`evaluation`** scores the system's claims against the hidden answer key.

The rule of the project: **numbers come from code, words come from the LLM.** Every
number an agent says comes from a tool, with event references a verifier can check.

All clubs, players, managers and competitions are invented. No real names,
logos or match data are used.

## Quick start (Windows PowerShell, inside the project folder)

```powershell
uv add numpy pandas pyarrow "mcp==2.3.0"
uv add --dev pytest
uv run scripts/generate.py          # 1. the league: about 1-2 minutes
uv run scripts/build_stats.py       # 2. derived statistics: about 40 seconds
uv run scripts/eval_scout.py        # 3. score the scouting against the answer key
uv run pytest -q                    # 19 tests
```

Try the MCP server with the official inspector, or start it for an agent:

```powershell
uv run python -m mcp_server.server                 # stdio (agents on this machine)
uv run python -m mcp_server.server --http --port 8000   # HTTP (e.g. Azure Container Apps)
```

Play the showcase match as a live feed (the live tools can never see past the feed clock):

```powershell
uv run scripts/replay_feed.py --speed 60    # one minute of play per second
uv run scripts/replay_feed.py --reset       # remove the clock afterwards
```

## Layers

```
data/public  ->  analytics (build: xT, shots, player-match, team-match, refs)  ->  data/derived
                    |                                                             |
                    +------------ analytics.api.Analyst  <------------------------+
                                        |
                                 mcp_server (18 tools)  ->  agents (next step)
data/hidden  ->  evaluation only (answer key scoring)
```

`analytics.store.Store` refuses to read anything under `data/hidden`, and a test
checks that no runtime code imports the evaluation package.

## MCP tools

| Tool | Purpose |
|---|---|
| `overview` | League, table, last summer, the showcase fixture. Start here |
| `league_table` | Table with Champions League / Europa League / relegation zones |
| `search`, `upcoming_fixtures` | Find ids; next round |
| `club_profile` | Manager, formation, record, home/away, attack, defence, style, discipline, formations used and results — all with league percentiles |
| `goals_breakdown` | How a club concedes or scores: open play, counter, corner, free kick, penalty, throw-in, own goal; by period, game state and zone; every goal listed |
| `player_profile`, `player_event_map`, `squad_report` | Per-90s and rates with position percentiles; where and when a player loses the ball |
| `scout_findings` | Weaknesses, strengths and tendencies with confidence and evidence |
| `head_to_head`, `matchup_report` | Pre-match report: stakes, Europe midweek, form, style clash, **edges** and **predictions to track live** |
| `live_state`, `live_key_moments`, `live_predictions`, `live_player` | The live match at any clock: score, xG, momentum, control vs chaos, key moments, prediction status, player focus |
| `get_events`, `glossary` | Verify a claim from its event references; metric definitions |

## How scouting works

For each candidate finding (e.g. *loses the ball under pressure*, *weak in the air*,
*poor at defending set pieces*, *fades after 75 minutes*), the Scout:

1. measures the matching statistic for the player or team,
2. adjusts for team style where the system inflates a player's numbers (a
   player in a direct, high-risk team loses the ball more through no fault of his own),
3. shrinks small samples toward the peer median,
4. compares with peers (same position and division) using a robust z-score,
5. blends last season when this season is short, each season compared with its own
   league, so a promoted club's second-tier numbers are put in context,
6. attaches a confidence level and example event references.

Confidence tiers: **high** = headline, safe to state on screen; **medium** = watch
list, framed as something to watch and verified live; **low** = weak signal.

## Results on the default seed

Scouting from statistics alone, before any LLM (`data/reports/scout_eval.md`):

| | 2025-26 (full season) | 2026-27 (10 rounds, blending last season) |
|---|---|---|
| Planted traits recovered (medium+) | 40 / 60 (67%) | 32 / 62 (52%) |
| High-confidence findings backed by hidden ratings | 80% | 84% |
| All medium+ findings backed by hidden ratings | 70% | 71% |

"Backed by hidden ratings" counts a finding as right if it names a planted trait or a
player/team whose hidden rating is in the worst (or best) 20% of peers.

The showcase match (Dunvarrow Borough v Penmarrow Athletic) before kick-off predicted
that Penmarrow's centre-back would lose aerial duels, Dunvarrow's centre-back would be
dispossessed under Penmarrow's press, and Penmarrow would foul a lot. All three were
confirmed live; two other predictions did not happen, and the system says so.

## The synthetic league

| | |
|---|---|
| Leagues | **Crown League** (20 clubs, 38 rounds) and **Crown League Two** (24 clubs, 46 rounds) |
| Seasons | **2025-26** complete; **2026-27** played to round 10, round 11 is the showcase |
| Promotion / relegation | Bottom 3 go down; top 2 go up plus the winner of a 3rd–6th playoff |
| Europe | Top 5 → Champions League, 6th → Europa League (5 CL places assumes a European Performance Spot; `--cl-spots 4` otherwise). Midweek games drive rest days, rotation and tiredness |
| Summer | Ageing, retirements, youth call-ups, transfers, promoted-club signings, manager changes |

Realism: 27 of 27 league-level checks fall inside real-football ranges (goals per
match ≈2.9, home/draw/away ≈45/26/29%, shots ≈26, xG per shot ≈0.11, pass completion
≈80%, corners, fouls, cards, penalties, offsides, set-piece and late-goal shares,
added time, table shape). See `data/reports/realism_report.md`.

The showcase match is the most watchable of 20 realistic simulations of the chosen
fixture (disclosed in `hidden/showcase_selection.json`); every historical match is a
single, unselected simulation.

Event coordinates are in the **acting team's frame**: `x` 0 → 105 toward the
opponent's goal, `y` 0 → 68 from the team's right touchline to its left.
`matchsim.schema.to_absolute` converts to a broadcast frame. `clock_s` is monotonic
across halves; sort by it to replay a feed.

## Code map

| Path | What it does |
|---|---|
| `matchsim/` | League universe, match engine, seasons, offseason, realism report |
| `analytics/store.py` | Public/derived data access with the hidden-data guard |
| `analytics/xt.py` | Expected threat learned from last season's events |
| `analytics/build.py` | Batch layer: shots with phase and assist, player-match, team-match, evidence refs |
| `analytics/metrics.py` | Metric definitions, shrinkage, team adjustment, peer comparison |
| `analytics/scout.py` | Findings with confidence and evidence |
| `analytics/profiles.py` | Club and player profiles, goal breakdowns, tables, form, head-to-head |
| `analytics/matchup.py` | Edges and live-checkable predictions |
| `analytics/live.py` | Live state, momentum, control vs chaos, key moments, prediction tracking, player focus |
| `analytics/api.py` | The `Analyst` facade used by the server and agents |
| `mcp_server/server.py` | The MCP server (stdio or HTTP) with the live-clock guard |
| `evaluation/answer_key.py` | Scoring against the hidden answer key and ratings |
| `scripts/` | `generate.py`, `build_stats.py`, `eval_scout.py`, `replay_feed.py` |
| `tests/` | 19 tests: generator, stats, live layer, MCP server, hidden-data guard |
