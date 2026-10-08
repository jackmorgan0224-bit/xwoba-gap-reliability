-- Build the analysis tables from the cached raw files in data/raw/.
-- Raw files are read as text and cast explicitly: Savant quotes wOBA as ".309" and
-- mixes 0-100 percents (custom leaderboard) with 0-1 fractions (batted-ball leaderboard).

-- Staging: Savant custom leaderboard, one row per player-season (min 100 PA)
CREATE OR REPLACE TABLE stg_savant_custom AS
SELECT
    CAST(player_id AS INTEGER)              AS player_id,
    CAST("year" AS INTEGER)                 AS season,
    "last_name, first_name"                 AS player_name,
    CAST(pa AS INTEGER)                     AS pa,
    TRY_CAST(woba AS DOUBLE)                AS woba,
    TRY_CAST(xwoba AS DOUBLE)               AS xwoba,
    TRY_CAST(k_percent AS DOUBLE)           AS k_pct,
    TRY_CAST(bb_percent AS DOUBLE)          AS bb_pct,
    TRY_CAST(barrel_batted_rate AS DOUBLE)  AS barrel_pct,
    TRY_CAST(hard_hit_percent AS DOUBLE)    AS hard_hit_pct,
    TRY_CAST(sweet_spot_percent AS DOUBLE)  AS sweet_spot_pct,
    TRY_CAST(pull_percent AS DOUBLE)        AS pull_pct,
    TRY_CAST(straightaway_percent AS DOUBLE) AS straight_pct,
    TRY_CAST(opposite_percent AS DOUBLE)    AS oppo_pct,
    TRY_CAST(groundballs_percent AS DOUBLE) AS gb_pct,
    TRY_CAST(flyballs_percent AS DOUBLE)    AS fb_pct,
    TRY_CAST(linedrives_percent AS DOUBLE)  AS ld_pct,
    TRY_CAST(sprint_speed AS DOUBLE)        AS sprint_speed,
    -- Savant also has partial-season 2023 bat tracking; keep full seasons only
    CASE WHEN CAST("year" AS INTEGER) >= 2024
         THEN TRY_CAST(avg_swing_speed AS DOUBLE) END AS bat_speed
FROM read_csv('data/raw/savant_custom_*.csv', all_varchar = true, header = true);

-- Staging: Savant batted-ball leaderboard (converted from fractions to percents)
CREATE OR REPLACE TABLE stg_batted_ball AS
SELECT
    CAST(id AS INTEGER)                          AS player_id,
    CAST("year" AS INTEGER)                      AS season,
    CAST(bbe AS INTEGER)                         AS bbe,
    100 * CAST(air_rate AS DOUBLE)               AS air_pct,
    100 * CAST(pull_air_rate AS DOUBLE)          AS pull_air_pct,       -- pulled air balls / all batted balls
    100 * CAST(pull_air_rate AS DOUBLE)
        / NULLIF(CAST(air_rate AS DOUBLE), 0)    AS pull_share_of_air   -- pulled air balls / air balls
FROM read_csv('data/raw/savant_batted_ball_*.csv', all_varchar = true, header = true);

-- Staging: MLB Stats API, one row per player x team x season
CREATE OR REPLACE TABLE stg_team_pa AS
SELECT
    CAST(season AS INTEGER)    AS season,
    CAST(player_id AS INTEGER) AS player_id,
    player_name,
    bat_side,
    CAST(team_id AS INTEGER)   AS team_id,
    team_abbr,
    -- The 2021 Blue Jays split home games across Dunedin, Buffalo, and Toronto, so
    -- they get no single home park; park analyses drop them.
    CASE WHEN CAST(season AS INTEGER) = 2021 AND CAST(team_id AS INTEGER) = 141
         THEN NULL ELSE CAST(venue_id AS INTEGER) END AS venue_id,
    CASE WHEN CAST(season AS INTEGER) = 2021 AND CAST(team_id AS INTEGER) = 141
         THEN NULL ELSE venue_name END                AS venue_name,
    CAST(pa AS INTEGER)        AS pa
FROM read_csv('data/raw/statsapi_team_pa_*.csv', all_varchar = true, header = true);

-- Cross-check source: Savant's expected-stats leaderboard, a separate endpoint that
-- also reports PA / wOBA / xwOBA. Used only by sql/02_validation.sql.
CREATE OR REPLACE TABLE xcheck_expected AS
SELECT
    CAST(player_id AS INTEGER) AS player_id,
    CAST("year" AS INTEGER)    AS season,
    CAST(pa AS INTEGER)        AS pa,
    CAST(woba AS DOUBLE)       AS woba,
    CAST(est_woba AS DOUBLE)   AS xwoba
FROM read_csv('data/raw/savant_expected_*.csv', all_varchar = true, header = true);

-- Core table: one row per player-season with the gap, spray, and park assignment.
-- A player who changed teams is assigned the team where he took the most PA;
-- primary_team_pa_share records how much of his season that team represents.
-- Teams and parks are identified by ID: abbreviations change (OAK -> ATH in 2025) and
-- stadiums get renamed (Minute Maid Park -> Daikin Park).
CREATE OR REPLACE TABLE player_season AS
WITH team_rank AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY player_id, season ORDER BY pa DESC, team_id) AS team_rank,
        COUNT(*)     OVER (PARTITION BY player_id, season)                           AS n_teams,
        SUM(pa)      OVER (PARTITION BY player_id, season)                           AS statsapi_pa
    FROM stg_team_pa
)
SELECT
    c.*,
    c.woba - c.xwoba                    AS woba_gap,
    b.bbe,
    b.air_pct,
    b.pull_air_pct,
    b.pull_share_of_air,
    t.bat_side,
    t.team_id                           AS primary_team_id,
    t.team_abbr                         AS primary_team,
    t.venue_id                          AS primary_venue_id,
    t.venue_name                        AS primary_venue,
    t.pa / t.statsapi_pa                AS primary_team_pa_share,
    t.n_teams,
    t.statsapi_pa
FROM stg_savant_custom AS c
LEFT JOIN stg_batted_ball AS b USING (player_id, season)
LEFT JOIN team_rank AS t
    ON t.player_id = c.player_id
   AND t.season = c.season
   AND t.team_rank = 1;

-- Consecutive-season pairs: the unit of analysis for "does the gap repeat?"
CREATE OR REPLACE TABLE season_pairs AS
SELECT
    y1.player_id,
    y1.player_name,
    y1.season                   AS season_1,
    y1.pa                       AS pa_1,
    y2.pa                       AS pa_2,
    y1.woba_gap                 AS gap_1,
    y2.woba_gap                 AS gap_2,
    y1.xwoba                    AS xwoba_1,
    y1.woba                     AS woba_1,
    y2.woba                     AS woba_2,
    y1.primary_team_id = y2.primary_team_id   AS same_team,
    y1.primary_venue_id = y2.primary_venue_id AS same_park  -- NULL when either park is unknown
FROM player_season AS y1
JOIN player_season AS y2
    ON y2.player_id = y1.player_id
   AND y2.season = y1.season + 1;
