"""Step 3: which hitter traits explain the part of the gap that repeats?

Requires the step 2 tables (statcast_pa, woba_weights): run src/step2_reliability.py first.

  A. Ball level: average residual (actual minus expected wOBA on contact) by spray
     direction, batted-ball type, and exit velocity.
  B. Parks: each park's effect on the gap, and how stable it is across seasons.
  C. Same season: how much of a hitter's gap do his traits explain?
  D. Next season: do traits forecast next season's gap better than step 2's shrunken gap
     alone? Rolling-origin test, fitting only on pairs that end before the test season.
Writes results/step3_*.csv.
"""

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SEED = 20261008
BOOT = 2000
TRAITS = ["pulled_hard_fb_share", "sprint_speed", "park_exposure", "is_lefty", "gb_pct"]
TRAIT_LABELS = {
    "pulled_hard_fb_share": "Pulled share of 95-105 mph fly balls",
    "sprint_speed": "Sprint speed",
    "park_exposure": "Park effect where his balls in play happened",
    "is_lefty": "Bats left-handed",
    "gb_pct": "Ground-ball rate",
}


def wls(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    return beta


def weighted_r2(X, y, w, beta) -> float:
    resid = y - X @ beta
    ybar = np.average(y, weights=w)
    return 1 - np.average(resid ** 2, weights=w) / np.average((y - ybar) ** 2, weights=w)


def load_player_table(con) -> pd.DataFrame:
    con.execute((ROOT / "sql" / "05_step3_traits.sql").read_text(encoding="utf-8"))
    return con.sql("""
        WITH means AS (
            SELECT season, SUM(woba_gap * pa) / SUM(pa) AS mean_gap FROM player_season GROUP BY season
        )
        SELECT p.player_id, p.player_name, p.season, p.pa, p.woba_gap - m.mean_gap AS cgap,
               p.sprint_speed, p.gb_pct / 100.0 AS gb_pct, (p.bat_side = 'L')::INTEGER AS is_lefty,
               p.bat_speed, t.bip, t.pulled_air_rate, t.pulled_hard_fb_share, t.park_exposure,
               f.park_exposure_known, f.next_park_exposure
        FROM player_season AS p
        JOIN means AS m USING (season)
        JOIN player_traits AS t USING (player_id, season)
        LEFT JOIN player_park_forecast AS f USING (player_id, season)
    """).df()


# ---------- A. ball level ----------

def ball_level(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    by_type = con.sql("""
        SELECT
            CASE WHEN bb_type = 'ground_ball' THEN 'ground ball' ELSE bb_type END AS batted_ball,
            CASE WHEN pulled THEN 'pulled'
                 WHEN ABS(spray_angle) <= 15 THEN 'center'
                 ELSE 'opposite' END                                AS direction,
            COUNT(*)                                                AS balls,
            AVG(resid) * 1000                                       AS mean_resid_points
        FROM bip
        WHERE bb_type IN ('ground_ball', 'line_drive', 'fly_ball')
        GROUP BY ALL
        ORDER BY batted_ball, direction
    """).df()
    fly_ev = con.sql("""
        SELECT
            CASE WHEN pulled THEN 'pulled' ELSE 'not pulled' END    AS direction,
            CASE WHEN launch_speed < 90 THEN 'under 90'
                 WHEN launch_speed < 95 THEN '90-95'
                 WHEN launch_speed < 100 THEN '95-100'
                 WHEN launch_speed < 105 THEN '100-105'
                 ELSE '105+' END                                    AS exit_velocity,
            COUNT(*)                                                AS balls,
            AVG(resid) * 1000                                       AS mean_resid_points
        FROM bip
        WHERE bb_type = 'fly_ball' AND launch_speed IS NOT NULL
        GROUP BY ALL
        ORDER BY direction, MIN(launch_speed)
    """).df()
    return by_type, fly_ev


# ---------- B. parks ----------

def parks(con) -> tuple[pd.DataFrame, float]:
    by_park = con.sql("""
        WITH venue AS (
            SELECT DISTINCT season, team_abbr, venue_id, venue_name FROM stg_team_pa WHERE venue_id IS NOT NULL
        ),
        league AS (SELECT season, AVG(resid) AS league_resid FROM bip GROUP BY season)
        SELECT v.venue_id, ANY_VALUE(v.venue_name ORDER BY b.season DESC) AS park,
               COUNT(DISTINCT b.season) AS seasons, COUNT(*) AS balls,
               AVG(b.resid - l.league_resid) * 1000 AS park_effect_points
        FROM bip AS b
        JOIN venue AS v ON v.season = b.season AND v.team_abbr = b.home_abbr
        JOIN league AS l ON l.season = b.season
        GROUP BY v.venue_id
        ORDER BY park_effect_points DESC
    """).df()
    # Stability: a park's effect in one season vs. its effect in its other seasons
    stability = con.sql("""
        WITH venue AS (
            SELECT DISTINCT season, team_abbr, venue_id FROM stg_team_pa WHERE venue_id IS NOT NULL
        ),
        league AS (SELECT season, AVG(resid) AS league_resid FROM bip GROUP BY season),
        own AS (
            SELECT v.venue_id, b.season, AVG(b.resid - l.league_resid) AS own_effect
            FROM bip AS b
            JOIN venue AS v ON v.season = b.season AND v.team_abbr = b.home_abbr
            JOIN league AS l ON l.season = b.season
            GROUP BY ALL
        )
        SELECT CORR(o.own_effect, p.park_resid_loso)
        FROM own AS o JOIN park_effect AS p USING (venue_id, season)
        WHERE p.park_resid_loso IS NOT NULL
    """).fetchone()[0]
    return by_park, stability


# ---------- C. same season ----------

def same_season(players: pd.DataFrame, rng) -> pd.DataFrame:
    d = players.dropna(subset=TRAITS + ["cgap"]).reset_index(drop=True)
    z = (d[TRAITS] - d[TRAITS].mean()) / d[TRAITS].std()
    X = np.column_stack([np.ones(len(d)), z.to_numpy()])
    y, w = d["cgap"].to_numpy(), d["pa"].to_numpy(float)
    beta = wls(X, y, w)
    r2 = weighted_r2(X, y, w, beta)
    by_player = d.groupby("player_id").indices
    players_ids = np.array(list(by_player))
    boots = []
    for _ in range(BOOT):
        idx = np.concatenate([by_player[p] for p in rng.choice(players_ids, len(players_ids))])
        boots.append(wls(X[idx], y[idx], w[idx]))
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    out = pd.DataFrame({
        "trait": [TRAIT_LABELS[t] for t in TRAITS],
        "points_per_sd": beta[1:] * 1000, "lo": lo[1:] * 1000, "hi": hi[1:] * 1000,
    })
    out.attrs["r2"] = r2
    out.attrs["n"] = len(d)
    return out


# ---------- D. next season ----------

def next_season(players: pd.DataFrame, rng) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Forecast-safe park inputs: park effects estimated only from seasons <= t
    players = players.assign(park_exposure=players["park_exposure_known"])
    nxt = players[["player_id", "season", "cgap", "pa"]].rename(columns={"cgap": "cgap_2", "pa": "pa_2"})
    nxt["season"] -= 1
    pairs = players.merge(nxt, on=["player_id", "season"])
    pairs = pairs.rename(columns={"next_park_exposure": "park_exposure_2"})
    pairs = pairs.dropna(subset=TRAITS + ["cgap_2", "park_exposure_2"]).reset_index(drop=True)

    def design(df, c, mean, sd, model, next_park=False):
        shrunk = (df["bip"] / (df["bip"] + c) * df["cgap"]).to_numpy()
        z = ((df[TRAITS] - mean) / sd)
        if next_park:
            z["park_exposure"] = (df["park_exposure_2"] - mean["park_exposure"]) / sd["park_exposure"]
        cols = [np.ones(len(df))]
        if model in ("shrunk gap", "shrunk gap + traits", "shrunk gap + traits, next park known"):
            cols.append(shrunk)
        if model in ("traits", "shrunk gap + traits", "shrunk gap + traits, next park known"):
            cols.extend(z.to_numpy().T)
        return np.column_stack(cols)

    def fit_c(train):
        g1, g2, n1, w = (train[c].to_numpy(float) for c in ("cgap", "cgap_2", "bip", "pa_2"))
        grid = np.linspace(1, 20000, 4000)
        return grid[int(np.argmin([(w * (g2 - n1 / (n1 + c) * g1) ** 2).sum() for c in grid]))]

    models = ["no trust", "shrunk gap", "traits", "shrunk gap + traits", "shrunk gap + traits, next park known"]
    preds = []
    for t in range(2023, 2026):  # test season pairs (t, t+1); train on pairs ending <= t
        train = pairs[pairs["season"] + 1 <= t]
        test = pairs[pairs["season"] == t].copy()
        mean, sd = train[TRAITS].mean(), train[TRAITS].std()
        c = fit_c(train)
        for m in models:
            if m == "no trust":
                test[f"pred_{m}"] = 0.0
                continue
            next_park = m.endswith("next park known")
            Xtr = design(train, c, mean, sd, m, next_park)
            beta = wls(Xtr, train["cgap_2"].to_numpy(), train["pa_2"].to_numpy(float))
            test[f"pred_{m}"] = design(test, c, mean, sd, m, next_park) @ beta
        preds.append(test)
    tested = pd.concat(preds, ignore_index=True)

    def rmse(df, col):
        return np.sqrt(np.average((df["cgap_2"] - df[col]) ** 2, weights=df["pa_2"]))

    by_player = tested.groupby("player_id").indices
    ids = np.array(list(by_player))
    boot = {m: [] for m in models}
    for _ in range(BOOT):
        sample = tested.iloc[np.concatenate([by_player[p] for p in rng.choice(ids, len(ids))])]
        base = rmse(sample, "pred_shrunk gap")
        for m in models:
            boot[m].append(rmse(sample, f"pred_{m}") - base)
    results = pd.DataFrame([{
        "forecast": m,
        "rmse_points": rmse(tested, f"pred_{m}") * 1000,
        "vs_shrunk_gap_points": (rmse(tested, f"pred_{m}") - rmse(tested, "pred_shrunk gap")) * 1000,
        "lo": np.percentile(boot[m], 2.5) * 1000,
        "hi": np.percentile(boot[m], 97.5) * 1000,
    } for m in models])
    results.attrs["test_pairs"] = len(tested)

    # Full-sample coefficients for the combined model (descriptive)
    mean, sd = pairs[TRAITS].mean(), pairs[TRAITS].std()
    c_all = fit_c(pairs)
    X = design(pairs, c_all, mean, sd, "shrunk gap + traits")
    y, w = pairs["cgap_2"].to_numpy(), pairs["pa_2"].to_numpy(float)
    beta = wls(X, y, w)
    by_player = pairs.groupby("player_id").indices
    ids = np.array(list(by_player))
    boots = []
    for _ in range(BOOT):
        idx = np.concatenate([by_player[p] for p in rng.choice(ids, len(ids))])
        boots.append(wls(X[idx], y[idx], w[idx]))
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    names = ["shrunk gap (per 1.0)"] + [TRAIT_LABELS[t] + " (per SD, points)" for t in TRAITS]
    scale = np.array([1.0] + [1000.0] * len(TRAITS))
    coefs = pd.DataFrame({"term": names, "estimate": beta[1:] * scale, "lo": lo[1:] * scale,
                          "hi": hi[1:] * scale})
    coefs.attrs["c"] = c_all
    coefs.attrs["pairs"] = len(pairs)
    return results, coefs


def trait_trends(players: pd.DataFrame) -> pd.DataFrame:
    """Per-season correlation of the gap with each trait (and bat speed, 2024+)."""
    rows = []
    for season, d in players[players["pa"] >= 300].groupby("season"):
        row = {"season": season, "hitters": len(d)}
        for t in ["pulled_hard_fb_share", "sprint_speed", "park_exposure", "bat_speed"]:
            ok = d[[t, "cgap"]].dropna()
            row[t] = ok[t].corr(ok["cgap"]) if len(ok) > 30 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    os.chdir(ROOT)
    RESULTS.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    con = duckdb.connect(str(ROOT / "data" / "statcast.duckdb"))
    players = load_player_table(con)

    coverage = con.sql("""
        SELECT COUNT(*) AS balls, COUNT(*) FILTER (WHERE pe.park_resid_loso IS NULL) AS no_park_effect
        FROM bip AS b
        LEFT JOIN (SELECT DISTINCT season, team_abbr, venue_id FROM stg_team_pa) AS v
            ON v.season = b.season AND v.team_abbr = b.home_abbr
        LEFT JOIN park_effect AS pe ON pe.venue_id = v.venue_id AND pe.season = b.season
    """).df()
    by_type, fly_ev = ball_level(con)
    by_park, park_stability = parks(con)
    same = same_season(players, rng)
    forecast, coefs = next_season(players, rng)
    trends = trait_trends(players)

    for name, df in [("coverage", coverage), ("ball_level", by_type), ("fly_ball_ev", fly_ev),
                     ("parks", by_park), ("same_season", same), ("forecast_test", forecast),
                     ("next_season_coefficients", coefs), ("trait_trends", trends)]:
        df.to_csv(RESULTS / f"step3_{name}.csv", index=False, float_format="%.4f")
    pd.DataFrame([
        {"quantity": "park effect stability (own season vs other seasons, r)", "value": park_stability},
        {"quantity": "same-season R2 of traits", "value": same.attrs["r2"]},
        {"quantity": "same-season player-seasons", "value": same.attrs["n"]},
        {"quantity": "next-season test pairs", "value": forecast.attrs["test_pairs"]},
        {"quantity": "next-season pairs (full sample)", "value": coefs.attrs["pairs"]},
        {"quantity": "carryover C (full sample, BIP)", "value": coefs.attrs["c"]},
    ]).to_csv(RESULTS / "step3_summary.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 200, "display.max_columns", 20)
    for title, df in [("Coverage", coverage), ("Ball level", by_type), ("Fly balls by EV", fly_ev),
                      ("Parks", by_park), ("Same season", same), ("Forecast test", forecast),
                      ("Coefficients", coefs), ("Trends", trends)]:
        print(f"\n{title}\n{df.round(3).to_string(index=False)}")
    print(f"\nPark stability r = {park_stability:.3f}; same-season R2 = {same.attrs['r2']:.3f}")


if __name__ == "__main__":
    main()
