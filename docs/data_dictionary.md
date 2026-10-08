# Data dictionary

Tables built by [`sql/01_build_tables.sql`](../sql/01_build_tables.sql) in `data/statcast.duckdb`.

## `player_season`

One row per hitter per season, 2021–2026, minimum 100 PA. Percent columns are on a 0–100 scale.

| Column | Description | Source |
|---|---|---|
| `player_id` | MLBAM player ID (join key for every source) | Savant |
| `season` | Season | Savant |
| `player_name` | "Last, First" | Savant |
| `pa` | Plate appearances, regular season | Savant |
| `woba` | Weighted on-base average (actual) | Savant |
| `xwoba` | Expected wOBA from exit velocity, launch angle, and (on topped/weakly hit balls) sprint speed | Savant |
| `woba_gap` | `woba - xwoba`. Positive = outperformed contact quality | derived |
| `k_pct`, `bb_pct` | Strikeout and walk rate | Savant |
| `barrel_pct` | Barrels per batted ball | Savant |
| `hard_hit_pct` | Batted balls at 95+ mph | Savant |
| `sweet_spot_pct` | Batted balls with a launch angle of 8–32° | Savant |
| `pull_pct`, `straight_pct`, `oppo_pct` | Spray direction, all batted balls | Savant |
| `gb_pct`, `fb_pct`, `ld_pct` | Ground ball / fly ball / line drive rate | Savant |
| `sprint_speed` | Feet per second in the fastest one-second window, competitive runs | Savant |
| `bat_speed` | Average bat speed (mph) at the bat's sweet spot, top 90% of the hitter's swings. Missing before 2024 | Savant bat tracking |
| `bbe` | Batted-ball events | Savant batted-ball leaderboard |
| `air_pct` | Air balls (fly balls, line drives, popups) per batted ball | Savant batted-ball leaderboard |
| `pull_air_pct` | Pulled air balls per batted ball | Savant batted-ball leaderboard |
| `pull_share_of_air` | Pulled air balls per air ball | derived |
| `bat_side` | L / R / S (current listing) | MLB Stats API |
| `primary_team_id`, `primary_team` | Team with the most PA that season (ID and abbreviation) | MLB Stats API |
| `primary_venue_id`, `primary_venue` | That team's home park (missing for the 2021 Blue Jays) | MLB Stats API |
| `primary_team_pa_share` | Share of the season's PA with the primary team | derived |
| `n_teams` | Number of MLB teams played for that season | MLB Stats API |
| `statsapi_pa` | PA summed across teams, for reconciliation | MLB Stats API |

## `season_pairs`

One row per hitter per pair of consecutive seasons where both seasons are in `player_season`.

| Column | Description |
|---|---|
| `player_id`, `player_name` | Hitter |
| `season_1` | First season of the pair (the second is `season_1 + 1`) |
| `pa_1`, `pa_2` | PA in each season |
| `gap_1`, `gap_2` | `woba_gap` in each season |
| `xwoba_1`, `woba_1`, `woba_2` | Season-1 xwOBA and wOBA, season-2 wOBA |
| `same_team` | Same primary team both seasons (by team ID) |
| `same_park` | Same home park both seasons (by venue ID; missing if either is unknown) |
