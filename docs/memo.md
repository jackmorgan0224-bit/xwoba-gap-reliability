# Memo: Reading 2026 batting lines for 2027 decisions

**To:** Baseball Operations · **From:** Jack Eisinger · **Date:** October 12, 2026 (updated from October 8 with the step 6 projection)
**Re:** Which 2026 batting lines overstate or understate what to expect in 2027

## Bottom line

1. **Price hitters on xwOBA, not wOBA, and ignore the gap between them.** The wOBA–xwOBA gap adds nothing to a projection, whether it uses one season ([step 4](step4.md)) or three ([step 6](step6.md)). Projections here weight three seasons of xwOBA and adjust for age, which beats a one-season rule out of sample. Typical miss: ±28 points.
2. **Randy Arozarena's 2026 line overstates him most among the pending free agents checked:** .379 wOBA, but he projects to .329, 50 points lower.
3. **On our roster, Marcus Semien's 2026 understates him most** (.276 vs. a .306 projection). Seven of eight regulars project above their 2026 wOBA, Juan Soto included.
4. **The biggest understated bats are stars on long-term deals,** led by Vladimir Guerrero Jr. (−57). The realistic buy-low targets are a tier down: Jarren Duran, Cam Smith, Dylan Crews, and Matt McLain.

## Pending free agents

Hitters named as pending free agents in MLB.com's [free agents by team](https://www.mlb.com/news/baseball-s-biggest-free-agents-by-team-for-2026-2027) (updated August 10, 2026), 400+ PA in 2026. 2026 league wOBA: .319.

| Hitter | 2026 team | Age in 2027 | PA | 2026 wOBA | 2026 xwOBA | 2027 projection | 2026 line vs. projection |
|---|---|---:|---:|---:|---:|---:|---:|
| Randy Arozarena | SEA | 32 | 670 | .379 | .348 | .329 | +50 |
| Brandon Lowe | PIT | 32 | 655 | .355 | .331 | .328 | +27 |
| Luis Arraez | SF | 30 | 655 | .331 | .307 | .314 | +17 |
| Gleyber Torres | DET | 30 | 420 | .328 | .325 | .332 | −4 |
| Jazz Chisholm Jr. | NYY | 29 | 532 | .312 | .294 | .319 | −7 |
| George Springer | TOR | 37 | 517 | .320 | .306 | .330 | −10 |

Positive = the 2026 line is above what to expect in 2027 (points of wOBA).
- **Arozarena, Lowe, and Arraez will be marketed on 2026 numbers that neither their contact quality nor their track record supports.** Arozarena's gap widened with the age adjustment (+40 → +50).
- **Torres, Chisholm, and Springer are within normal noise** (±28). Springer's .330 leans on strong earlier seasons; at 37, discount it further.

## Mets hitters (400+ PA in 2026)

| Hitter | Age in 2027 | PA | 2026 wOBA | 2026 xwOBA | 2027 projection | 2026 line vs. projection |
|---|---:|---:|---:|---:|---:|---:|
| Carson Benge | 24 | 654 | .342 | .341 | .340 | +2 |
| Francisco Álvarez | 25 | 420 | .313 | .322 | .325 | −12 |
| Francisco Lindor | 33 | 469 | .322 | .331 | .339 | −17 |
| A.J. Ewing | 22 | 492 | .311 | .320 | .331 | −20 |
| Brett Baty | 27 | 473 | .304 | .321 | .325 | −21 |
| Juan Soto | 28 | 482 | .385 | .411 | .407 | −22 |
| Bo Bichette | 29 | 696 | .309 | .330 | .332 | −23 |
| Marcus Semien | 36 | 547 | .276 | .300 | .306 | −30 |

- **The roster is better than its 2026 numbers.** Seven of eight regulars project above their 2026 wOBA. Citi Field may be part of it: across 2021–26, all hitters' results there ran 8 points per ball in play below xwOBA, the 7th-lowest of 32 parks ([step 3](step3.md)). Adjusting for park didn't measurably improve forecasts, so this is context, not an extra adjustment.
- **Soto flipped from "slightly overstated" to "understated."** One season of regression (step 5) pulled him toward league; three elite seasons say his .411 xwOBA is mostly real. He projects highest on the roster by 67 points.
- **Semien is still understated, but he's 36.** The age adjustment already takes about 12 points off; a .306 projection is a below-average bat.
- **Luis Robert Jr. is no longer a Mets decision.** He finished 2026 with Baltimore (current team per the MLB Stats API, October 8, 2026).

## Understated hitters on other teams

Hitters whose 2026 line sits 30+ points below their projection.

| Hitter | 2026 team | Age in 2027 | PA | 2026 wOBA | 2026 xwOBA | 2027 projection | 2026 line vs. projection |
|---|---|---:|---:|---:|---:|---:|---:|
| Vladimir Guerrero Jr. | TOR | 28 | 609 | .305 | .331 | .362 | −57 |
| Jarren Duran | BOS | 30 | 608 | .274 | .301 | .320 | −46 |
| Salvador Perez | KC | 37 | 627 | .285 | .316 | .328 | −43 |
| Cal Raleigh | SEA | 30 | 530 | .297 | .312 | .338 | −41 |
| J.T. Realmuto | PHI | 36 | 467 | .275 | .317 | .314 | −39 |
| Corey Seager | TEX | 33 | 436 | .320 | .350 | .357 | −37 |
| Jackson Merrill | SD | 24 | 664 | .320 | .347 | .354 | −34 |
| Austin Riley | ATL | 30 | 630 | .290 | .299 | .323 | −33 |
| Matt McLain | CIN | 27 | 496 | .272 | .293 | .305 | −33 |
| Ketel Marte | AZ | 33 | 624 | .323 | .349 | .355 | −32 |
| Cam Smith | HOU | 24 | 568 | .293 | .316 | .323 | −30 |
| Dylan Crews | WSH | 25 | 443 | .294 | .317 | .324 | −30 |

- **The stars (Guerrero, Raleigh, Seager, Merrill, Riley, Marte) are mostly not available.** Per press reports, all six are on long-term contracts. For them, the board's value is a warning not to read their 2026 lines as decline, for example when they show up in division matchups.
- **Realistic targets are a tier down.** Duran, Smith, Crews, and McLain project as roughly league-average bats (.305–.324) coming off down years that their contact and track record don't support. Smith and Crews, at 24 and 25, are the cleanest cases.
- **Discount the catchers less than before, but still discount them.** Perez (37) and Realmuto (36) already carry the age adjustment; catcher-specific aging is likely steeper than this simple curve.
- **Duran's decline looks partly real:** his xwOBA fell three straight years (.340, .326, .301).
- Four more hitters were understated by 30+ but project below .310 (Nasim Nuñez, Ezequiel Tovar, Zach McKinstry, Evan Carter), so a cheaper price still buys a below-average bat.

## Before acting

- **Contract status** comes from public reporting (MLB.com, August 2026, and press reports). Confirm options, opt-outs, and extensions against our own records.
- **Projections are offense only** and use a simple two-slope age curve (peak 27), not position-specific aging. They rank hitters by what contact quality and track record support; they aren't full player valuations.
- **Individual projections are uncertain** (±28 points), so a gap of 10–15 points between the 2026 line and the projection is within normal noise. The board is most useful at its ends.

Full board, with both the step 5 and step 6 projections: [`results/step6_board.csv`](../results/step6_board.csv) (205 hitters with 400+ PA).
