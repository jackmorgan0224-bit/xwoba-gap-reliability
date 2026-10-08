# Step 2: How much of a gap should you believe, given the sample?

**Answer.** Very little until the sample is large. A hitter's wOBA–xwOBA gap is half
signal only after about **1,000 balls in play** (95% CI 780–1,370), roughly 1,500 plate
appearances or two and a half full seasons. For one full season (about 400 balls in play,
590 PA), believe **28%** of the gap as a description of that season and **25%** as a
forecast for the next. Applying that discount beats both trusting the gap and ignoring it
on seasons the model never saw.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/step2_trust_dark.png">
  <img alt="Share of the gap to believe rises from about 3% at 25 balls in play to 28% at 400 and 37% at 600 for the current season, and slightly lower for next season." src="figures/step2_trust_light.png">
</picture>

## Data

- **740,633 balls in play** (2021–2026 regular season) from Baseball Savant's Statcast
  Search, one row per plate appearance ([`src/fetch_statcast.py`](../src/fetch_statcast.py)).
- **The gap comes only from balls in play.** xwOBA credits walks, strikeouts, and hit by
  pitches at their actual value, so each ball in play contributes actual minus expected
  wOBA, and sample size is counted in balls in play.
- **Exact weights.** Statcast Search's per-pitch `woba_value` uses rounded weights (single
  0.9, home run 2.0) and counts reaching on an error as a single. Left as is, every single
  would carry a .02 bonus, and singles rate is a stable skill, so contact hitters would
  look like they have a persistent gap. Each season's exact weights were recovered from the
  leaderboard by least squares ([`results/step2_woba_weights.csv`](../results/step2_woba_weights.csv)).
  For 2021: single .879, double 1.244, triple 1.565, HR 2.005, walk .691, HBP .724, and
  reaching on an error 0. With them, 97.3% of rebuilt wOBAs match the leaderboard to its
  rounding.

### Reconciliation with the leaderboard

| Check | Result |
|---|---|
| Duplicate plate appearances | 0 |
| Player-seasons missing from the PA-level data | 0 of 2,774 |
| Player-seasons whose PA differs | 0 |
| Rebuilt wOBA within leaderboard rounding (.0005) | 97.3% (max difference .0007) |
| Rebuilt xwOBA within .002 | 87.2% (max .014) |
| Rebuilt gap vs. leaderboard gap | r = .998; RMS difference 1.4 points vs. a 23.0-point spread across hitters |
| Balls in play with no Statcast xwOBA (excluded) | 2,640 of 740,633 (0.4%) |

The per-ball expected values in Statcast Search don't reproduce the leaderboard's xwOBA
exactly. The source of the small differences couldn't be identified: in 2021 data it
isn't explained by sprint speed, errors, sacrifice flies, or any other event type tested. The rebuilt gap tracks
the leaderboard gap at r = .998, so results carry over.

## Method

**A. This season (split-half reliability).** For every player-season with at least 2n
balls in play, draw 2n of his balls in play at random, split them n and n, and correlate
the two halves' average residuals across hitters. Repeat 200 times per n. This measures
reliability at exactly n balls in play, with no extrapolation. Residuals are centered on
each season's league average.

**B. Next season (carryover).** On consecutive-season pairs, find the C for which
`gap_next ≈ bip / (bip + C) × gap_this` fits best (weighted by next-season PA).

Both follow the standard shrinkage curve `share to believe = n / (n + C)`, where C is the
sample at which the gap is half signal. A 95% interval for C comes from 300 bootstrap
resamples of players. Code: [`src/step2_reliability.py`](../src/step2_reliability.py).

## Results

| Balls in play | ≈ PA | Believe, this season | Believe, next season |
|---:|---:|---:|---:|
| 50 | 70 | 5% | 4% |
| 100 | 150 | 9% | 8% |
| 200 | 300 | 16% | 14% |
| 300 | 440 | 23% | 20% |
| 400 | 590 | 28% | 25% |
| 500 | 740 | 33% | 29% |

- **C = 1,017 balls in play this season** (95% CI 778–1,368) and **1,219 for next season.**
  Fitting only on seasons through 2022, 2023, 2024, or 2025 gives C = 973, 915, 1,079, and
  1,092, so the estimate is stable.
- **The curve isn't an artifact of who has big samples.** Repeating the split-half on one
  fixed group (the 69 player-seasons with 500+ balls in play) traces the same curve
  (for example .14 at 150 per half vs. .13 for all hitters).
- **Next season is only a little lower than this season.** Most of what makes a gap real
  within a season carries into the next one; the gap is mostly noise, not a real skill
  that fades.
- **It agrees with step 1.** Step 1 found a year-over-year slope of .25 for hitters with
  300+ PA in both seasons, from a different method and data source.

### Does the discount actually forecast better?

Each season's gap was predicted from the previous season (2022→23 through 2025→26),
fitting C only on earlier seasons. Error is the PA-weighted RMS error of next season's gap,
in wOBA points; intervals bootstrap players.

| Forecast | Error | vs. "gap is pure noise" (95% CI) |
|---|---:|---|
| Gap is pure noise (predict 0) | 19.5 | — |
| Trust the whole gap | 26.2 | +6.73 (+5.64 to +7.80) worse |
| Shrink by this-season reliability | 19.1 | −0.38 (−0.69 to −0.09) better |
| Shrink by next-season carryover | 19.1 | −0.39 (−0.66 to −0.13) better |

Trusting the whole gap is far worse than ignoring it. Shrinking it is a small but reliable
improvement over ignoring it.

## What this means for a front office

- **A gap in April or May is almost all noise.** At 100 balls in play, believe under 10%.
- **One full season: keep about a quarter.** A hitter who beat his xwOBA by .040 should
  be projected about .010 above it next year.
- **Never take the gap at face value.** That forecast is worse than assuming every gap is
  luck.

## Limitations

- Split-half reliability treats every ball in play as exchangeable within a season, so it
  doesn't capture within-season changes (injury, swing changes).
- The rebuilt gap matches the leaderboard at r = .998, not exactly.
- Hitters need 100+ PA to be included; players who lose their jobs early aren't in the
  forecast test.
