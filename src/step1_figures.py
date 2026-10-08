"""Step 1 figures, rendered in light and dark versions for GitHub's theme-aware README.

Reads results/step1_*.csv (run src/step1_persistence.py first) and writes PNGs to
docs/figures/.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "docs" / "figures"

# Reference palette (validated for both surfaces with the dataviz validator)
THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
              "grid": "#e1e0d9", "axis": "#c3c2b7", "history": "#2a78d6", "recent": "#eb6834"},
    "dark": {"surface": "#1a1a19", "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
             "grid": "#2c2c2a", "axis": "#383835", "history": "#3987e5", "recent": "#d95926"},
}
ERA_LABEL = {"history": "2015–19", "recent": "2021–26"}


def style_axes(ax, t: dict) -> None:
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.tick_params(colors=t["muted"], labelsize=10, length=0)
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def title(fig, t: dict, main: str, sub: str) -> None:
    fig.text(0.06, 0.95, main, color=t["ink"], fontsize=14, fontweight="bold", va="top")
    fig.text(0.06, 0.885, sub, color=t["ink2"], fontsize=10.5, va="top")


def persistence_by_threshold(t: dict, mode: str) -> None:
    ladder = pd.read_csv(RESULTS / "step1_thresholds.csv")
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=t["surface"])
    fig.subplots_adjust(left=0.1, right=0.86, top=0.76, bottom=0.14)
    style_axes(ax, t)

    for era in ("history", "recent"):
        d = ladder[ladder["era"] == era]
        x = d["min_pa_both_seasons"]
        ax.fill_between(x, d["r_weighted_lo"], d["r_weighted_hi"], color=t[era], alpha=0.14, linewidth=0)
        ax.plot(x, d["r_weighted"], color=t[era], linewidth=2, marker="o", markersize=8,
                markeredgecolor=t["surface"], markeredgewidth=2, label=ERA_LABEL[era], zorder=3)
        last = d.iloc[-1]
        ax.annotate(ERA_LABEL[era], (last["min_pa_both_seasons"], last["r_weighted"]),
                    xytext=(10, 0), textcoords="offset points", va="center",
                    color=t["ink2"], fontsize=10.5)

    ax.axhline(0.43, color=t["muted"], linewidth=1, linestyle=(0, (4, 3)))
    ax.text(100, 0.445, "Melchior (2019): r = .43", color=t["muted"], fontsize=9.5)

    ax.set_xticks([100, 200, 300, 400, 500], ["100+", "200+", "300+", "400+", "500+"])
    ax.set_xlabel("Minimum plate appearances in both seasons", color=t["ink2"], fontsize=10.5)
    ax.set_ylabel("Year-over-year correlation of the gap", color=t["ink2"], fontsize=10.5)
    ax.set_ylim(0, 0.6)
    ax.set_xlim(80, 520)
    legend = ax.legend(loc="upper left", frameon=False, fontsize=10, labelcolor=t["ink2"])
    for handle in legend.legend_handles:
        handle.set_markeredgecolor(t["surface"])
    title(fig, t, "The wOBA–xwOBA gap repeats less than it used to",
          "PA-weighted correlation of a hitter's gap with his next-season gap. Bands: 95% intervals\n"
          "(bootstrap by player). Both eras use today's Savant data.")
    fig.savefig(FIGURES / f"step1_persistence_{mode}.png", dpi=200, facecolor=t["surface"])
    plt.close(fig)


def speed_link_by_season(t: dict, mode: str) -> None:
    trend = pd.read_csv(RESULTS / "step1_speed_by_season.csv")
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=t["surface"])
    fig.subplots_adjust(left=0.1, right=0.97, top=0.74, bottom=0.12)
    style_axes(ax, t)

    for era, seasons in (("history", range(2015, 2020)), ("recent", range(2021, 2027))):
        d = trend[trend["season"].isin(seasons)]
        ax.bar(d["season"], d["r_gap_speed"], width=0.7, color=t[era], label=ERA_LABEL[era])
        for season, r in zip(d["season"], d["r_gap_speed"]):
            ax.text(season, r + 0.008, f"{r:.2f}".replace("0.", "."), ha="center",
                    color=t["ink2"], fontsize=9)
    ax.text(2020, 0.012, "no\n2020", ha="center", color=t["muted"], fontsize=9)

    ax.set_xticks(list(range(2015, 2027)), [str(s) if s != 2020 else "" for s in range(2015, 2027)])
    ax.set_ylabel("Correlation: gap vs. sprint speed", color=t["ink2"], fontsize=10.5)
    ax.set_ylim(0, 0.4)
    ax.legend(loc="upper right", frameon=False, fontsize=10, labelcolor=t["ink2"])
    title(fig, t, "Speed explains less of the gap than it used to",
          "Correlation between a hitter's wOBA–xwOBA gap and his sprint speed, hitters with 300+ PA.")
    fig.savefig(FIGURES / f"step1_speed_{mode}.png", dpi=200, facecolor=t["surface"])
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    for mode, t in THEMES.items():
        persistence_by_threshold(t, mode)
        speed_link_by_season(t, mode)
    print(f"Wrote figures to {FIGURES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
