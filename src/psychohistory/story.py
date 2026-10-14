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
            steps = edge_steps(by_step, model, d)
            if steps is None:
                continue
            if steps:
                lines.append(f"In {DOMAIN_PLAIN[d]}, its edge lasts up to about {steps} {STEP_UNIT[d]} ahead.")
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


def edge_steps(by_step: pd.DataFrame | None, model: str, domain: str) -> int | None:
    """How many steps ahead the model still beats the naive guess in a domain (0 = never, None =
    no data). Skill is smoothed over three steps so one lucky step does not count."""
    if by_step is None or by_step.empty:
        return None
    part = by_step[(by_step["model"] == model) & (by_step["domain"] == domain)].sort_values("step")
    if part.empty:
        return None
    smooth = part["skill"].rolling(3, min_periods=1, center=True).median().to_numpy()
    positive = np.flatnonzero(smooth > 0)
    return int(part["step"].iloc[positive[-1]]) if len(positive) else 0


# Colours for the README scoreboard, which GitHub shows in light or dark mode.
SVG_THEMES = {
    "light": {"bg": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3df", "blue": "#2a78d6",
              "orange": "#eb6834", "dot": "#0b0b0b"},
    "dark": {"bg": "#1a1a19", "text": "#f0efec", "muted": "#c3c2b7", "grid": "#383835", "blue": "#3987e5",
             "orange": "#d95926", "dot": "#f0efec"},
}
DOMAIN_CARDS = (("news", "📰", "World news"), ("markets", "📈", "Markets"), ("tech", "🚀", "Technology"))


def scorecard(
    summary: pd.DataFrame | None,
    model: str,
    by_step: pd.DataFrame | None = None,
    results: pd.DataFrame | None = None,
) -> dict[str, dict]:
    """The three numbers per domain that the scoreboard shows: skill, how far ahead it sees, and
    how often it called the direction right. Missing values are None."""
    card = {}
    mine = pd.DataFrame()
    if summary is not None and not summary.empty:
        table = domain_table(summary)
        mine = table[table["model"] == model].set_index("domain")
    for domain, _, _ in DOMAIN_CARDS:
        row = mine.loc[domain] if domain in mine.index else None
        forecasts = None
        if results is not None and not results.empty:
            forecasts = int(((results["model"] == model) & (results["domain"] == domain)).sum())
        card[domain] = {
            "skill": None if row is None else float(row["median_skill"]),
            "direction": None if row is None or pd.isna(row["direction"]) else float(row["direction"]),
            "edge": edge_steps(by_step, model, domain),
            "forecasts": forecasts,
        }
    return card


def scorecard_svg(card: dict[str, dict], model: str, theme: str = "light", updated: str | None = None) -> str:
    """An SVG 'scoreboard' for the top of the README: one column per domain with a big skill
    number, how far ahead the model sees, and its direction hit rate."""
    from html import escape

    c = SVG_THEMES[theme]
    columns = []
    for i, (domain, icon, name) in enumerate(DOMAIN_CARDS):
        x = 40 + i * 380
        v = card.get(domain, {})
        skill, edge, direction = v.get("skill"), v.get("edge"), v.get("direction")
        if skill is None:
            big, colour, caption = "?", c["muted"], "after the first forecast run"
        else:
            big = f"{skill:+.0%}".replace("-", "−")
            colour = c["blue"] if skill > 0 else c["orange"]
            caption = "less error than the simple guess" if skill > 0 else "more error than the simple guess"
        unit = STEP_UNIT[domain]
        sees = "–" if edge is None else ("no edge at any distance" if edge == 0 else f"about {edge} {unit}")
        hits = "–" if direction is None else f"{direction:.0%} of the time"
        columns.append(f"""
<g transform="translate({x},0)">
  <rect x="0" y="62" width="350" height="208" rx="12" class="card"/>
  <text x="22" y="98" class="name">{icon}  {escape(name)}</text>
  <text x="22" y="160" class="big" style="fill:{colour}">{big}</text>
  <text x="22" y="186" class="cap">{escape(caption)}</text>
  <text x="22" y="222" class="k">Sees ahead</text><text x="328" y="222" class="v" text-anchor="end">{escape(sees)}</text>
  <text x="22" y="250" class="k">Right direction</text><text x="328" y="250" class="v" text-anchor="end">{escape(hits)}</text>
</g>""")
    total = sum((card.get(d, {}).get("forecasts") or 0) for d, _, _ in DOMAIN_CARDS)
    footer = (f"Updated {updated} · {total:,} backtest forecasts scored · refreshed every week"
              if updated and total else "Placeholder: the real scoreboard is drawn by the first forecast run")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 310" role="img" aria-label="Scoreboard: how {escape(model)} did in each domain">
