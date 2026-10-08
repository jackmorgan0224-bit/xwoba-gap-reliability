"""Step 2: how much of a hitter's wOBA - xwOBA gap should be trusted, given his sample size?

Two different questions, answered separately:
  A. Within-season reliability: how much of the gap we observed is the hitter rather than
     noise, this season? Measured by split-half correlation at exactly n balls in play.
  B. Next-season carryover: how much of the gap will show up again next season? Fitted on
     consecutive-season pairs and tested on seasons it wasn't fitted on.
A is the right discount for describing a season; B is the right discount for forecasting.

The gap comes entirely from balls in play (xwOBA credits walks, strikeouts, and HBP at
their actual value), so sample size is counted in balls in play (BIP).
Writes results/step2_*.csv.
"""

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SEED = 20261008
SPLIT_REPS = 200
BOOT = 300
HALF_SIZES = [25, 50, 75, 100, 150, 200, 250]


# ---------- data ----------

def fit_woba_weights(con) -> pd.DataFrame:
    """Each season's wOBA weights, fitted to the leaderboard wOBA by least squares.

    Statcast Search's per-pitch woba_value uses rounded weights, so the exact weights are
    recovered from the leaderboard: woba x denominator = sum of weight x event count.
    """
    counts = con.sql("""
        SELECT c.*, p.woba AS woba_leaderboard
        FROM statcast_counts AS c
        JOIN player_season AS p USING (player_id, season)
    """).df()
    rows = []
    for season, d in counts.groupby("season"):
        X = d[["n_1b", "n_2b", "n_3b", "n_hr", "n_bb", "n_hbp"]].to_numpy(float)
        w, *_ = np.linalg.lstsq(X, d["woba_leaderboard"] * d["denom"], rcond=None)
        rows.append({"season": season, **dict(zip(["w_1b", "w_2b", "w_3b", "w_hr", "w_bb", "w_hbp"], w))})
    return pd.DataFrame(rows)


def load(con) -> pd.DataFrame:
    con.execute((ROOT / "sql" / "04_statcast_pa.sql").read_text(encoding="utf-8"))
    weights = fit_woba_weights(con)
    con.register("weights_df", weights)
    con.execute("CREATE OR REPLACE TABLE woba_weights AS SELECT * FROM weights_df")
    con.execute((ROOT / "sql" / "04b_statcast_values.sql").read_text(encoding="utf-8"))
    return weights


def reconcile(con) -> pd.DataFrame:
    """Rebuilt PA / wOBA / xwOBA / gap vs. the leaderboard, every player-season."""
    df = con.sql("""
        SELECT p.player_id, p.season, p.pa, p.woba, p.xwoba, p.woba_gap,
               s.pa AS pa_rebuilt, s.woba AS woba_rebuilt, s.xwoba AS xwoba_rebuilt, s.gap AS gap_rebuilt
        FROM player_season AS p
        LEFT JOIN statcast_player_season AS s USING (player_id, season)
    """).df()
    missing_xwoba = con.sql("SELECT SUM(bip_missing_xwoba), SUM(bip) FROM statcast_counts").fetchone()
    werr = (df["woba_rebuilt"] - df["woba"]).abs()
    xerr = (df["xwoba_rebuilt"] - df["xwoba"]).abs()
    dupes = con.sql("""
        SELECT COUNT(*) - COUNT(DISTINCT (game_pk, at_bat_number)) FROM statcast_raw
    """).fetchone()[0]
    checks = [
        ("duplicate plate appearances (game_pk, at_bat_number)", int(dupes)),
        ("player-seasons (leaderboard, 100+ PA)", len(df)),
        ("missing from PA-level data", int(df["pa_rebuilt"].isna().sum())),
        ("PA differs", int((df["pa_rebuilt"] != df["pa"]).sum())),
        ("balls in play missing Statcast xwOBA", f"{missing_xwoba[0]} of {missing_xwoba[1]}"),
        ("wOBA within .0005 (leaderboard rounding)", f"{(werr <= 0.0005).mean():.1%}"),
        ("wOBA max difference", round(float(werr.max()), 5)),
        ("xwOBA within .0005", f"{(xerr <= 0.0005).mean():.1%}"),
        ("xwOBA within .002", f"{(xerr <= 0.002).mean():.1%}"),
        ("xwOBA max difference", round(float(xerr.max()), 5)),
        ("gap: correlation, rebuilt vs leaderboard", round(float(df["gap_rebuilt"].corr(df["woba_gap"])), 4)),
        ("gap: RMS difference (wOBA points x1000)", round(float(np.sqrt(((df["gap_rebuilt"] - df["woba_gap"]) ** 2).mean())) * 1000, 2)),
        ("gap: leaderboard SD across player-seasons (x1000)", round(float(df["woba_gap"].std()) * 1000, 2)),
    ]
    return pd.DataFrame(checks, columns=["check", "value"])


