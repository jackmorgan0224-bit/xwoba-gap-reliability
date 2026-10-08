"""Step 1: how strongly does a hitter's wOBA - xwOBA gap persist from one season to the next?

Compares 2021-2026 with 2015-2019 (the seasons the published estimates used), using
today's Savant data for both, so any difference reflects the game rather than a change
in how xwOBA is calculated. Writes results/step1_*.csv.

Method
- Gap centered on each season's league average (sql/03_step1_pairs.sql).
- Headline statistic: correlation of season-1 gap with season-2 gap, weighted by the
  harmonic mean of the two seasons' PA. The weighted slope is reported alongside: the
  share of a season-1 gap that shows up again in season 2.
- 95% intervals from a cluster bootstrap that resamples players (with all their pairs),
  since most players appear in several pairs.
- Replications of Edwards (2017) and Melchior (2019) use their sample rules and their
  statistic (plain, uncentered Pearson r), applied to today's data.
"""

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
N_BOOT = 2000
SEED = 20261008
MAIN_MIN_PA = 300


def weighted_r_and_slope(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    w = w / w.sum()
    mx, my = (w * x).sum(), (w * y).sum()
    cov = (w * (x - mx) * (y - my)).sum()
    vx, vy = (w * (x - mx) ** 2).sum(), (w * (y - my) ** 2).sum()
    return cov / np.sqrt(vx * vy), cov / vx


def summarize(pairs: pd.DataFrame, rng: np.random.Generator,
              cols: tuple[str, str] = ("cgap_1", "cgap_2")) -> dict:
    """Point estimates plus player-clustered bootstrap intervals for one subset of pairs."""
    x, y, w = pairs[cols[0]].to_numpy(), pairs[cols[1]].to_numpy(), pairs["weight"].to_numpy()
    r_w, slope_w = weighted_r_and_slope(x, y, w)
    r_plain = np.corrcoef(x, y)[0, 1]

    rows_by_player = [idx for idx in pairs.groupby("player_id").indices.values()]
    boot = np.empty((N_BOOT, 3))
    for b in range(N_BOOT):
        picked = rng.integers(0, len(rows_by_player), len(rows_by_player))
        idx = np.concatenate([rows_by_player[i] for i in picked])
        boot[b, :2] = weighted_r_and_slope(x[idx], y[idx], w[idx])
        boot[b, 2] = np.corrcoef(x[idx], y[idx])[0, 1]
    lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)

    return {
        "pairs": len(pairs),
        "players": pairs["player_id"].nunique(),
        "r_weighted": r_w, "r_weighted_lo": lo[0], "r_weighted_hi": hi[0],
        "slope_weighted": slope_w, "slope_lo": lo[1], "slope_hi": hi[1],
        "r_plain": r_plain, "r_plain_lo": lo[2], "r_plain_hi": hi[2],
    }


def era_difference(all_pairs: pd.DataFrame, min_pa: int, rng: np.random.Generator,
                   cols: tuple[str, str] = ("cgap_1", "cgap_2")) -> dict:
    """Recent minus history weighted r, bootstrapping players jointly (some play in both eras)."""
    pairs = all_pairs[all_pairs["min_pa"] >= min_pa].reset_index(drop=True)
    players = pairs["player_id"].unique()
    rows = {pid: idx for pid, idx in pairs.groupby("player_id").indices.items()}
    x, y, w = pairs[cols[0]].to_numpy(), pairs[cols[1]].to_numpy(), pairs["weight"].to_numpy()
    recent = (pairs["era"] == "recent").to_numpy()

    def diff(idx: np.ndarray) -> float:
        rec, hist = idx[recent[idx]], idx[~recent[idx]]
        return weighted_r_and_slope(x[rec], y[rec], w[rec])[0] - weighted_r_and_slope(x[hist], y[hist], w[hist])[0]

    point = diff(np.arange(len(pairs)))
    boot = np.array([
        diff(np.concatenate([rows[p] for p in rng.choice(players, len(players))]))
        for _ in range(N_BOOT)
    ])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"min_pa": min_pa, "r_recent_minus_history": point, "lo": lo, "hi": hi,
            "share_of_boot_below_zero": (boot < 0).mean()}


