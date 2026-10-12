"""Step 6: does a 3-season, age-adjusted projection beat step 4's one-season xwOBA rule,
and does the gap help once three seasons are used?

Forecasts of next-season wOBA (relative to league), each fitted only on season pairs that end
before the test season and scored on 2022->23 through 2025->26, same as step 4:
  A  step 4 rule: this season's xwOBA
  B  3-season xwOBA: seasons weighted 5/4/3 by PA, shrunk toward league by total weighted PA
  C  B + age (separate slopes before and after 27)
  D  C + 3-season gap, shrunk the same way
Error = PA-weighted RMS error in points (x1000); 95% intervals from bootstrapping players.
Ages use birthdates from the MLB Stats API (cached in data/raw/birthdates.csv).
Writes results/step6_forecast.csv, results/step6_model.csv, results/step6_board.csv.
"""

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RAW = ROOT / "data" / "raw"
WEIGHTS = (5, 4, 3)          # this season, last season, two seasons ago
C_GRID = np.arange(100, 6001, 50)
PEAK_AGE = 27
TEST_TARGETS = (2023, 2024, 2025, 2026)
BOOT = 1000
SEED = 20261012
MIN_PA_FIT, MIN_PA_BOARD = 300, 400


def load_seasons(con) -> pd.DataFrame:
    return con.sql("""
        WITH league AS (
            SELECT season, SUM(woba * pa) / SUM(pa) AS lg_woba, SUM(xwoba * pa) / SUM(pa) AS lg_xwoba
            FROM player_season GROUP BY season
        )
        SELECT p.player_id, p.player_name, p.season, p.pa, p.woba, p.xwoba, p.primary_team,
               l.lg_woba, p.woba - l.lg_woba AS cwoba, p.xwoba - l.lg_xwoba AS cxwoba
        FROM player_season AS p JOIN league AS l USING (season)
    """).df()


def birthdates(ids) -> pd.DataFrame:
    path = RAW / "birthdates.csv"
    have = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["player_id", "birth_date"])
    need = sorted(set(int(i) for i in ids) - set(have["player_id"].astype(int)))
    rows = []
    for i in range(0, len(need), 100):
        chunk = ",".join(str(x) for x in need[i:i + 100])
        r = requests.get(f"https://statsapi.mlb.com/api/v1/people?personIds={chunk}", timeout=30)
        r.raise_for_status()
        rows += [{"player_id": p["id"], "birth_date": p.get("birthDate")} for p in r.json()["people"]]
    if rows:
        have = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
        RAW.mkdir(parents=True, exist_ok=True)
        have.to_csv(path, index=False)
    have["birth_date"] = pd.to_datetime(have["birth_date"])
    return have


def build_examples(seasons: pd.DataFrame, ages: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, base season T): 3-season history up to T, plus next season's result."""
    s = seasons.set_index(["player_id", "season"])
    rows = []
    for (pid, t), row in s.iterrows():
        rec = {"player_id": pid, "player_name": row.player_name, "season": t, "pa": row.pa,
               "cxwoba": row.cxwoba, "team": row.primary_team}
        num_x = num_g = den = 0.0
        for k, w in enumerate(WEIGHTS):
            if (pid, t - k) in s.index:
                h = s.loc[(pid, t - k)]
                num_x += w * h.pa * h.cxwoba
                num_g += w * h.pa * (h.cwoba - h.cxwoba)
                den += w * h.pa
        rec.update(wpa=den, wx=num_x / den, wgap=num_g / den)
        if (pid, t + 1) in s.index:
            n = s.loc[(pid, t + 1)]
            rec.update(target=n.cwoba, pa_2=n.pa)
        rows.append(rec)
    ex = pd.DataFrame(rows).merge(ages, on="player_id", how="left")
    # age next season, as of June 30 (the usual baseball convention)
    ref = pd.to_datetime((ex["season"] + 1).astype(str) + "-06-30")
    ex["age_next"] = (ref - ex["birth_date"]).dt.days / 365.25
    ex["age_young"] = np.minimum(ex["age_next"] - PEAK_AGE, 0)
    ex["age_old"] = np.maximum(ex["age_next"] - PEAK_AGE, 0)
    return ex


def design(df, model, c_x=None, c_g=None):
    cols = [np.ones(len(df))]
    if model == "A":
        cols.append(df["cxwoba"])
    else:
        cols.append(df["wx"] * df["wpa"] / (df["wpa"] + c_x))
        if model in ("C", "D"):
            cols += [df["age_young"], df["age_old"]]
        if model == "D":
            cols.append(df["wgap"] * df["wpa"] / (df["wpa"] + c_g))
    return np.column_stack(cols)


def wls(X, y, w):
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    return beta


def fit(train, model):
    """Returns (beta, c_x, c_g). Shrinkage constants chosen by grid search on training data only."""
    y, w = train["target"].to_numpy(float), train["pa_2"].to_numpy(float)
    sse = lambda X: ((w * (y - X @ wls(X, y, w)) ** 2)).sum()
    if model == "A":
        return wls(design(train, "A"), y, w), None, None
    c_x = min(C_GRID, key=lambda c: sse(design(train, "C" if model != "B" else "B", c, 1000)))
    c_g = None
    if model == "D":
        c_g = min(C_GRID, key=lambda c: sse(design(train, "D", c_x, c)))
    return wls(design(train, model, c_x, c_g), y, w), c_x, c_g