def bip_residuals(con) -> tuple[list[np.ndarray], pd.DataFrame]:
    """Per player-season arrays of ball-in-play residuals, centered on the season mean."""
    bip = con.sql("""
        SELECT player_id, season, resid - AVG(resid) OVER (PARTITION BY season) AS resid
        FROM statcast_pa
        WHERE is_bip AND resid IS NOT NULL  -- 0.3% of balls in play have no Statcast xwOBA
    """).df()
    groups = bip.groupby(["player_id", "season"])["resid"]
    keys = pd.DataFrame(list(groups.groups.keys()), columns=["player_id", "season"])
    arrays = [g.to_numpy() for _, g in groups]
    keys["bip"] = [len(a) for a in arrays]
    return arrays, keys


# ---------- A. within-season split-half reliability ----------

def split_half_curve(arrays: list[np.ndarray], rng: np.random.Generator,
                     reps: int = SPLIT_REPS, half_sizes=HALF_SIZES) -> pd.DataFrame:
    """Reliability at exactly n BIP: split 2n random BIP into n vs. n, correlate the halves.

    Each repetition draws one random ordering of every player-season's BIP and reuses it
    for every n (the first 2n balls), so all n are estimated from the same draws.
    """
    lengths = np.array([len(a) for a in arrays])
    width = lengths.max()
    padded = np.full((len(arrays), width), np.nan)
    for i, a in enumerate(arrays):
        padded[i, :len(a)] = a
    results = {n: [] for n in half_sizes}
    for _ in range(reps):
        keys = rng.random(padded.shape)
        keys[np.isnan(padded)] = np.inf
        order = np.argsort(keys, axis=1)
        shuffled = np.take_along_axis(padded, order, axis=1)
        for n in half_sizes:
            rows = lengths >= 2 * n
            if rows.sum() < 30:  # too few player-seasons for a stable correlation
                results[n].append(np.nan)
                continue
            a = shuffled[rows, :n].mean(axis=1)
            b = shuffled[rows, n:2 * n].mean(axis=1)
            results[n].append(np.corrcoef(a, b)[0, 1])
    return pd.DataFrame([{
        "bip_per_half": n,
        "player_seasons": int((lengths >= 2 * n).sum()),
        "reliability": float(np.mean(results[n])) if not np.isnan(results[n]).all() else np.nan,
        "split_lo": float(np.percentile(results[n], 2.5)) if not np.isnan(results[n]).all() else np.nan,
        "split_hi": float(np.percentile(results[n], 97.5)) if not np.isnan(results[n]).all() else np.nan,
    } for n in half_sizes])


def fit_c(curve: pd.DataFrame) -> float:
    """Least-squares C in r(n) = n / (n + C), weighted by the number of player-seasons."""
    curve = curve.dropna(subset=["reliability"])
    if len(curve) < 3:
        raise ValueError("Too few sample sizes with a reliability estimate to fit C")
    n, r, w = (curve[c].to_numpy(float) for c in ("bip_per_half", "reliability", "player_seasons"))
    grid = np.linspace(1, 3000, 30000)
    sse = [(w * (r - n / (n + c)) ** 2).sum() for c in grid]
    return float(grid[int(np.argmin(sse))])


