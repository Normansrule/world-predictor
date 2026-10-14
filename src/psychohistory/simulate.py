"""Seldon's law in a toy world: an agent-based simulation of why crowds are predictable.

Each simulated person has a mood that is part shared "tide" (the slow forces acting on everyone)
and mostly personal noise. One person is close to unpredictable; the average of a large crowd
follows the tide almost exactly. This is the intuition behind psychohistory, and behind test 2
of the real backtest (aggregates vs individuals). Inspired by agent-based modelling frameworks
such as Mesa (https://github.com/projectmesa/mesa), but written in plain NumPy.

    psychohistory simulate        # writes results/plots/seldon_crowd.gif and prints the table
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .story import save_gif
from .report import GRID, SERIES_COLORS, SURFACE, TEXT, TEXT_SECONDARY

CROWD_SIZES = (1, 3, 10, 30, 100, 300, 1000, 10000)


def _ar1(rng, shape, phi: float, sd: float) -> np.ndarray:
    shocks = rng.normal(0, sd, shape)
    out = np.empty(shape)
    out[0] = shocks[0] / np.sqrt(1 - phi**2)
    for t in range(1, shape[0]):
        out[t] = phi * out[t - 1] + shocks[t]
    return out


def simulate_crowd(n_agents: int = 10000, steps: int = 240, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return (tide, people): the shared signal with shape (steps,) and each agent's mood with
    shape (steps, n_agents). Personal noise is about three times stronger than the tide."""
    rng = np.random.default_rng(seed)
    t = np.arange(steps)
    tide = 1.2 * np.sin(2 * np.pi * t / 120) + _ar1(rng, (steps,), 0.97, 0.12)
    noise = _ar1(rng, (steps, n_agents), 0.8, 2.0)
    return tide, tide[:, None] + noise


def crowd_predictability(tide: np.ndarray, people: np.ndarray, sizes=CROWD_SIZES) -> pd.DataFrame:
    """For each crowd size: the share of the crowd average's movement explained by the shared tide
    (squared correlation). The tide is the part a model could learn; the rest is noise."""
    rows = []
    for n in sizes:
        if n > people.shape[1]:
            continue
        average = people[:, :n].mean(axis=1)
        rows.append({"crowd_size": n, "predictable_share": float(np.corrcoef(average, tide)[0, 1] ** 2)})
    return pd.DataFrame(rows)


def crowd_gif(out_path: Path, seed: int = 0, fps: float = 1.0) -> Path | None:
    """Animated GIF: the crowd grows frame by frame and its average locks onto the tide."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image  # noqa: F401  (needed by save_gif)
    except ImportError:
        return None
    tide, people = simulate_crowd(seed=seed)
    table = crowd_predictability(tide, people)
    sizes = table["crowd_size"].tolist()
    t = np.arange(len(tide))
    span = np.abs(people[:, :12]).max() * 1.05
    lo, hi = -span, span

    fig, (left, right) = plt.subplots(1, 2, figsize=(9, 3.6), dpi=110, gridspec_kw={"width_ratios": [1.7, 1]})

    def style(ax):
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)
        ax.grid(color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)

    def draw(i: int):
        n = sizes[i]
        fig.set_facecolor(SURFACE)
        for ax in (left, right):
            ax.clear()
            style(ax)
        for j in range(min(n, 12)):  # a few individuals, faint
            left.plot(t, people[:, j], color=TEXT_SECONDARY, alpha=0.15, linewidth=0.7)
        left.plot(t, people[:, :n].mean(axis=1), color=SERIES_COLORS[0], linewidth=2.2,
                  label="One person" if n == 1 else f"Average of {n:,} people")
        left.plot(t, tide, color=SERIES_COLORS[1], linewidth=1.8, linestyle="--", zorder=3,
                  label="Shared tide (the predictable part)")
        left.set_ylim(lo, hi)
        left.set_xticks([])
        left.set_ylabel("Mood", color=TEXT_SECONDARY, fontsize=9)
        left.legend(frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY, loc="upper center",
                    bbox_to_anchor=(0.5, -0.04), ncol=2)

        shown = table.iloc[: i + 1]
        labels = [f"{s:,}" for s in sizes]
        colors = [SERIES_COLORS[0] if k == i else GRID for k in range(i + 1)]
        right.bar(labels[: i + 1], shown["predictable_share"] * 100, color=colors, width=0.7)
        right.set_xlim(-0.6, len(sizes) - 0.4)
        right.set_ylim(0, 100)
        right.set_xlabel("Crowd size", color=TEXT_SECONDARY, fontsize=9)
        right.set_ylabel("% predictable", color=TEXT_SECONDARY, fontsize=9)
        right.tick_params(axis="x", labelsize=7, rotation=45)
        share = table["predictable_share"].iloc[i]
        said = "over 99%" if share > 0.99 else f"{share:.0%}"
        who = "One person" if n == 1 else f"A crowd of {n:,}"
        fig.suptitle(
            f"{who}: {said} of the movement follows the shared tide",
            color=TEXT, fontsize=11, x=0.02, ha="left",
        )
        fig.tight_layout()

    frames = list(range(len(sizes))) + [len(sizes) - 1] * 2  # hold the last frame
    save_gif(fig, draw, frames, out_path, fps)
    plt.close(fig)
    return out_path
