"""Plain-English framing and the animated "replay" of past forecasts against reality.

The numbers in REPORT.md answer precise questions; this module turns them into a few sentences
anyone can read, and into an animation that shows, one forecast at a time, what the model said
would happen and what actually happened.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import domain_table, scale_table
from .report import GRID, SERIES_COLORS, SURFACE, TEXT, TEXT_SECONDARY

log = logging.getLogger(__name__)

DOMAIN_PLAIN = {"news": "world news", "markets": "markets", "tech": "technology"}
STEP_UNIT = {"news": "days", "markets": "trading days", "tech": "days"}
HEADLINE_SERIES = ("sp500", "gold", "news_composite", "wiki_ai")


def headlines(
    summary: pd.DataFrame,
    model: str,
    results: pd.DataFrame | None = None,
    by_step: pd.DataFrame | None = None,
) -> list[str]:
    """A handful of sentences that say what the results mean, in everyday words."""
    lines = []
    domains = domain_table(summary)
    mine = domains[domains["model"] == model].set_index("domain")
    if not mine.empty:
        wins = [d for d in mine.index if mine.loc[d, "median_skill"] > 0.02]
        verdicts = []
        for d in ("news", "markets", "tech"):
            if d in mine.index:
                skill = mine.loc[d, "median_skill"]
                if skill > 0.02:
                    verdicts.append(f"{DOMAIN_PLAIN[d]} ({skill:.0%} less error)")
        if wins:
            lines.append(
                f"{model} beat the simple guess \"tomorrow looks like today\" in {len(wins)} of "
                f"{len(mine)} areas: {', '.join(verdicts)}."
            )
        else:
            lines.append(f"{model} did not beat the simple guess \"tomorrow looks like today\" in any area.")

    scales = scale_table(summary)
    scales = scales[scales["model"] == model].groupby("scale")["median_skill"].median()
    if {"aggregate", "individual"} <= set(scales.index):
        agg, ind = scales["aggregate"], scales["individual"]
        if agg > ind:
            lines.append(
                f"Seldon was right here: big aggregates such as indices and averages were easier to predict "
                f"than single stocks or topics ({agg:.0%} vs {ind:.0%} skill)."
            )
        else:
            lines.append(
                f"Seldon's law did not hold here: aggregates were not easier to predict than individual "
                f"series ({agg:.0%} vs {ind:.0%} skill)."
            )

    if by_step is not None and not by_step.empty:
        for d in ("news", "markets", "tech"):
            part = by_step[(by_step["model"] == model) & (by_step["domain"] == d)].sort_values("step")
            if part.empty:
                continue
            smooth = part["skill"].rolling(3, min_periods=1, center=True).median().to_numpy()
            positive = np.flatnonzero(smooth > 0)
            if len(positive):
                lines.append(
                    f"In {DOMAIN_PLAIN[d]}, its edge lasts up to about {int(part['step'].iloc[positive[-1]])} "
                    f"{STEP_UNIT[d]} ahead."
                )
            else:
                lines.append(f"In {DOMAIN_PLAIN[d]}, it had no edge at any distance ahead.")

    if results is not None and "p_up" in results.columns:
        rows = results[(results["model"] == model)].dropna(subset=["p_up", "went_up"])
        confident = rows[rows["p_up"] >= 0.7]
        if len(confident) >= 5:
            lines.append(
                f"When it gave 70% or more odds of a rise, the rise really happened "
                f"{confident['went_up'].mean():.0%} of the time ({len(confident)} forecasts)."
            )
    return lines


def pick_headline_series(paths: pd.DataFrame) -> str | None:
    if paths.empty:
        return None
    available = set(paths["series_id"])
    for series_id in HEADLINE_SERIES:
        if series_id in available:
            return series_id
    return sorted(available)[0]


def replay_gif(
    series: pd.Series,
    paths: pd.DataFrame,
    title: str,
    out_path: Path,
    fps: float = 1.2,
) -> Path | None:
    """Animated GIF: for each past forecast, show what the model expected (orange fan) and then
    what really happened (dark dots). Built with matplotlib's FuncAnimation and Pillow."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation, PillowWriter
    except ImportError:
        return None
    origins = sorted(paths["origin"].unique())
    if not origins:
        return None
    first = pd.Timestamp(origins[0])
    span = pd.Timestamp(paths["date"].max()) - first
    window = series[(series.index >= first - span * 0.6) & (series.index <= pd.Timestamp(paths["date"].max()))]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=110)

    def draw(i: int):
        ax.clear()
        ax.set_facecolor(SURFACE)
        fig.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)
        ax.grid(color=GRID, linewidth=0.8)
        origin = pd.Timestamp(origins[i])
        known = window[window.index <= origin]
        ax.plot(known.index, known.values, color=SERIES_COLORS[0], linewidth=1.8, label="What it could see")
        for j in range(i):  # earlier forecasts stay as faint ghosts
            ghost = paths[paths["origin"] == origins[j]]
            ax.plot(pd.to_datetime(ghost["date"]), ghost["q50"], color=SERIES_COLORS[1], alpha=0.18, linewidth=1)
        now = paths[paths["origin"] == origins[i]].sort_values("step")
        dates = pd.to_datetime(now["date"])
        ax.fill_between(dates, now["q10"], now["q90"], color=SERIES_COLORS[1], alpha=0.2, linewidth=0, label="Its 80% range")
        ax.plot(dates, now["q50"], color=SERIES_COLORS[1], linewidth=2, label="Its best guess")
        ax.scatter(dates, now["actual"], s=10, color=TEXT, zorder=3, label="What really happened")
        inside = float(np.mean((now["actual"] >= now["q10"]) & (now["actual"] <= now["q90"])))
        ax.set_xlim(window.index[0], window.index[-1])
        ax.set_ylim(window.min() - 0.05 * np.ptp(window), window.max() + 0.05 * np.ptp(window))
        ax.set_title(
            f"{title}: forecast made {origin.date()} ({inside:.0%} of reality inside its range)",
            color=TEXT, loc="left", fontsize=10,
        )
        ax.legend(frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY, loc="upper center",
                  bbox_to_anchor=(0.5, -0.1), ncol=4)
        fig.tight_layout()

    animation = FuncAnimation(fig, draw, frames=len(origins), interval=1000 / fps)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    animation.save(out_path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return out_path