def bootstrap_c(arrays, keys, rng) -> tuple[float, float]:
    """95% interval for C, resampling players (all of a player's seasons together)."""
    by_player = keys.groupby("player_id").indices
    players = np.array(list(by_player))
    cs = []
    for _ in range(BOOT):
        picked = rng.choice(players, len(players))
        idx = np.concatenate([by_player[p] for p in picked])
        curve = split_half_curve([arrays[i] for i in idx], rng, reps=20)
        cs.append(fit_c(curve))
    return tuple(np.percentile(cs, [2.5, 97.5]))


# ---------- B. next-season carryover ----------

def carryover_pairs(con, keys: pd.DataFrame) -> pd.DataFrame:
    pairs = con.sql("""
        SELECT player_id, season_1, pa_1, pa_2, gap_1, gap_2 FROM season_pairs
    """).df()
    means = con.sql("""
        SELECT season, SUM(woba_gap * pa) / SUM(pa) AS mean_gap FROM player_season GROUP BY season
    """).df().set_index("season")["mean_gap"]
    pairs["cgap_1"] = pairs["gap_1"] - pairs["season_1"].map(means)
    pairs["cgap_2"] = pairs["gap_2"] - (pairs["season_1"] + 1).map(means)
    bip = keys.rename(columns={"season": "season_1", "bip": "bip_1"})
    return pairs.merge(bip, on=["player_id", "season_1"], how="left")


def fit_carryover_c(pairs: pd.DataFrame) -> float:
    """C minimizing PA-weighted squared error of gap_2 - bip_1 / (bip_1 + C) * gap_1."""
    g1, g2, n1, w = (pairs[c].to_numpy(float) for c in ("cgap_1", "cgap_2", "bip_1", "pa_2"))
    grid = np.linspace(1, 20000, 20000)
    sse = [(w * (g2 - n1 / (n1 + c) * g1) ** 2).sum() for c in grid]
    return float(grid[int(np.argmin(sse))])


def rolling_test(pairs: pd.DataFrame, curve_c_by_season: dict, rng) -> pd.DataFrame:
    """Predict each season's gap from the prior season, fitting only on earlier pairs.

    Forecasts compared (PA-weighted RMSE of the next-season centered gap):
      no trust      predict 0 (gap is pure noise)
      full trust    predict the whole prior-season gap
      split-half    shrink by within-season reliability (step A), fitted on seasons <= t
      carryover     shrink by next-season carryover C, fitted on pairs ending <= t
    """
    rows = []
    for t in range(2022, 2026):  # predict t -> t+1 using only pairs that end by t
        train = pairs[pairs["season_1"] + 1 <= t]
        test = pairs[pairs["season_1"] == t].reset_index(drop=True)
        c_carry = fit_carryover_c(train)
        c_split = curve_c_by_season[t]
        n1 = test["bip_1"].to_numpy(float)
        preds = {
            "no trust": np.zeros(len(test)),
            "full trust": test["cgap_1"].to_numpy(),
            "split-half shrink": n1 / (n1 + c_split) * test["cgap_1"].to_numpy(),
            "carryover shrink": n1 / (n1 + c_carry) * test["cgap_1"].to_numpy(),
        }
        test = test.assign(**{f"pred_{k}": v for k, v in preds.items()}, c_carry=c_carry, c_split=c_split)
        rows.append(test)
    tested = pd.concat(rows, ignore_index=True)

    def rmse(df, col):
        return float(np.sqrt(np.average((df["cgap_2"] - df[col]) ** 2, weights=df["pa_2"])))

    names = ["no trust", "full trust", "split-half shrink", "carryover shrink"]
    point = {k: rmse(tested, f"pred_{k}") for k in names}
    by_player = tested.groupby("player_id").indices
    players = np.array(list(by_player))
    boot = {k: [] for k in names}
    for _ in range(2000):
        idx = np.concatenate([by_player[p] for p in rng.choice(players, len(players))])
        sample = tested.iloc[idx]
        base = rmse(sample, "pred_no trust")
        for k in names:
            boot[k].append(rmse(sample, f"pred_{k}") - base)
    out = pd.DataFrame([{
        "forecast": k,
        "rmse_points": point[k] * 1000,
        "vs_no_trust_points": (point[k] - point["no trust"]) * 1000,
        "vs_no_trust_lo": np.percentile(boot[k], 2.5) * 1000,
        "vs_no_trust_hi": np.percentile(boot[k], 97.5) * 1000,
    } for k in names])
    out.attrs["tested"] = tested
    return out


