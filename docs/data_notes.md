# Data notes

Issues found while building and validating the dataset, and how each was handled.
Current check results are in [`validation_report.md`](validation_report.md).

## Fixed

**MLB Stats API team endpoint leaves out players who left a team midseason.**
The first version pulled plate appearances team by team (`/api/v1/stats?teamId=...`).
The PA reconciliation check (Savant PA vs. Stats API PA) flagged 31 player-seasons, all
2024–2025 and all off by hundreds of PA. Example: Nathaniel Lowe, 2025, showed 119 PA
(Boston only) against 609 in Savant. Washington released him in August, and his 490 PA
there were missing because the team-level endpoint no longer listed him. Switched to the
player-level endpoint (`/api/v1/people?personIds=...&hydrate=stats(...)`), which returns
one split per team. After the fix every player-season reconciles within 2 PA, and 312
multi-team player-seasons are split correctly (previously 282 were detected).

**Team abbreviations and stadium names change.** The Athletics' abbreviation changed from
OAK to ATH in 2025, and several parks were renamed (Minute Maid Park → Daikin Park,
Guaranteed Rate Field → Rate Field, Dodger Stadium → UNIQLO Field at Dodger Stadium).
Matching on names split those franchises and parks in two, so teams and parks are matched
on MLB's numeric IDs. Real moves are kept as park changes: the Athletics to Sutter Health
Park (2025), the Rays to George M. Steinbrenner Field (2025) and back to Tropicana Field
(2026).

**2021 Blue Jays home park.** The MLB Stats API lists Rogers Centre, but the 2021 Blue
Jays played home games in Dunedin, Buffalo, and Toronto. They get no single home park
(13 player-seasons), so park-based analyses drop them.

**Partial-season 2023 bat tracking.** Savant reports bat speed for part of 2023. It is
set to missing before 2024 so bat-speed analyses use full seasons only.

**Checks that couldn't fail on missing values.** In SQL, `ABS(a - b) > 2` is not true
when either value is missing, so the first version of several checks silently passed
rows with missing data. Every check now counts a missing value as flagged.

## Known and accepted

- **PA differs by 1–2 between Savant and the MLB Stats API** (31 player-seasons). Both
  sources were confirmed against the live endpoints; this is a small difference in how
  each counts, not a download error.
- **Spray percentages that don't sum to 100** (3 player-seasons, 98.6–99.3%: David Bote
  2022, James McCann 2024, Kristian Campbell 2025, all 127–263 PA). Most likely one or two
  batted balls without a spray classification; too small to affect results.
- **No batted-ball leaderboard row** (2 player-seasons: Andrew Young 2021 with 47 balls in
  play, Zack Gelof 2025 with 48), below that leaderboard's 50-batted-ball minimum. They
  drop out of any model that uses pulled-air rate.
- **Batting hand is the player's current listing**, not per season, so a hitter who
  changed sides would be mislabeled in earlier seasons.
- **Savant can revise its expected stats.** Results reflect the data as downloaded on
  October 8, 2026.

## Design decisions

- **Join on MLBAM `player_id`, never on names.** Names carry accents (Suárez, Díaz) and
  suffixes (Jr.) that differ across sources.
- **Home park for players who changed teams:** the team where the player took the most PA;
  `primary_team_pa_share` records how much of the season that represents, so park
  analyses can exclude split seasons.
- **2021 is the last season pitchers batted** (the universal DH arrived in 2022). The
  100-PA floor excludes them: the only 2021 hitter in the data who regularly pitched is
  Shohei Ohtani (23 starts). The other 46 who pitched that year were position players
  in blowouts (at most 6 appearances, no starts), checked against MLB Stats API 2021
  pitching lines.
- **No 2020.** The 60-game season is excluded.
- **Cross-check source:** every player-season's PA, wOBA, and xwOBA is compared against
  Savant's expected-stats leaderboard, a separate endpoint from the one the data comes
  from.
