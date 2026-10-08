-- Value every plate appearance with the season's fitted wOBA weights (table woba_weights,
-- written by src/step2_reliability.py) and rebuild player-season wOBA, xwOBA, and gap.

CREATE OR REPLACE TABLE statcast_pa AS
SELECT
    r.*,
    CASE r.events
        WHEN 'single'       THEN w.w_1b
        WHEN 'double'       THEN w.w_2b
        WHEN 'triple'       THEN w.w_3b
        WHEN 'home_run'     THEN w.w_hr
        WHEN 'walk'         THEN w.w_bb
        WHEN 'hit_by_pitch' THEN w.w_hbp
        ELSE 0
    END                                                       AS woba_exact,
    CASE WHEN r.is_bip THEN
        CASE r.events
            WHEN 'single'   THEN w.w_1b
            WHEN 'double'   THEN w.w_2b
            WHEN 'triple'   THEN w.w_3b
            WHEN 'home_run' THEN w.w_hr
            ELSE 0
        END - r.xwoba_contact
    ELSE 0 END                                                AS resid
FROM statcast_raw AS r
JOIN woba_weights AS w USING (season);

CREATE OR REPLACE TABLE statcast_player_season AS
SELECT
    player_id,
    season,
    COUNT(*) FILTER (WHERE is_pa)                                AS pa,
    COUNT(*) FILTER (WHERE in_denominator)                       AS denom,
    COUNT(*) FILTER (WHERE is_bip)                               AS bip,
    SUM(woba_exact) FILTER (WHERE in_denominator)
        / COUNT(*) FILTER (WHERE in_denominator)                 AS woba,
    SUM(CASE WHEN is_bip THEN xwoba_contact ELSE woba_exact END) FILTER (WHERE in_denominator)
        / COUNT(*) FILTER (WHERE in_denominator)                 AS xwoba,
    SUM(resid) / COUNT(*) FILTER (WHERE in_denominator)          AS gap
FROM statcast_pa
GROUP BY player_id, season;