def main() -> None:
    os.chdir(ROOT)
    RESULTS.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    con = duckdb.connect(str(ROOT / "data" / "statcast.duckdb"))
    weights = load(con)
    weights.to_csv(RESULTS / "step2_woba_weights.csv", index=False, float_format="%.4f")
    print(weights.round(3).to_string(index=False))

    rec = reconcile(con)
    rec.to_csv(RESULTS / "step2_reconciliation.csv", index=False)
    print(rec.to_string(index=False))
    values = dict(zip(rec["check"], rec["value"]))
    if values["duplicate plate appearances (game_pk, at_bat_number)"] or values["PA differs"]             or values["missing from PA-level data"]:
        raise SystemExit("Reconciliation failed: fix the PA-level data before analysis")

    arrays, keys = bip_residuals(con)
    bip_per_pa = con.sql("SELECT COUNT(*) FILTER (WHERE is_bip) / COUNT(*) FILTER (WHERE is_pa) FROM statcast_pa").fetchone()[0]

    # A. Within-season reliability, all seasons pooled
    curve = split_half_curve(arrays, rng)
    c_all = fit_c(curve)
    c_lo, c_hi = bootstrap_c(arrays, keys, rng)
    curve["fitted"] = curve["bip_per_half"] / (curve["bip_per_half"] + c_all)
    curve.to_csv(RESULTS / "step2_split_half.csv", index=False, float_format="%.4f")

    # Same curve restricted to one fixed pool (player-seasons with 500+ BIP), to check that
    # the changing pool across n isn't driving the shape
    fixed = [a for a in arrays if len(a) >= 500]
    curve_fixed = split_half_curve(fixed, rng, reps=100)
    curve_fixed.to_csv(RESULTS / "step2_split_half_fixed_pool.csv", index=False, float_format="%.4f")

    # Per-season C for the rolling test (each fitted only on seasons <= t)
    c_by_season = {}
    for t in range(2022, 2026):
        idx = keys.index[keys["season"] <= t]
        c_by_season[t] = fit_c(split_half_curve([arrays[i] for i in idx], rng, reps=50))

    # B. Next-season carryover
    pairs = carryover_pairs(con, keys)
    c_carry_all = fit_carryover_c(pairs)
    test = rolling_test(pairs, c_by_season, rng)
    test.to_csv(RESULTS / "step2_forecast_test.csv", index=False, float_format="%.3f")

    # Front-office table: how much of a gap to keep at each sample size
    table = pd.DataFrame({"bip": [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]})
    table["approx_pa"] = (table["bip"] / bip_per_pa).round(-1).astype(int)
    table["keep_this_season"] = table["bip"] / (table["bip"] + c_all)
    table["keep_next_season"] = table["bip"] / (table["bip"] + c_carry_all)
    table.to_csv(RESULTS / "step2_trust_table.csv", index=False, float_format="%.3f")

    summary = pd.DataFrame([
        {"quantity": "C, within-season (BIP for 50% reliability)", "value": c_all, "lo": c_lo, "hi": c_hi},
        {"quantity": "C, next-season carryover (all pairs)", "value": c_carry_all, "lo": np.nan, "hi": np.nan},
        {"quantity": "Balls in play per plate appearance", "value": bip_per_pa, "lo": np.nan, "hi": np.nan},
    ])
    summary.to_csv(RESULTS / "step2_summary.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 200)
    for title, df in [("Split-half reliability", curve), ("Fixed pool (500+ BIP)", curve_fixed),
                      ("Summary", summary), ("Forecast test (points of wOBA x1000)", test),
                      ("Trust table", table)]:
        print(f"\n{title}\n{df.round(3).to_string(index=False)}")
    print("\nRolling C by season:", {k: round(v) for k, v in c_by_season.items()})


if __name__ == "__main__":
    main()
