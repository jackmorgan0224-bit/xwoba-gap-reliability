"""Step 4: does adding the shrunk gap to xwOBA forecast next season's wOBA better?

Requires the step 2-3 tables (run src/step2_reliability.py and src/step3_traits.py first).

Every forecast is a weighted linear model of next-season wOBA, fitted only on season pairs
that end before the test season (rolling origin: test 2022->23, 2023->24, 2024->25,
2025->26). wOBA and xwOBA are measured relative to each season's league average, so the
test is about ranking and spacing hitters, not guessing next year's run environment.
Error = PA-weighted RMS error of next-season wOBA, in points (x1000); 95% intervals from
bootstrapping players.
Writes results/step4_*.csv.
"""

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import step3_traits as s3

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SEED = 20261008
BOOT = 2000

FORECASTS = {
    "wOBA": ["cwoba"],
    "xwOBA": ["cxwoba"],
    "xwOBA + shrunk gap": ["cxwoba", "shrunk_gap"],
    "xwOBA + shrunk gap + traits": ["cxwoba", "shrunk_gap"] + s3.TRAITS,
    "xwOBA + shrunk gap + traits, next park known": ["cxwoba", "shrunk_gap"] + s3.TRAITS,
}


def load_pairs(con) -> pd.DataFrame:
    players = s3.load_player_table(con)
    level = con.sql("""
        WITH league AS (
            SELECT season, SUM(woba * pa) / SUM(pa) AS lg_woba, SUM(xwoba * pa) / SUM(pa) AS lg_xwoba
            FROM player_season GROUP BY season
        )
        SELECT p.player_id, p.season, p.woba - l.lg_woba AS cwoba, p.xwoba - l.lg_xwoba AS cxwoba
        FROM player_season AS p JOIN league AS l USING (season)
    """).df()
    players = players.merge(level, on=["player_id", "season"])
    players["park_exposure"] = players["park_exposure_known"]  # forecast-safe (step 3)
    nxt = players[["player_id", "season", "cwoba", "cgap", "pa"]].rename(
        columns={"cwoba": "cwoba_2", "cgap": "cgap_2", "pa": "pa_2"})
    nxt["season"] -= 1
    pairs = players.merge(nxt, on=["player_id", "season"])
    pairs = pairs.rename(columns={"next_park_exposure": "park_exposure_2"})
    return pairs.dropna(subset=s3.TRAITS + ["park_exposure_2", "cxwoba", "cwoba_2", "cgap_2"]).reset_index(drop=True)


def fit_c(train: pd.DataFrame) -> float:
    g1, g2, n1, w = (train[c].to_numpy(float) for c in ("cgap", "cgap_2", "bip", "pa_2"))
    grid = np.linspace(1, 20000, 4000)
    return float(grid[int(np.argmin([(w * (g2 - n1 / (n1 + c) * g1) ** 2).sum() for c in grid]))])


def design(df: pd.DataFrame, cols: list[str], mean: pd.Series, sd: pd.Series, next_park: bool) -> np.ndarray:
    x = df[cols].copy()
    if next_park:
        x["park_exposure"] = df["park_exposure_2"]
    for t in s3.TRAITS:
        if t in x:
            x[t] = (x[t] - mean[t]) / sd[t]
    return np.column_stack([np.ones(len(df)), x.to_numpy(float)])


def rolling(pairs: pd.DataFrame) -> pd.DataFrame:
    tested = []
    for t in range(2022, 2026):
        train = pairs[pairs["season"] + 1 <= t].copy()
        test = pairs[pairs["season"] == t].copy()
        c = fit_c(train)
        for df in (train, test):
            df["shrunk_gap"] = df["bip"] / (df["bip"] + c) * df["cgap"]
        mean, sd = train[s3.TRAITS].mean(), train[s3.TRAITS].std()
        for name, cols in FORECASTS.items():
            next_park = name.endswith("next park known")
            beta = s3.wls(design(train, cols, mean, sd, next_park), train["cwoba_2"].to_numpy(),
                          train["pa_2"].to_numpy(float))
            test[f"pred_{name}"] = design(test, cols, mean, sd, next_park) @ beta
        test["c"] = c
        tested.append(test)
    return pd.concat(tested, ignore_index=True)


