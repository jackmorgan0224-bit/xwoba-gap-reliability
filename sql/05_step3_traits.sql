-- Step 3 inputs built from individual balls in play (requires sql/04_statcast_pa.sql).
--
-- Spray angle: degrees from straightaway center, from Statcast hit coordinates
-- (home plate at hc_x = 125.42, hc_y = 198.27). Negative = third-base side.
-- "Pulled" = more than 15 degrees toward the batter's pull side.
-- "Air" = fly ball, line drive, or popup (Savant's definition).

CREATE OR REPLACE TABLE bip AS
SELECT
    pa.*,
    DEGREES(ATAN2(hc_x - 125.42, 198.27 - hc_y))                     AS spray_angle,
    CASE WHEN stand = 'R' THEN DEGREES(ATAN2(hc_x - 125.42, 198.27 - hc_y)) < -15
         ELSE DEGREES(ATAN2(hc_x - 125.42, 198.27 - hc_y)) > 15 END    AS pulled,
    bb_type IN ('fly_ball', 'line_drive', 'popup')                     AS is_air,
    -- Statcast labels the Athletics 'ATH' in every season; the MLB Stats API uses 'OAK'
    -- through 2024. Neutral-site games (London, Tokyo, Seoul, etc.) are attributed to the
    -- designated home team's park: a handful of games per season.
    CASE WHEN home_team = 'ATH' AND season <= 2024 THEN 'OAK' ELSE home_team END AS home_abbr
FROM statcast_pa AS pa
WHERE is_bip AND resid IS NOT NULL AND hc_x IS NOT NULL AND hc_y IS NOT NULL;

-- Park effect on the gap: mean ball-in-play residual of ALL hitters (home and visiting)
-- in each park, measured from the OTHER seasons the same team played there, so a
-- hitter's own season never informs his park adjustment. Parks are matched by MLB venue
-- ID, so the Rays' 2025 season at Steinbrenner Field and the Athletics' moves get their
-- own parks.
CREATE OR REPLACE TABLE park_effect AS
WITH venue AS (
    SELECT DISTINCT season, team_abbr, venue_id FROM stg_team_pa WHERE venue_id IS NOT NULL
),
by_venue_season AS (
    SELECT v.venue_id, b.season, SUM(b.resid) AS resid_sum, COUNT(*) AS n
    FROM bip AS b
    JOIN venue AS v ON v.season = b.season AND v.team_abbr = b.home_abbr
    GROUP BY v.venue_id, b.season
),
league AS (
    SELECT season, AVG(resid) AS league_resid FROM bip GROUP BY season
)
SELECT
    t.venue_id,
    t.season,
    -- leave-one-season-out: other seasons' residuals, each relative to its league average
    (SUM(o.resid_sum - o.n * l.league_resid) / NULLIF(SUM(o.n), 0)) AS park_resid_loso,
    SUM(o.n) AS bip_other_seasons
FROM by_venue_season AS t
LEFT JOIN by_venue_season AS o ON o.venue_id = t.venue_id AND o.season <> t.season
LEFT JOIN league AS l ON l.season = o.season
GROUP BY t.venue_id, t.season;

-- Player-season traits from individual balls in play
CREATE OR REPLACE TABLE player_traits AS
WITH venue AS (
    SELECT DISTINCT season, team_abbr, venue_id FROM stg_team_pa WHERE venue_id IS NOT NULL
)
SELECT
    b.player_id,
    b.season,
    COUNT(*)                                                             AS bip,
    AVG(CASE WHEN b.pulled AND b.is_air THEN 1.0 ELSE 0 END)             AS pulled_air_rate,
    -- Salorio's Opt_95 idea: pulled fly balls at 95-105 mph, per ball at 95-105 mph
    AVG(CASE WHEN b.pulled AND b.bb_type = 'fly_ball' THEN 1.0 ELSE 0 END)
        FILTER (WHERE b.launch_speed BETWEEN 95 AND 105)                 AS pulled_hard_fb_share,
    -- average park effect over the parks where his balls in play happened
    AVG(pe.park_resid_loso)                                              AS park_exposure,
    COUNT(*) FILTER (WHERE pe.park_resid_loso IS NULL)                   AS bip_no_park_effect
FROM bip AS b
LEFT JOIN venue AS v ON v.season = b.season AND v.team_abbr = b.home_abbr
LEFT JOIN park_effect AS pe ON pe.venue_id = v.venue_id AND pe.season = b.season
GROUP BY b.player_id, b.season;

-- For forecasting, park effects may only use what was known at the time: the effect of
-- each park estimated from seasons up to and including season s.
CREATE OR REPLACE TABLE park_effect_through AS
WITH venue AS (
    SELECT DISTINCT season, team_abbr, venue_id FROM stg_team_pa WHERE venue_id IS NOT NULL
),
league AS (SELECT season, AVG(resid) AS league_resid FROM bip GROUP BY season),
by_venue_season AS (
    SELECT v.venue_id, b.season, SUM(b.resid - l.league_resid) AS excess, COUNT(*) AS n
    FROM bip AS b
    JOIN venue AS v ON v.season = b.season AND v.team_abbr = b.home_abbr
    JOIN league AS l ON l.season = b.season
    GROUP BY ALL
)
SELECT t.venue_id, s.season AS through_season, SUM(t.excess) / SUM(t.n) AS park_effect
FROM by_venue_season AS t
JOIN (SELECT DISTINCT season FROM bip) AS s ON t.season <= s.season
GROUP BY ALL;

-- Forecast-safe park exposure for each player-season t:
--   park_exposure_known:   his season-t balls in play, park effects through season t
--   next_park_exposure:    his season-(t+1) balls in play, park effects through season t
--                          (stands in for a known schedule; stored on the season-t row)
CREATE OR REPLACE TABLE player_park_forecast AS
WITH venue AS (
    SELECT DISTINCT season, team_abbr, venue_id FROM stg_team_pa WHERE venue_id IS NOT NULL
),
ball_venue AS (
    SELECT b.player_id, b.season, v.venue_id
    FROM bip AS b
    JOIN venue AS v ON v.season = b.season AND v.team_abbr = b.home_abbr
),
known AS (
    SELECT bv.player_id, bv.season, AVG(pe.park_effect) AS park_exposure_known
    FROM ball_venue AS bv
    JOIN park_effect_through AS pe ON pe.venue_id = bv.venue_id AND pe.through_season = bv.season
    GROUP BY ALL
),
nxt AS (
    SELECT bv.player_id, bv.season - 1 AS season, AVG(pe.park_effect) AS next_park_exposure
    FROM ball_venue AS bv
    JOIN park_effect_through AS pe ON pe.venue_id = bv.venue_id AND pe.through_season = bv.season - 1
    GROUP BY ALL
)
SELECT k.player_id, k.season, k.park_exposure_known, n.next_park_exposure
FROM known AS k
LEFT JOIN nxt AS n USING (player_id, season);
