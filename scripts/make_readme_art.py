"""Regenerate the README artwork in docs/assets/ (illustrations, not results).

    python scripts/make_readme_art.py

* banner-light.svg / banner-dark.svg - animated hero: history draws in, the forecast fan opens,
  then "what really happened" dots appear. Pure SVG + CSS, so it animates on github.com.
* how-to-read.svg - labelled anatomy of a fan chart, for readers new to forecasts.
* seldon-crowd.gif - the toy crowd simulation (psychohistory.simulate), animated.
* placeholder scoreboard (results/plots/scorecard-*.svg) and charts in results/plots/ until the first real run replaces them.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"

THEMES = {
    "light": {"bg": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3df", "blue": "#2a78d6",
              "orange": "#eb6834", "dot": "#0b0b0b"},
    "dark": {"bg": "#1a1a19", "text": "#f0efec", "muted": "#c3c2b7", "grid": "#383835", "blue": "#3987e5",
             "orange": "#d95926", "dot": "#f0efec"},
}


def illustrative_series(seed: int = 7):
    """A made-up wandering line plus a forecast fan for it (illustration only)."""
    rng = np.random.default_rng(seed)
    history = 50 + np.cumsum(rng.normal(0.15, 1.2, 60))
    steps = np.arange(1, 21)
    median = history[-1] + 0.2 * steps
    spread = 1.28 * 1.2 * np.sqrt(steps)
    # "Reality" wanders mostly inside the band, as a calibrated forecast promises.
    future = median + np.clip(np.cumsum(rng.normal(0, 0.6, 20)), -0.9 * spread, 0.9 * spread)
    return history, future, median, median - spread, median + spread


def to_xy(values, x0, x1, y0, y1, lo, hi, offset=0, total=None):
    total = total or len(values)
    xs = x0 + (np.arange(len(values)) + offset) * (x1 - x0) / (total - 1)
    ys = y1 - (np.asarray(values) - lo) * (y1 - y0) / (hi - lo)
    return xs, ys


def pts(xs, ys):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))


def banner(theme: str) -> str:
    c = THEMES[theme]
    history, future, median, low, high = illustrative_series()
    lo, hi = min(history.min(), low.min(), future.min()) - 2, max(history.max(), high.max(), future.max()) + 2
    x0, x1, y0, y1, total = 640, 1160, 50, 270, 80
    hx, hy = to_xy(history, x0, x1, y0, y1, lo, hi, 0, total)
    fx, fy = to_xy(future, x0, x1, y0, y1, lo, hi, 60, total)
    mx, my = to_xy(median, x0, x1, y0, y1, lo, hi, 60, total)
    _, ly = to_xy(low, x0, x1, y0, y1, lo, hi, 60, total)
    _, uy = to_xy(high, x0, x1, y0, y1, lo, hi, 60, total)
    fan = pts([hx[-1], *mx, *mx[::-1], hx[-1]], [hy[-1], *uy, *ly[::-1], hy[-1]])
    dots = "".join(
        f'<circle class="dot" style="animation-delay:{3.2 + i * 0.08:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="3.2"/>'
        for i, (x, y) in enumerate(zip(fx, fy))
    )
    grid = "".join(f'<line x1="{x0}" x2="{x1}" y1="{y:.0f}" y2="{y:.0f}"/>' for y in np.linspace(y0, y1, 5))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" role="img" aria-label="World Predictions: an animated forecast fan chart">
<style>
  .bg {{ fill: {c['bg']}; }}
  .title {{ font: 700 46px Inter, system-ui, sans-serif; fill: {c['text']}; }}
  .sub {{ font: 400 19px Inter, system-ui, sans-serif; fill: {c['muted']}; }}
  .tag {{ font: 600 14px Inter, system-ui, sans-serif; fill: {c['muted']}; letter-spacing: .08em; }}
  .grid line {{ stroke: {c['grid']}; stroke-width: 1; }}
  .history {{ fill: none; stroke: {c['blue']}; stroke-width: 3; stroke-linejoin: round;
             stroke-dasharray: 1400; stroke-dashoffset: 1400; animation: draw 2s ease-out forwards; }}
  .fan {{ fill: {c['orange']}; opacity: 0; animation: fade .9s ease-out 2s forwards; }}
  .median {{ fill: none; stroke: {c['orange']}; stroke-width: 3; opacity: 0; animation: show .5s ease-out 2.4s forwards; }}
  .dot {{ fill: {c['dot']}; opacity: 0; animation: show .3s ease-out forwards; }}
  .label {{ font: 500 13px Inter, system-ui, sans-serif; fill: {c['muted']}; opacity: 0; animation: show .6s ease-out 2.8s forwards; }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
  @keyframes fade {{ to {{ opacity: .22; }} }}
  @keyframes show {{ to {{ opacity: 1; }} }}
  @media (prefers-reduced-motion: reduce) {{
    .history, .fan, .median, .dot, .label {{ animation: none; opacity: 1; stroke-dashoffset: 0; }}
    .fan {{ opacity: .22; }}
  }}
</style>
<rect class="bg" width="1200" height="320" rx="16"/>
<text class="tag" x="48" y="88">PSYCHOHISTORY  ×  GOOGLE TIMESFM</text>
<text class="title" x="48" y="146">World Predictions</text>
<text class="sub" x="48" y="190">Can Hari Seldon's math predict the future?</text>
<text class="sub" x="48" y="218">Testing an AI forecaster on world news, markets</text>
<text class="sub" x="48" y="246">(stocks, gold, silver) and new technologies.</text>
<g class="grid">{grid}</g>
<polygon class="fan" points="{fan}"/>
<polyline class="history" points="{pts(hx, hy)}"/>
<polyline class="median" points="{pts([hx[-1], *mx], [hy[-1], *my])}"/>
{dots}
<text class="label" x="{x0}" y="{y1 + 34}">what it could see</text>
<text class="label" x="{x1}" y="{y1 + 34}" text-anchor="end">its forecast  ·  what really happened</text>
</svg>
"""


