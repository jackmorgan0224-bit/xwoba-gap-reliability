# Step 6: Do three seasons and age improve the projection, and does the gap help then?

**Answer.** Yes to the first, no to the second. Weighting three seasons of xwOBA and adding a simple aging curve cuts next-season forecast error by **0.86 points** (95% CI 0.28 to 1.45) compared with step 4's one-season rule. Adding a three-season gap to that model still changes nothing (−0.02 points, 95% CI −0.09 to +0.05). With more history the gap gets more reliable, but it still doesn't earn a place in the forecast.

## Method

Same test as [step 4](step4.md): every forecast is fitted only on season pairs that end before the test season and scored on 2022→23 through 2025→26 (1,426 test pairs, 100+ PA in both seasons). Error is PA-weighted RMS error of next-season wOBA relative to the league, in points; 95% intervals bootstrap players. Code: [`src/step6_multiseason.py`](../src/step6_multiseason.py).

| Forecast | How it works |
|---|---|
| **A. Step 4 rule** | This season's xwOBA, regressed toward league |
| **B. 3-season xwOBA** | xwOBA from this season and the two before, weighted 5/4/3 by PA (Marcel-style), then shrunk toward league by total weighted PA. The shrinkage constant is chosen on training data only. |
| **C. B + age** | Adds next season's age, with separate slopes before and after 27. Birthdates from the MLB Stats API. |
| **D. C + 3-season gap** | Adds the wOBA–xwOBA gap, weighted and shrunk the same way |

Hitters with fewer than three seasons simply use what they have (a season under 100 PA counts as missing).

## Results

| Forecast | Error (points) | vs. step 4 rule (95% CI) |
|---|---:|---|
| A. This season's xwOBA (step 4) | 31.62 | — |
| B. 3-season xwOBA | 31.19 | −0.43 (−1.08 to +0.17) |
| **C. 3-season xwOBA + age** | **30.76** | **−0.86 (−1.45 to −0.28) better** |
| D. C + 3-season gap | 30.74 | −0.88 (−1.47 to −0.29); vs. C: −0.02 (−0.09 to +0.05) |

- **Age matters more than the extra seasons.** Three seasons alone help a little (B), but the improvement is only clear once age is added (C).
- **The gap still adds nothing (D vs. C).** This closes the loophole in step 4, where one season of gap might have been too noisy to help. With three seasons it's still no help.

## The new projection rule

Fitted on regulars (300+ PA in both seasons, 994 pairs), in points of wOBA relative to league:

> **2027 wOBA ≈ league + 3.8 + 1.03 × weighted xwOBA × WPA / (WPA + 2,750) + age adjustment**

- **Weighted xwOBA:** seasons weighted 5/4/3 by PA. **WPA:** that same weighted PA total. A hitter with three full seasons (≈7,000 weighted PA) keeps about 74% of his xwOBA edge over league; one with a single 500-PA season keeps about 49%.
- **Age adjustment:** about **+1.5 points per year younger than 27** and **−1.3 points per year older than 27**. A 24-year-old gains about 4.5 points; a 36-year-old loses about 12.
- **Typical miss:** ±28 points on regulars, in-sample (±28 for the step 4 rule too). The out-of-sample gain above is real but modest; this is a better ranking, not a crystal ball.

## What changes on the 2027 board

[`results/step6_board.csv`](../results/step6_board.csv) has both projections for all 205 hitters with 400+ PA in 2026. The median hitter moves 5 points. The big moves are established stars whose 2026 lagged their track record: Juan Soto (+33 vs. step 5), Vladimir Guerrero Jr. (+32), Shohei Ohtani (+27). The memo now uses this board.

## Limitations

- Offense only. Age is a simple two-slope curve, not position- or skill-specific.
- Three seasons is the most the 2021–26 data allows for most hitters; 2020's shortened season is excluded.
- 2027's league offensive level is unknown; projections are relative to 2026's (.319).
