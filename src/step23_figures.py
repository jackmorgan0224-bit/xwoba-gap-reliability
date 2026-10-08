"""Step 2 and 3 figures, light and dark versions. Reads results/step2_*.csv and step3_*.csv."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from step1_figures import FIGURES, RESULTS, THEMES, style_axes, title


def trust_curve(t: dict, mode: str) -> None:
    curve = pd.read_csv(RESULTS / "step2_split_half.csv")
    summary = pd.read_csv(RESULTS / "step2_summary.csv").set_index("quantity")
    c, c_lo, c_hi = summary.loc["C, within-season (BIP for 50% reliability)", ["value", "lo", "hi"]]
    c_next = summary.loc["C, next-season carryover (all pairs)", "value"]
    n = np.linspace(1, 600, 300)

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=t["surface"])
    fig.subplots_adjust(left=0.1, right=0.83, top=0.76, bottom=0.13)
    style_axes(ax, t)
    ax.fill_between(n, n / (n + c_hi), n / (n + c_lo), color=t["history"], alpha=0.14, linewidth=0)
    ax.plot(n, n / (n + c), color=t["history"], linewidth=2)
    ax.errorbar(curve["bip_per_half"], curve["reliability"],
                yerr=[curve["reliability"] - curve["split_lo"], curve["split_hi"] - curve["reliability"]],
                fmt="o", color=t["history"], markersize=8, markeredgecolor=t["surface"],
                markeredgewidth=2, elinewidth=1.2, capsize=0, zorder=3)
    ax.plot(n, n / (n + c_next), color=t["recent"], linewidth=2, linestyle=(0, (5, 3)))
    ax.annotate("This season", (600, 600 / (600 + c)), xytext=(8, 0), textcoords="offset points",
                va="center", color=t["ink2"], fontsize=10.5)
    ax.annotate("Next season", (600, 600 / (600 + c_next)), xytext=(8, -2), textcoords="offset points",
                va="center", color=t["ink2"], fontsize=10.5)
    ax.axvline(400, color=t["muted"], linewidth=1, linestyle=(0, (2, 3)))
    ax.text(405, 0.47, "≈ full season\n(400 BIP, ~590 PA)", color=t["muted"], fontsize=9.5, va="top")
    ax.set_xlim(0, 600)
    ax.set_ylim(0, 0.5)
    ax.set_xlabel("Balls in play observed", color=t["ink2"], fontsize=10.5)
    ax.set_ylabel("Share of the gap to believe", color=t["ink2"], fontsize=10.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    title(fig, t, "Even a full season's gap is mostly noise",
          "Dots: split-half reliability at n balls in play (range across 200 random splits). Lines: fitted\n"
          f"n / (n + C), C = {c:,.0f} this season (band: 95% CI) and {c_next:,.0f} for next season.")
    fig.savefig(FIGURES / f"step2_trust_{mode}.png", dpi=200, facecolor=t["surface"])
    plt.close(fig)


def pulled_fly_balls(t: dict, mode: str) -> None:
    ev = pd.read_csv(RESULTS / "step3_fly_ball_ev.csv")
    order = ["under 90", "90-95", "95-100", "100-105", "105+"]
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=t["surface"])
    fig.subplots_adjust(left=0.11, right=0.97, top=0.76, bottom=0.13)
    style_axes(ax, t)
    width = 0.36
    for offset, (direction, key) in zip((-width / 2 - 0.01, width / 2 + 0.01),
                                        (("pulled", "recent"), ("not pulled", "history"))):
        d = ev[ev["direction"] == direction].set_index("exit_velocity").loc[order]
        bars = ax.bar(x + offset, d["mean_resid_points"], width=width, color=t[key],
                      label="Pulled" if direction == "pulled" else "Center or opposite field")
        for xi, v in zip(x + offset, d["mean_resid_points"]):
            ax.text(xi, v + (12 if v >= 0 else -12), f"{v:+.0f}", ha="center",
                    va="bottom" if v >= 0 else "top", color=t["ink2"], fontsize=9)
    ax.axhline(0, color=t["axis"], linewidth=1)
    ax.set_xticks(x, [f"{o} mph" for o in order])
    ax.set_ylabel("Actual minus expected wOBA per fly ball (points)", color=t["ink2"], fontsize=10.5)
    ax.set_ylim(-340, 600)
    ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=t["ink2"])
    title(fig, t, "xwOBA can't see direction, and hard fly balls show it",
          "Average result vs. Statcast expectation for fly balls, 2021–26, by exit velocity.\n"
          "1 point = .001 of wOBA; a home run is worth about 2,000.")
    fig.savefig(FIGURES / f"step3_pulled_{mode}.png", dpi=200, facecolor=t["surface"])
    plt.close(fig)


def park_effects(t: dict, mode: str) -> None:
    parks = pd.read_csv(RESULTS / "step3_parks.csv").sort_values("park_effect_points")
    fig, ax = plt.subplots(figsize=(8, 9), facecolor=t["surface"])
    fig.subplots_adjust(left=0.36, right=0.95, top=0.88, bottom=0.07)
    style_axes(ax, t)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    y = np.arange(len(parks))
    colors = [t["recent"] if p == "Citi Field" else t["history"] for p in parks["park"]]
    ax.barh(y, parks["park_effect_points"], height=0.68, color=colors)
    labels = [f"{p}  ({s} season{'s' if s > 1 else ''})" if s < 6 else p
              for p, s in zip(parks["park"], parks["seasons"])]
    ax.set_yticks(y, labels, fontsize=9.5, color=t["ink2"])
    ax.axvline(0, color=t["axis"], linewidth=1)
    for yi, v in zip(y, parks["park_effect_points"]):
        ax.text(v + (1 if v >= 0 else -1), yi, f"{v:+.0f}", va="center",
                ha="left" if v >= 0 else "right", color=t["ink2"], fontsize=8.5)
    ax.set_xlabel("Actual minus expected wOBA per ball in play, all hitters (points)",
                  color=t["ink2"], fontsize=10)
    ax.set_xlim(-25, 48)
    fig.text(0.04, 0.965, "Where the gap comes from: parks", color=t["ink"], fontsize=14,
             fontweight="bold", va="top")
    fig.text(0.04, 0.935, "2021–26, home and visiting hitters. Citi Field highlighted.",
             color=t["ink2"], fontsize=10.5, va="top")
    fig.savefig(FIGURES / f"step3_parks_{mode}.png", dpi=200, facecolor=t["surface"])
    plt.close(fig)


def main() -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    for mode, t in THEMES.items():
        trust_curve(t, mode)
        pulled_fly_balls(t, mode)
        park_effects(t, mode)
    print(f"Wrote figures to {FIGURES.relative_to(Path(__file__).resolve().parents[1])}")


if __name__ == "__main__":
    main()