def main() -> None:
    os.chdir(ROOT)
    RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "statcast.duckdb"))
    con.execute((ROOT / "sql" / "03_step1_pairs.sql").read_text(encoding="utf-8"))
    pairs = con.sql("SELECT * FROM step1_pairs").df()
    rng = np.random.default_rng(SEED)

    # 1. Threshold ladder, both eras
    ladder = []
    for era in ("history", "recent"):
        for min_pa in (100, 200, 300, 400, 500):
            subset = pairs[(pairs["era"] == era) & (pairs["min_pa"] >= min_pa)].reset_index(drop=True)
            ladder.append({"era": era, "min_pa_both_seasons": min_pa, **summarize(subset, rng)})
    ladder = pd.DataFrame(ladder)
    ladder.to_csv(RESULTS / "step1_thresholds.csv", index=False, float_format="%.4f")

    # 2. Each season pair at the main threshold
    by_pair = []
    for (era, season_1), subset in pairs[pairs["min_pa"] >= MAIN_MIN_PA].groupby(["era", "season_1"]):
        by_pair.append({"era": era, "seasons": f"{season_1}-{str(season_1 + 1)[2:]}",
                        **summarize(subset.reset_index(drop=True), rng)})
    by_pair = pd.DataFrame(by_pair)
    by_pair.to_csv(RESULTS / "step1_by_season_pair.csv", index=False, float_format="%.4f")

    # 3. Shift ban (banned starting 2023): pairs entirely before, spanning, and after
    recent = pairs[(pairs["era"] == "recent") & (pairs["min_pa"] >= MAIN_MIN_PA)]
    windows = {
        "before ban (2021-22)": recent["season_1"] == 2021,
        "spans ban (2022-23)": recent["season_1"] == 2022,
        "after ban (2023-24 to 2025-26)": recent["season_1"] >= 2023,
    }
    shift = pd.DataFrame([{"window": name, **summarize(recent[mask].reset_index(drop=True), rng)}
                          for name, mask in windows.items()])
    shift.to_csv(RESULTS / "step1_shift_ban.csv", index=False, float_format="%.4f")

    # 4. Is the recent era really lower than 2015-2019?
    diffs = pd.DataFrame([era_difference(pairs, min_pa, rng) for min_pa in (300, 400, 500)])
    diffs.to_csv(RESULTS / "step1_era_difference.csv", index=False, float_format="%.4f")

    # 5. Replicate the published estimates with their sample rules and statistic
    hist = pairs[pairs["era"] == "history"]
    replications = [
        ("Edwards 2017: 400+ AB in 2015 and 2016", "R² = .17",
         hist[(hist["season_1"] == 2015) & (hist["min_ab"] >= 400)]),
        ("Melchior 2019: 2,000+ pitches in back-to-back seasons, 2015-2019", "r = .43 (R² = .17)",
         hist[hist["min_pitches"] >= 2000]),
    ]
    rep_rows = []
    for name, published, subset in replications:
        s = summarize(subset.reset_index(drop=True), rng, cols=("gap_1", "gap_2"))
        rep_rows.append({"study": name, "published": published, "pairs": s["pairs"],
                         "r_plain": s["r_plain"], "r_plain_lo": s["r_plain_lo"],
                         "r_plain_hi": s["r_plain_hi"], "r_squared": s["r_plain"] ** 2})
    rep = pd.DataFrame(rep_rows)
    rep.to_csv(RESULTS / "step1_replications.csv", index=False, float_format="%.4f")

    # 6. How much of the era difference runs through sprint speed?
    speed_rows = []
    for label, cols in [("gap (centered)", ("cgap_1", "cgap_2")),
                        ("gap with sprint-speed component removed", ("speed_gap_1", "speed_gap_2"))]:
        for era in ("history", "recent"):
            subset = pairs[(pairs["era"] == era) & (pairs["min_pa"] >= MAIN_MIN_PA)].reset_index(drop=True)
            speed_rows.append({"measure": label, "era": era, **summarize(subset, rng, cols=cols)})
        d = era_difference(pairs, MAIN_MIN_PA, rng, cols=cols)
        speed_rows.append({"measure": label, "era": "recent minus history",
                           "r_weighted": d["r_recent_minus_history"], "r_weighted_lo": d["lo"],
                           "r_weighted_hi": d["hi"]})
    speed = pd.DataFrame(speed_rows).astype({"pairs": "Int64", "players": "Int64"})
    speed.to_csv(RESULTS / "step1_speed.csv", index=False, float_format="%.4f")

    # Gap-speed correlation by season (300+ PA), to show the trend
    speed_trend = con.sql("""
        SELECT season, COUNT(*) AS hitters, CORR(woba_gap, sprint_speed) AS r_gap_speed
        FROM (SELECT season, pa, woba_gap, sprint_speed FROM history_season
              UNION ALL
              SELECT season, pa, woba_gap, sprint_speed FROM player_season)
        WHERE pa >= 300
        GROUP BY season ORDER BY season
    """).df()
    speed_trend.to_csv(RESULTS / "step1_speed_by_season.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 200, "display.max_columns", 20)
    for title, df in [("Threshold ladder", ladder), ("By season pair (300+ PA)", by_pair),
                      ("Shift ban (300+ PA)", shift), ("Recent minus history", diffs),
                      ("Replications", rep), ("Speed (300+ PA)", speed),
                      ("Gap-speed correlation by season", speed_trend)]:
        print(f"\n{title}\n{df.round(3).to_string(index=False)}")


if __name__ == "__main__":
    main()