<style>
  .bg {{ fill: {c['bg']}; }}
  .card {{ fill: none; stroke: {c['grid']}; stroke-width: 1.5; }}
  .title {{ font: 600 15px Inter, system-ui, sans-serif; fill: {c['muted']}; letter-spacing: .06em; }}
  .name {{ font: 600 18px Inter, system-ui, sans-serif; fill: {c['text']}; }}
  .big {{ font: 700 52px Inter, system-ui, sans-serif; }}
  .cap {{ font: 400 14px Inter, system-ui, sans-serif; fill: {c['muted']}; }}
  .k {{ font: 400 14px Inter, system-ui, sans-serif; fill: {c['muted']}; }}
  .v {{ font: 600 14px Inter, system-ui, sans-serif; fill: {c['text']}; }}
  .foot {{ font: 400 12px Inter, system-ui, sans-serif; fill: {c['muted']}; }}
</style>
<rect class="bg" width="1200" height="310" rx="16"/>
<text x="40" y="42" class="title">SCOREBOARD  ·  {escape(model.upper())}  VS  "TOMORROW LOOKS LIKE TODAY"</text>
{''.join(columns)}
<text x="40" y="296" class="foot">{escape(footer)}</text>
</svg>
"""


def write_scorecards(out_dir: Path, card: dict[str, dict], model: str, updated: str | None) -> list[Path]:
    paths = []
    for theme in SVG_THEMES:
        path = out_dir / "plots" / f"scorecard-{theme}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(scorecard_svg(card, model, theme, updated))
        paths.append(path)
    return paths


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
        from PIL import Image  # noqa: F401  (needed by save_gif)
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

    save_gif(fig, draw, range(len(origins)), out_path, fps)
    plt.close(fig)
    return out_path


def save_gif(fig, draw, frames, out_path: Path, fps: float) -> Path:
    """Render ``draw(i)`` for each frame into an animated GIF with one shared palette.

    GIFs hold 256 colours per frame; quantizing each frame on its own can turn a thin orange
    line grey. Seeding a shared palette with large swatches of the chart colours keeps them true."""
    from PIL import Image

    images = []
    for i in frames:
        draw(i)
        fig.canvas.draw()
        images.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()))
    swatches = Image.new("RGB", (len(SERIES_COLORS + [TEXT, TEXT_SECONDARY, GRID, SURFACE]) * 64, 64))
    for k, color in enumerate(SERIES_COLORS + [TEXT, TEXT_SECONDARY, GRID, SURFACE]):
        swatches.paste(color, (k * 64, 0, (k + 1) * 64, 64))
    sample = Image.new("RGB", (images[0].width, images[0].height * 2 + 64), SURFACE)
    sample.paste(images[0], (0, 0))
    sample.paste(images[-1], (0, images[0].height))
    sample.paste(swatches, (0, images[0].height * 2))
    palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    frames_p = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames_p[0].save(out_path, save_all=True, append_images=frames_p[1:], duration=int(1000 / fps), loop=0, optimize=True)
    return out_path
