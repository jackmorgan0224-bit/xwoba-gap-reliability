-- Step 1 analysis table: consecutive-season pairs from both eras, with each season's gap
-- centered on that season's league average (PA-weighted over all 100+ PA hitters), so a
-- league-wide shift in wOBA - xwOBA isn't mistaken for player-level persistence.
-- weight = harmonic mean of the two seasons' PA: a pair is only as informative as its
-- smaller season.

-- speed_gap_1/2: the same gap with its sprint-speed component removed (residual from a
-- per-season, PA-weighted regression of gap on sprint speed over all 100+ PA hitters).
-- Used to test how much of any change in persistence runs through speed.

CREATE OR REPLACE TABLE step1_pairs AS
WITH all_seasons AS (
    SELECT player_id, season, pa, woba_gap, sprint_speed FROM player_season
    UNION ALL
    SELECT player_id, season, pa, woba_gap, sprint_speed FROM history_season
),
season_means AS (
    SELECT
        season,
        SUM(woba_gap * pa) / SUM(pa)                     AS mean_gap,
        SUM(sprint_speed * pa) / SUM(pa)                 AS mean_speed
    FROM all_seasons
    GROUP BY season
),
speed_fit AS (
    -- weighted least-squares slope of gap on sprint speed, per season
    SELECT
        s.season,
        SUM(s.pa * (s.sprint_speed - m.mean_speed) * (s.woba_gap - m.mean_gap))
            / SUM(s.pa * (s.sprint_speed - m.mean_speed) ^ 2) AS speed_slope
    FROM all_seasons AS s
    JOIN season_means AS m USING (season)
    GROUP BY s.season
),
residual AS (
    SELECT
        s.player_id,
        s.season,
        s.woba_gap - m.mean_gap - f.speed_slope * (s.sprint_speed - m.mean_speed) AS speed_adj_gap
    FROM all_seasons AS s
    JOIN season_means AS m USING (season)
    JOIN speed_fit AS f USING (season)
),
all_pairs AS (
    SELECT 'recent' AS era, player_id, player_name, season_1, pa_1, pa_2,
           min_ab, min_pitches, gap_1, gap_2
    FROM season_pairs
    UNION ALL
    SELECT 'history' AS era, player_id, player_name, season_1, pa_1, pa_2,
           min_ab, min_pitches, gap_1, gap_2
    FROM history_pairs
)
SELECT
    p.*,
    p.gap_1 - m1.mean_gap                  AS cgap_1,
    p.gap_2 - m2.mean_gap                  AS cgap_2,
    r1.speed_adj_gap                       AS speed_gap_1,
    r2.speed_adj_gap                       AS speed_gap_2,
    LEAST(p.pa_1, p.pa_2)                  AS min_pa,
    2.0 / (1.0 / p.pa_1 + 1.0 / p.pa_2)    AS weight
FROM all_pairs AS p
JOIN season_means AS m1 ON m1.season = p.season_1
JOIN season_means AS m2 ON m2.season = p.season_1 + 1
JOIN residual AS r1 ON r1.player_id = p.player_id AND r1.season = p.season_1
JOIN residual AS r2 ON r2.player_id = p.player_id AND r2.season = p.season_1 + 1;
