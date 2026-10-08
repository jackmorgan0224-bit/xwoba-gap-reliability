-- Data-quality checks run after every build. Each check returns the number of rows
-- flagged out of the rows checked; build_db.py writes the results to docs/validation_report.md.
--   FAIL  = should never happen; build_db.py exits non-zero
--   WARN  = expected to be small; review flagged rows before modeling
--   INFO  = descriptive count, no pass/fail threshold
-- Comparisons are written so a NULL counts as flagged: in SQL, NULL > x is not true,
-- so a check like ABS(a - b) > 2 alone would silently pass rows with a missing value.

WITH checks AS (

    -- Uniqueness: one row per player-season at every stage, so joins can't fan out
    SELECT 1 AS check_order, 'Duplicate player-seasons: Savant custom leaderboard' AS check_name,
           COUNT(*) - COUNT(DISTINCT (player_id, season)) AS flagged, COUNT(*) AS checked,
           'FAIL' AS severity
    FROM stg_savant_custom

    UNION ALL
    SELECT 2, 'Duplicate player-seasons: Savant batted-ball leaderboard',
           COUNT(*) - COUNT(DISTINCT (player_id, season)), COUNT(*), 'FAIL'
    FROM stg_batted_ball

    UNION ALL
    SELECT 3, 'Duplicate player-seasons: player_season (join fan-out)',
           COUNT(*) - COUNT(DISTINCT (player_id, season)), COUNT(*), 'FAIL'
    FROM player_season

    UNION ALL
    SELECT 4, 'Duplicate pairs: season_pairs',
           COUNT(*) - COUNT(DISTINCT (player_id, season_1)), COUNT(*), 'FAIL'
    FROM season_pairs

    -- Completeness: every season present, and no blank columns (Savant returns an
    -- all-blank column for a mistyped field key)
    UNION ALL
    SELECT 5, 'Seasons 2021-2026 missing from player_season or the MLB Stats API data',
           6 - (SELECT COUNT(DISTINCT season) FROM player_season WHERE season BETWEEN 2021 AND 2026)
             + 6 - (SELECT COUNT(DISTINCT season) FROM stg_team_pa WHERE season BETWEEN 2021 AND 2026),
           12, 'FAIL'

    UNION ALL
    SELECT 6, 'Missing value in any core Savant column (PA, wOBA, xwOBA, K%, BB%, contact, spray, batted-ball type, sprint speed)',
           COUNT(*) FILTER (WHERE pa IS NULL OR woba IS NULL OR xwoba IS NULL
                               OR k_pct IS NULL OR bb_pct IS NULL OR barrel_pct IS NULL
                               OR hard_hit_pct IS NULL OR sweet_spot_pct IS NULL
                               OR pull_pct IS NULL OR straight_pct IS NULL OR oppo_pct IS NULL
                               OR gb_pct IS NULL OR fb_pct IS NULL OR ld_pct IS NULL
                               OR sprint_speed IS NULL),
           COUNT(*), 'FAIL'
    FROM player_season

    UNION ALL
    SELECT 7, 'Missing bat speed, 2024+',
           COUNT(*) FILTER (WHERE bat_speed IS NULL), COUNT(*), 'WARN'
    FROM player_season WHERE season >= 2024

    UNION ALL
    SELECT 8, 'Bat speed present before 2024 (should be nulled in staging)',
           COUNT(*) FILTER (WHERE bat_speed IS NOT NULL), COUNT(*), 'FAIL'
    FROM player_season WHERE season < 2024

    -- Plausibility
    UNION ALL
    SELECT 9, 'wOBA or xwOBA outside plausible range (.100-.600)',
           COUNT(*) FILTER (WHERE NOT (woba BETWEEN 0.1 AND 0.6 AND xwoba BETWEEN 0.1 AND 0.6)
                               OR woba IS NULL OR xwoba IS NULL),
           COUNT(*), 'WARN'
    FROM player_season

    UNION ALL
    SELECT 10, 'Pull + straightaway + oppo % does not sum to 100 (+/- 0.5)',
           COUNT(*) FILTER (WHERE NOT ABS(pull_pct + straight_pct + oppo_pct - 100) <= 0.5
                               OR pull_pct IS NULL OR straight_pct IS NULL OR oppo_pct IS NULL),
           COUNT(*), 'WARN'
    FROM player_season

    -- Cross-source reconciliation
    UNION ALL
    SELECT 11, 'No MLB Stats API match (team/hand unknown)',
           COUNT(*) FILTER (WHERE primary_team_id IS NULL OR bat_side IS NULL), COUNT(*), 'FAIL'
    FROM player_season

    UNION ALL
    SELECT 12, 'Savant PA differs from MLB Stats API PA by more than 2',
           COUNT(*) FILTER (WHERE NOT ABS(pa - statsapi_pa) <= 2 OR statsapi_pa IS NULL),
           COUNT(*), 'WARN'
    FROM player_season

    UNION ALL
    SELECT 13, 'Savant PA differs from MLB Stats API PA by 1-2 (source rounding, informational)',
           COUNT(*) FILTER (WHERE ABS(pa - statsapi_pa) BETWEEN 1 AND 2), COUNT(*), 'INFO'
    FROM player_season

    UNION ALL
    SELECT 14, 'Cross-check: player-season missing from Savant expected-stats leaderboard',
           COUNT(*) FILTER (WHERE x.player_id IS NULL), COUNT(*), 'FAIL'
    FROM player_season AS p
    LEFT JOIN xcheck_expected AS x USING (player_id, season)

    UNION ALL
    SELECT 15, 'Cross-check: PA, wOBA, or xwOBA disagrees with Savant expected-stats leaderboard',
           COUNT(*) FILTER (WHERE NOT (p.pa = x.pa
                                       AND ABS(p.woba - x.woba) <= 0.0005
                                       AND ABS(p.xwoba - x.xwoba) <= 0.0005)
                               OR x.pa IS NULL OR x.woba IS NULL OR x.xwoba IS NULL),
           COUNT(*), 'FAIL'
    FROM player_season AS p
    JOIN xcheck_expected AS x USING (player_id, season)

    UNION ALL
    SELECT 16, 'No batted-ball leaderboard match (pulled-air rate unknown)',
           COUNT(*) FILTER (WHERE pull_air_pct IS NULL), COUNT(*), 'WARN'
    FROM player_season

    -- Descriptive counts
    UNION ALL
    SELECT 17, 'Played for 2+ teams in the season',
           COUNT(*) FILTER (WHERE n_teams > 1), COUNT(*), 'INFO'
    FROM player_season

    UNION ALL
    SELECT 18, 'No single home park (2021 Blue Jays)',
           COUNT(*) FILTER (WHERE primary_venue_id IS NULL AND primary_team_id IS NOT NULL), COUNT(*), 'INFO'
    FROM player_season

    UNION ALL
    SELECT 19, 'Consecutive-season pairs (both seasons 100+ PA)',
           COUNT(*), COUNT(*), 'INFO'
    FROM season_pairs
)
SELECT
    check_order,
    check_name,
    flagged,
    checked,
    CASE
        WHEN severity = 'INFO' THEN 'INFO'
        WHEN flagged = 0 THEN 'PASS'
        ELSE severity
    END AS result
FROM checks
ORDER BY check_order;