def score(tested: pd.DataFrame, rng) -> pd.DataFrame:
    def rmse(df, name):
        return np.sqrt(np.average((df["cwoba_2"] - df[f"pred_{name}"]) ** 2, weights=df["pa_2"]))

    by_player = tested.groupby("player_id").indices
    ids = np.array(list(by_player))
    boot = {n: [] for n in FORECASTS}
    for _ in range(BOOT):
        sample = tested.iloc[np.concatenate([by_player[p] for p in rng.choice(ids, len(ids))])]
        base = rmse(sample, "xwOBA")
        for n in FORECASTS:
            boot[n].append(rmse(sample, n) - base)
    return pd.DataFrame([{
        "forecast": n,
        "rmse_points": rmse(tested, n) * 1000,
        "vs_xwoba_points": (rmse(tested, n) - rmse(tested, "xwOBA")) * 1000,
        "lo": np.percentile(boot[n], 2.5) * 1000,
        "hi": np.percentile(boot[n], 97.5) * 1000,
        "share_of_boot_better": float(np.mean(np.array(boot[n]) < 0)),
    } for n in FORECASTS])


def decomposition(pairs: pd.DataFrame, rng, min_pa: int = 100) -> pd.DataFrame:
    """Effect of this season's gap on next season's gap, xwOBA, and wOBA, holding xwOBA fixed.

    next wOBA = next xwOBA + next gap, so the wOBA coefficient is the sum of the other two.
    """
    d = pairs[(pairs["pa"] >= min_pa) & (pairs["pa_2"] >= min_pa)].reset_index(drop=True)
    d["cxwoba_2"] = d["cwoba_2"] - d["cgap_2"]
    X = np.column_stack([np.ones(len(d)), d["cxwoba"], d["cgap"]])
    w = d["pa_2"].to_numpy(float)
    targets = {"next gap": "cgap_2", "next xwOBA": "cxwoba_2", "next wOBA": "cwoba_2"}
    point = {k: s3.wls(X, d[v].to_numpy(), w) for k, v in targets.items()}
    by_player = d.groupby("player_id").indices
    ids = np.array(list(by_player))
    boot = {k: [] for k in targets}
    for _ in range(BOOT):
        idx = np.concatenate([by_player[p] for p in rng.choice(ids, len(ids))])
        for k, v in targets.items():
            boot[k].append(s3.wls(X[idx], d[v].to_numpy()[idx], w[idx]))
    rows = []
    for k in targets:
        b = np.array(boot[k])
        for j, term in ((1, "this season's xwOBA"), (2, "this season's gap")):
            rows.append({"min_pa": min_pa, "outcome": k, "term": term, "coefficient": point[k][j],
                         "lo": np.percentile(b[:, j], 2.5), "hi": np.percentile(b[:, j], 97.5),
                         "pairs": len(d)})
    return pd.DataFrame(rows)


def main() -> None:
    os.chdir(ROOT)
    RESULTS.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    con = duckdb.connect(str(ROOT / "data" / "statcast.duckdb"))
    pairs = load_pairs(con)
    tested = rolling(pairs)
    overall = score(tested, rng)
    by_season = pd.concat([score(g, rng).assign(test_pair=f"{t}-{str(t + 1)[2:]}")
                           for t, g in tested.groupby("season")], ignore_index=True)
    decomp = pd.concat([decomposition(pairs, rng, m) for m in (100, 300)], ignore_index=True)
    decomp.to_csv(RESULTS / "step4_decomposition.csv", index=False, float_format="%.4f")
    print(decomp.round(3).to_string(index=False))
    overall.to_csv(RESULTS / "step4_forecast.csv", index=False, float_format="%.4f")
    by_season.to_csv(RESULTS / "step4_forecast_by_season.csv", index=False, float_format="%.4f")
    pd.DataFrame([{"test_pairs": len(tested), "players": tested["player_id"].nunique(),
                   "c_by_fold": "; ".join(f"{t}: {c:.0f}" for t, c in tested.groupby("season")["c"].first().items())}]
                 ).to_csv(RESULTS / "step4_summary.csv", index=False)
    pd.set_option("display.width", 200, "display.max_columns", 20)
    print(f"Test pairs: {len(tested)}, players: {tested['player_id'].nunique()}")
    print(overall.round(3).to_string(index=False))
    print(by_season.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