def how_to_read(theme: str) -> str:
    c = THEMES[theme]
    history, future, median, low, high = illustrative_series(seed=3)
    lo, hi = min(history.min(), low.min(), future.min()) - 2, max(history.max(), high.max(), future.max()) + 2
    x0, x1, y0, y1, total = 50, 680, 40, 300, 80
    hx, hy = to_xy(history, x0, x1, y0, y1, lo, hi, 0, total)
    fx, fy = to_xy(future, x0, x1, y0, y1, lo, hi, 60, total)
    mx, my = to_xy(median, x0, x1, y0, y1, lo, hi, 60, total)
    _, ly = to_xy(low, x0, x1, y0, y1, lo, hi, 60, total)
    _, uy = to_xy(high, x0, x1, y0, y1, lo, hi, 60, total)
    fan = pts([hx[-1], *mx, *mx[::-1], hx[-1]], [hy[-1], *uy, *ly[::-1], hy[-1]])
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c["dot"]}"/>' for x, y in zip(fx, fy))
    today = hx[-1]

    def note(n, x, y, tx, ty, text):
        return (f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{tx:.0f}" y2="{ty:.0f}" stroke="{c["muted"]}" stroke-width="1"/>'
                f'<circle cx="{tx:.0f}" cy="{ty:.0f}" r="11" fill="{c["text"]}"/>'
                f'<text x="{tx:.0f}" y="{ty + 4:.0f}" text-anchor="middle" class="n">{n}</text>'
                f'<text x="{tx + 18:.0f}" y="{ty + 5:.0f}" class="t">{text}</text>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 340" role="img" aria-label="How to read a forecast fan chart">
<style>
  .t {{ font: 500 14px Inter, system-ui, sans-serif; fill: {c['text']}; }}
  .n {{ font: 700 12px Inter, system-ui, sans-serif; fill: {c['bg']}; }}
  .m {{ font: 400 12px Inter, system-ui, sans-serif; fill: {c['muted']}; }}
</style>
<rect width="1100" height="340" rx="12" fill="{c['bg']}"/>
<line x1="{today:.0f}" x2="{today:.0f}" y1="{y0}" y2="{y1}" stroke="{c['grid']}" stroke-width="2" stroke-dasharray="4 4"/>
<text x="{today:.0f}" y="{y1 + 20}" text-anchor="middle" class="m">today</text>
<polygon points="{fan}" fill="{c['orange']}" opacity=".22"/>
<polyline points="{pts(hx, hy)}" fill="none" stroke="{c['blue']}" stroke-width="2.5"/>
<polyline points="{pts([hx[-1], *mx], [hy[-1], *my])}" fill="none" stroke="{c['orange']}" stroke-width="2.5"/>
{dots}
{note(1, hx[52], hy[52] - 4, 740, 70, "The past it could see")}
{note(2, mx[19], my[19], 740, 130, "Its best guess")}
{note(3, mx[16], uy[16], 740, 190, "80% range: reality lands here 8 times in 10")}
{note(4, fx[12], fy[12], 740, 250, "What really happened, scored later")}
</svg>
"""


def placeholder_png(path: Path, text: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(7.5, 3.4), dpi=120)
    fig.set_facecolor("#f3f2ee")
    fig.text(0.5, 0.55, text, ha="center", va="center", fontsize=13, color="#52514e")
    fig.text(0.5, 0.38, "GitHub: Actions → predict → Run workflow, or run `psychohistory run` locally.",
             ha="center", va="center", fontsize=9, color="#52514e")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (ASSETS / f"banner-{theme}.svg").write_text(banner(theme))
        (ASSETS / f"how-to-read-{theme}.svg").write_text(how_to_read(theme))
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from psychohistory.simulate import crowd_gif
    from psychohistory.story import scorecard, write_scorecards

    crowd_gif(ASSETS / "seldon-crowd.gif")
    plots = ROOT / "results" / "plots"
    if not (plots / "scorecard-light.svg").exists():
        write_scorecards(plots.parent, scorecard(None, "timesfm-2.5"), "timesfm-2.5", None)
    for name, text in [
        ("skill_by_domain.png", "The skill chart appears after the first forecast run."),
        ("skill_by_step.png", "The 'how far ahead' chart appears after the first forecast run."),
    ]:
        if not (plots / name).exists():
            placeholder_png(plots / name, text)
    replay = plots / "replay.gif"
    if not replay.exists():
        from PIL import Image

        png = plots / "_replay_placeholder.png"
        placeholder_png(png, "The animated replay appears after the first forecast run.")
        Image.open(png).convert("P").save(replay)
        png.unlink()
    print(f"Wrote artwork to {ASSETS} and placeholders to {plots}")


if __name__ == "__main__":
    main()
