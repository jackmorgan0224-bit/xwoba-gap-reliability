# Step 4: Does the gap help project next season's wOBA?

**Answer.** No. To project a hitter's next-season wOBA, use his xwOBA, pulled a bit less than
halfway back to the league average, and ignore his wOBA–xwOBA gap. Adding the gap,
discounted the step 2 way, doesn't improve the forecast (+0.01 points of error, 95% CI −0.04
to +0.06), and neither do the step 3 traits. The reason: a hitter's gap *does* partly repeat
(step 2), but hitters who beat their xwOBA also tend to see their xwOBA fall the next year by
about as much, so the two cancel.

## Method

- **Forecasts.** Each is a PA-weighted linear model of next-season wOBA, fitted only on
  season pairs that end before the test season, then scored on 2022→23, 2023→24, 2024→25,
  and 2025→26 (1,426 test pairs, 563 hitters, 100+ PA in both seasons).
- **Fair comparison.** Every forecast gets its own fitted regression toward the mean, so
  xwOBA isn't penalized for being used raw.
- **League environment.** wOBA and xwOBA are measured against each season's league
  average, so the test is about ranking and spacing hitters, not guessing next year's
  offensive level.
- Error = PA-weighted RMS error of next-season wOBA, in points (.001); 95% intervals
  bootstrap players. Code: [`src/step4_projection.py`](../src/step4_projection.py).

## Results

| Forecast | Error (points) | vs. xwOBA (95% CI) |
|---|---:|---|
| This season's wOBA | 33.4 | +1.75 (+1.04 to +2.46) worse |
| **This season's xwOBA** | **31.6** | — |
| xwOBA + discounted gap | 31.6 | +0.01 (−0.04 to +0.06) |
| xwOBA + discounted gap + traits | 31.6 | +0.01 (−0.22 to +0.24) |
| Same, with next season's parks known | 31.6 | −0.06 (−0.30 to +0.16) |

xwOBA beats wOBA clearly. Nothing added to xwOBA beats xwOBA alone. The pattern holds in
each test season ([`results/step4_forecast_by_season.csv`](../results/step4_forecast_by_season.csv)).

### Why the gap doesn't help

Holding this season's xwOBA fixed, what does this season's gap predict about next season?
(All 1,780 pairs with 100+ PA in both seasons; regulars with 300+ PA in both, 994 pairs.)

| Next season's... | All hitters | Regulars |
|---|---|---|
| gap | +0.14 (0.08 to 0.19) | +0.21 (0.15 to 0.29) |
| xwOBA | −0.13 (−0.19 to −0.06) | −0.12 (−0.21 to −0.02) |
| **wOBA** (the sum) | **+0.01 (−0.08 to +0.10)** | **+0.10 (−0.02 to +0.20)** |

The gap repeats, as step 2 found. But a hitter who beat his xwOBA this season has a lower
xwOBA next season than his current xwOBA would suggest, by about as much. Why isn't
established here; one possibility is that the contact patterns xwOBA misjudges (step 3:
pulled vs. non-pulled hard fly balls) also make this season's xwOBA itself a slightly biased
read of the hitter. For regulars a small net effect may remain (+0.10), but it isn't
statistically clear.

## The projection rule

Fitted on the 994 season pairs of regulars:

> **2027 wOBA ≈ league wOBA + .003 + 0.56 × (2026 xwOBA − league xwOBA)**

Typical error: ±28 points. A hitter 40 points above the league in xwOBA projects about 25
points above the league next year. Step 5 applies this to 2026 hitters.

## Limitations

- Offense only, one season of history, no age adjustment. A full projection system would
  weight several seasons and age; the point here is which inputs earn a place, and the gap
  doesn't.
- 2027's league offensive level is unknown; projections are relative to 2026's.
