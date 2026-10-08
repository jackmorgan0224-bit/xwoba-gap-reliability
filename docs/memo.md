# Memo: Reading 2026 batting lines for 2027 decisions

**To:** Baseball Operations · **From:** Jack Eisinger · **Date:** October 8, 2026
**Re:** Which 2026 batting lines overstate or understate what to expect in 2027

## Bottom line

1. **Price hitters on xwOBA, not wOBA, and ignore the gap between them.** A hitter's 2026
   wOBA–xwOBA gap adds nothing to a 2027 projection once xwOBA is known
   ([step 4](step4.md)). Rule: 2027 wOBA ≈ league + .003 + 0.56 × (2026 xwOBA − league).
   Typical miss: ±28 points.
2. **Randy Arozarena's 2026 line overstates him most among the pending free agents
   checked:** .379 wOBA, but a .348 xwOBA projects to .339.
3. **On our roster, Marcus Semien's 2026 understates him most:** .276 wOBA, .300 xwOBA,
   projects to .312. Bo Bichette and Brett Baty also project about 20 points above their 2026
   wOBA.

## Pending free agents

Hitters named as pending free agents in MLB.com's
[free agents by team](https://www.mlb.com/news/baseball-s-biggest-free-agents-by-team-for-2026-2027)
(updated August 10, 2026), 400+ PA in 2026. 2026 league wOBA: .319.

| Hitter | 2026 team | PA | 2026 wOBA | 2026 xwOBA | 2027 projection | 2026 line vs. projection |
|---|---|---:|---:|---:|---:|---:|
| Randy Arozarena | SEA | 670 | .379 | .348 | .339 | +40 |
| Brandon Lowe | PIT | 655 | .355 | .331 | .330 | +25 |
| Luis Arraez | SF, PHI | 655 | .331 | .307 | .316 | +15 |
| George Springer | TOR | 517 | .320 | .306 | .316 | +4 |
| Jazz Chisholm Jr. | NYY | 532 | .312 | .294 | .309 | +3 |
| Gleyber Torres | DET | 420 | .328 | .325 | .326 | +2 |

Positive = the 2026 line is above what to expect in 2027 (points of wOBA). Arozarena, Lowe,
and Arraez will be marketed on 2026 numbers that their contact quality doesn't support.

## Mets hitters (400+ PA in 2026)

| Hitter | PA | 2026 wOBA | 2026 xwOBA | 2027 projection | 2026 line vs. projection |
|---|---:|---:|---:|---:|---:|
| Juan Soto | 482 | .385 | .411 | .375 | +10 |
| Carson Benge | 654 | .342 | .341 | .335 | +7 |
| Francisco Lindor | 469 | .322 | .331 | .330 | −8 |
| Francisco Álvarez | 420 | .313 | .322 | .325 | −12 |
| A.J. Ewing | 492 | .311 | .320 | .324 | −13 |
| Brett Baty | 473 | .304 | .321 | .324 | −20 |
| Bo Bichette | 696 | .309 | .330 | .329 | −20 |
| Marcus Semien | 547 | .276 | .300 | .312 | −36 |

- **Soto's +10 isn't a warning.** It's ordinary regression toward the league for the best
  contact quality on the team (.411 xwOBA); he still projects highest by 40 points.
- **Seven of eight regulars hit below their xwOBA in 2026.** Citi Field may be part of it:
  across 2021–26, all hitters' results at Citi Field ran 8 points per ball in play below
  xwOBA, the 7th-lowest of 32 parks ([step 3](step3.md)). Adjusting projections for park didn't
  measurably improve accuracy, so this is context, not an extra adjustment.
- **Luis Robert Jr. (club option, $20 million, per MLB.com):** only 230 PA in 2026, so
  outside the board. His xwOBA was .321 in both 2025 (431 PA) and 2026, which projects to
  about .324, near league average. That's offense only; defense and baserunning are outside
  this model.

## Before acting

- **Contract status** comes only from the MLB.com article above (August 2026). Confirm
  options, opt-outs, and extensions against our own records.
- **Projections are offense only** and use one season, with no age adjustment. They rank
  hitters by what 2026 contact quality supports; they aren't full player valuations.
- **Individual projections are uncertain** (±28 points), so a 2026 line that differs from
  projection by 10–15 points is within normal noise. The board is most useful at its ends.

Full board: [`results/step5_board.csv`](../results/step5_board.csv) (205 hitters with 400+ PA).