def predict(df, model, params):
    beta, c_x, c_g = params
    return design(df, model, c_x, c_g) @ beta


def rmse(err, w):
    return float(np.sqrt((w * err ** 2).sum() / w.sum()) * 1000)


def main() -> None:
    os.chdir(ROOT)
    con = duckdb.connect(str(ROOT / "data" / "statcast.duckdb"), read_only=True)
    seasons = load_seasons(con)
    ages = birthdates(seasons["player_id"].unique())
    ex = build_examples(seasons, ages)
    pairs = ex.dropna(subset=["target", "age_next"]).reset_index(drop=True)
    print(f"{len(pairs)} season pairs, {pairs.player_id.nunique()} hitters; "
          f"{ex['age_next'].isna().sum()} rows missing a birthdate")

    models = ["A", "B", "C", "D"]
    names = {"A": "This season's xwOBA (step 4 rule)", "B": "3-season weighted xwOBA",
             "C": "3-season xwOBA + age", "D": "3-season xwOBA + age + 3-season gap"}
    preds = {m: np.full(len(pairs), np.nan) for m in models}
    test_mask = np.zeros(len(pairs), bool)
    for tgt in TEST_TARGETS:
        train = pairs[pairs["season"] + 1 < tgt]
        test = pairs["season"] + 1 == tgt
        test_mask |= test.to_numpy()
        for m in models:
            preds[m][test.to_numpy()] = predict(pairs[test], m, fit(train, m))

    t = pairs[test_mask]
    w, y = t["pa_2"].to_numpy(float), t["target"].to_numpy(float)
    errs = {m: preds[m][test_mask] - y for m in models}
    rng = np.random.default_rng(SEED)
    players = t["player_id"].to_numpy()
    uniq = np.unique(players)
    idx_by_player = {p: np.flatnonzero(players == p) for p in uniq}
    boot = {m: [] for m in models}
    for _ in range(BOOT):
        idx = np.concatenate([idx_by_player[p] for p in rng.choice(uniq, len(uniq))])
        base = rmse(errs["A"][idx], w[idx])
        for m in models:
            boot[m].append(rmse(errs[m][idx], w[idx]) - base)
    out = []
    for m in models:
        lo, hi = np.percentile(boot[m], [2.5, 97.5])
        out.append({"forecast": names[m], "rmse_points": rmse(errs[m], w),
                    "vs_A": rmse(errs[m], w) - rmse(errs["A"], w), "ci_low": lo, "ci_high": hi,
                    "test_pairs": len(t)})
    # D vs C directly: does the gap help once 3 seasons and age are in?
    dc = [bd - bc for bd, bc in zip(boot["D"], boot["C"])]
    res = pd.DataFrame(out)
    res.to_csv(RESULTS / "step6_forecast.csv", index=False)
    pd.set_option("display.width", 200)
    print(res.to_string(index=False, float_format="{:.2f}".format))
    print(f"D vs C (gap added to the 3-season + age model): {np.mean(dc):+.2f} "
          f"(95% CI {np.percentile(dc, 2.5):+.2f} to {np.percentile(dc, 97.5):+.2f})")

    # final model on regulars, then the 2027 board
    reg = pairs[(pairs["pa"] >= MIN_PA_FIT) & (pairs["pa_2"] >= MIN_PA_FIT)]
    best = "C"
    beta, c_x, c_g = fit(reg, best)
    pd.DataFrame([{"model": names[best], "intercept": beta[0], "slope_shrunk_wx": beta[1],
                   "age_young_per_year": beta[2], "age_old_per_year": beta[3], "shrink_c_pa": c_x,
                   "fit_pairs": len(reg)}]).to_csv(RESULTS / "step6_model.csv", index=False)
    print(f"final model (regulars, {len(reg)} pairs): intercept {beta[0]*1000:+.1f} pts, "
          f"slope {beta[1]:.2f}, shrink c={c_x}, age before 27 {beta[2]*1000:+.1f} pts/yr, "
          f"after 27 {beta[3]*1000:+.1f} pts/yr")

    cur = ex[(ex["season"] == 2026) & (ex["pa"] >= MIN_PA_BOARD)].copy()
    lg = seasons.loc[seasons.season == 2026, "lg_woba"].iloc[0]
    cur["proj_3yr_age"] = lg + predict(cur, best, (beta, c_x, c_g))
    old = pd.read_csv(RESULTS / "step5_board.csv")
    # step 5's board has no player_id; names are unique among 400+ PA hitters
    cur = cur.merge(old[["player_name", "proj_2027"]].rename(columns={"proj_2027": "proj_step5"}),
                    on="player_name", how="left")
    cur = cur.merge(seasons[seasons.season == 2026][["player_id", "woba", "xwoba"]], on="player_id")
    cur["change_vs_step5"] = (cur["proj_3yr_age"] - cur["proj_step5"]) * 1000
    board = cur[["player_name", "team", "age_next", "pa", "woba", "xwoba", "proj_step5", "proj_3yr_age",
                 "change_vs_step5"]].sort_values("proj_3yr_age", ascending=False)
    board.to_csv(RESULTS / "step6_board.csv", index=False, float_format="%.4f")
    print(f"board: {len(board)} hitters -> results/step6_board.csv")


if __name__ == "__main__":
    main()
