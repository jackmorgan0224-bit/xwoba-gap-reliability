"""Step 5: 2027 projections for 2026 hitters, and where 2026 results misstate them.

Uses step 4's result: next-season wOBA is projected from xwOBA alone (the gap adds nothing),
regressed toward the league average. The regression is fitted on every 2021-26 season pair
of regulars (300+ PA both seasons) and applied to 2026 hitters with 400+ PA.
Writes results/step5_board.csv and results/step5_model.csv.
"""

import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import step3_traits as s3

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MIN_PA_FIT = 300
MIN_PA_BOARD = 400


def main() -> None:
    os.chdir(ROOT)
    con = duckdb.connect(str(ROOT / "data" / "statcast.duckdb"))
    con.execute((ROOT / "sql" / "05_step3_traits.sql").read_text(encoding="utf-8"))
    seasons = con.sql("""
        WITH league AS (
            SELECT season, SUM(woba * pa) / SUM(pa) AS lg_woba, SUM(xwoba * pa) / SUM(pa) AS lg_xwoba
            FROM player_season GROUP BY season
        )
        SELECT p.player_id, p.player_name, p.season, p.pa, p.woba, p.xwoba, p.woba_gap,
               p.primary_team, p.n_teams, l.lg_woba, l.lg_xwoba,
               p.woba - l.lg_woba AS cwoba, p.xwoba - l.lg_xwoba AS cxwoba,
               t.pulled_hard_fb_share, p.sprint_speed
        FROM player_season AS p
        JOIN league AS l USING (season)
        LEFT JOIN player_traits AS t USING (player_id, season)
    """).df()

    nxt = seasons[["player_id", "season", "cwoba", "pa"]].rename(columns={"cwoba": "cwoba_2", "pa": "pa_2"})
    nxt["season"] -= 1
    pairs = seasons.merge(nxt, on=["player_id", "season"])
    pairs = pairs[(pairs["pa"] >= MIN_PA_FIT) & (pairs["pa_2"] >= MIN_PA_FIT)]
    X = np.column_stack([np.ones(len(pairs)), pairs["cxwoba"]])
    w = pairs["pa_2"].to_numpy(float)
    a, b = s3.wls(X, pairs["cwoba_2"].to_numpy(), w)
    resid = pairs["cwoba_2"] - X @ np.array([a, b])
    rmse = float(np.sqrt(np.average(resid ** 2, weights=w)))
    pd.DataFrame([{"intercept": a, "xwoba_slope": b, "pairs": len(pairs), "rmse": rmse}]).to_csv(
        RESULTS / "step5_model.csv", index=False, float_format="%.4f")

    board = seasons[(seasons["season"] == 2026) & (seasons["pa"] >= MIN_PA_BOARD)].copy()
    # 2027 run environment is unknown; project relative to the 2026 league average
    board["proj_2027"] = board["lg_woba"] + a + b * board["cxwoba"]
    board["woba_minus_proj"] = board["woba"] - board["proj_2027"]
    board = board.sort_values("woba_minus_proj", ascending=False)
    cols = ["player_name", "primary_team", "n_teams", "pa", "woba", "xwoba", "woba_gap",
            "proj_2027", "woba_minus_proj", "pulled_hard_fb_share", "sprint_speed"]
    board[cols].to_csv(RESULTS / "step5_board.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 220, "display.max_columns", 20)
    print(f"model: proj = league + {a:.4f} + {b:.3f} x (xwOBA - league xwOBA); "
          f"{len(pairs)} pairs; RMSE {rmse * 1000:.1f} points")
    print(f"2026 league wOBA {board['lg_woba'].iloc[0]:.4f}, xwOBA {board['lg_xwoba'].iloc[0]:.4f}; "
          f"{len(board)} hitters on the board")
    print("\nResults most above projection\n", board[cols].head(12).round(3).to_string(index=False))
    print("\nResults most below projection\n", board[cols].tail(12).round(3).to_string(index=False))
    print("\nMets\n", board[board["primary_team"] == "NYM"][cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
