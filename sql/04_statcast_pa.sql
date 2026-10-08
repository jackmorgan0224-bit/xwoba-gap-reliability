-- Plate-appearance tables from the Statcast Search downloads (src/fetch_statcast.py).
--
-- Statcast Search's per-pitch woba_value uses rounded generic weights (single 0.9,
-- double 1.25, HR 2.0, walk 0.7) and counts reaching on an error as a single, while the
-- leaderboards use each season's exact linear weights with errors as outs. So:
--   1. statcast_counts: event counts per player-season;
--   2. src/step2_reliability.py fits each season's weights to the leaderboard wOBA
--      (exact to rounding) and stores them as woba_weights;
--   3. statcast_pa values every PA with those weights. xwOBA credits walks, strikeouts,
--      and HBP at their actual value, so the gap comes from balls in play only:
--      resid = exact value - Statcast expected wOBA on contact (0 for other PAs).
-- wOBA denominator = PA - intentional walks - sacrifice bunts - catcher's interference
-- (truncated PAs, ended by a baserunning out, aren't plate appearances).

CREATE OR REPLACE TABLE statcast_raw AS
SELECT
    YEAR(CAST(game_date AS DATE))                       AS season,
    CAST(game_date AS DATE)                             AS game_date,
    CAST(game_pk AS INTEGER)                            AS game_pk,
    CAST(at_bat_number AS INTEGER)                      AS at_bat_number,
    CAST(batter AS INTEGER)                             AS player_id,
    stand,
    home_team,
    away_team,
    events,
    bb_type,
    TRY_CAST(launch_speed AS DOUBLE)                    AS launch_speed,
    TRY_CAST(launch_angle AS DOUBLE)                    AS launch_angle,
    TRY_CAST(hc_x AS DOUBLE)                            AS hc_x,
    TRY_CAST(hc_y AS DOUBLE)                            AS hc_y,
    TRY_CAST(estimated_woba_using_speedangle AS DOUBLE) AS xwoba_contact,
    of_fielding_alignment,
    TRY_CAST(bat_speed AS DOUBLE)                       AS bat_speed,
    events <> 'truncated_pa'                            AS is_pa,
    events NOT IN ('truncated_pa', 'intent_walk', 'sac_bunt', 'sac_bunt_double_play', 'catcher_interf')
                                                        AS in_denominator,
    bb_type IS NOT NULL
        AND events NOT IN ('truncated_pa', 'sac_bunt', 'sac_bunt_double_play') AS is_bip
FROM read_csv('data/raw/statcast/*/*.csv.gz', all_varchar = true, header = true, union_by_name = true);

CREATE OR REPLACE TABLE statcast_counts AS
SELECT
    player_id,
    season,
    COUNT(*) FILTER (WHERE is_pa)                            AS pa,
    COUNT(*) FILTER (WHERE in_denominator)                   AS denom,
    COUNT(*) FILTER (WHERE events = 'single')                AS n_1b,
    COUNT(*) FILTER (WHERE events = 'double')                AS n_2b,
    COUNT(*) FILTER (WHERE events = 'triple')                AS n_3b,
    COUNT(*) FILTER (WHERE events = 'home_run')              AS n_hr,
    COUNT(*) FILTER (WHERE events = 'walk')                  AS n_bb,
    COUNT(*) FILTER (WHERE events = 'hit_by_pitch')          AS n_hbp,
    COUNT(*) FILTER (WHERE is_bip)                           AS bip,
    COUNT(*) FILTER (WHERE is_bip AND xwoba_contact IS NULL) AS bip_missing_xwoba,
    SUM(CASE WHEN is_bip THEN xwoba_contact ELSE 0 END)      AS xwoba_contact_sum
FROM statcast_raw
GROUP BY player_id, season;
