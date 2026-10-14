"""Interactive HTML dashboard (``results/dashboard.html``) built with Plotly.

Layout ideas borrowed from Our World in Data's Grapher (one clear question per chart, a short
caption, a source line) and from Plotly's own fan-chart examples. The file is self-contained
except for plotly.js, which loads from Plotly's CDN, so it can be opened locally or served with
GitHub Pages.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import pandas as pd

from .backtest import calibration, domain_table
from .report import DOMAIN_TITLES, GRID, SERIES_COLORS, SURFACE, TEXT, TEXT_SECONDARY, model_order

DOMAINS = ("news", "markets", "tech")
SOURCE = "Model: Google TimesFM. Data: GDELT, Yahoo Finance (yfinance), Wikimedia, Our World in Data."


def _layout(fig, title: str, x_title: str = "", y_title: str = ""):
    fig.update_layout(
        template="plotly_white",
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 16, "color": TEXT}},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": "Inter, system-ui, sans-serif", "color": TEXT_SECONDARY, "size": 12},
        margin={"l": 60, "r": 20, "t": 60, "b": 50},
        legend={"orientation": "h", "y": -0.2},
        hovermode="x unified",
        height=380,
    )
    fig.update_xaxes(title=x_title, gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(title=y_title, gridcolor=GRID, zerolinecolor=TEXT_SECONDARY)
    return fig


def _skill_figure(summary: pd.DataFrame, main_model: str):
    import plotly.graph_objects as go

    table = domain_table(summary)
    table = table[table["model"] != "naive"]
    fig = go.Figure()
    for i, model in enumerate(model_order(table["model"], main_model)):
        rows = table[table["model"] == model].set_index("domain")
        domains = [d for d in DOMAINS if d in rows.index]
        fig.add_bar(
            x=[DOMAIN_TITLES[d] for d in domains],
            y=[rows.loc[d, "median_skill"] for d in domains],
            name=model,
            marker_color=SERIES_COLORS[i % len(SERIES_COLORS)],
            hovertemplate="%{x}<br>" + model + ": %{y:.1%} less error than naive<extra></extra>",
        )
    fig.update_layout(barmode="group", hovermode="closest")
    fig.update_yaxes(tickformat=".0%")
    return _layout(fig, "Can the future be predicted? Skill versus 'tomorrow = today'", "", "Median skill")


def _horizon_figure(by_step: pd.DataFrame, model: str):
    import plotly.graph_objects as go

    rows = by_step[by_step["model"] == model]
    fig = go.Figure()
    for i, domain in enumerate(d for d in DOMAINS if d in set(rows["domain"])):
        part = rows[rows["domain"] == domain].sort_values("step")
        fig.add_scatter(
            x=part["step"], y=part["skill"], mode="lines", name=DOMAIN_TITLES[domain],
            line={"color": SERIES_COLORS[i], "width": 2},
            hovertemplate="%{y:.1%}<extra>" + DOMAIN_TITLES[domain] + "</extra>",
        )
    fig.add_hline(y=0, line_color=TEXT_SECONDARY, line_width=1)
    fig.update_yaxes(tickformat=".0%")
    return _layout(fig, f"How far ahead can {model} see?", "Steps ahead", "Median skill vs naive")


def _calibration_figure(results: pd.DataFrame, model: str):
    import plotly.graph_objects as go

    table = calibration(results, model)
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfectly honest odds",
                    line={"color": TEXT_SECONDARY, "dash": "dot", "width": 1}, hoverinfo="skip")
    present = set(table["domain"]) if not table.empty else set()
    for i, domain in enumerate(d for d in DOMAINS if d in present):
        part = table[table["domain"] == domain]
        fig.add_scatter(
            x=part["said"], y=part["happened"], mode="markers+lines", name=DOMAIN_TITLES[domain],
            marker={"size": 10, "color": SERIES_COLORS[i], "line": {"color": SURFACE, "width": 2}},
            line={"color": SERIES_COLORS[i], "width": 1},
            customdata=part["forecasts"],
            hovertemplate="Said %{x:.0%}, happened %{y:.0%} (%{customdata} forecasts)<extra></extra>",
        )
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(range=[-0.03, 1.03], tickformat=".0%")
    fig.update_yaxes(range=[-0.03, 1.03], tickformat=".0%")
    return _layout(fig, "Are its odds honest?", "Chance of rising the model gave", "How often it really rose")


def _fan_figure(latest: pd.DataFrame, ledger: pd.DataFrame, data: dict[str, pd.Series], model: str):
    """One fan chart per series with a dropdown to switch between them."""
    import plotly.graph_objects as go

    from . import catalog

    fig = go.Figure()
    buttons = []
    series_ids = [s for s in latest[latest["model"] == model]["series_id"] if s in data]
    for n, series_id in enumerate(series_ids):
        newest = ledger[(ledger["model"] == model) & (ledger["series_id"] == series_id)]
        newest = newest[newest["made_on"] == newest["made_on"].max()].sort_values("step")
        dates = pd.to_datetime(newest["target_date"])
        history = data[series_id].iloc[-max(6 * len(newest), 60):]
        visible = n == 0
        fig.add_scatter(x=history.index, y=history.values, name="Observed", visible=visible,
                        line={"color": SERIES_COLORS[0], "width": 2})
        fig.add_scatter(x=list(dates) + list(dates[::-1]), y=list(newest["q90"]) + list(newest["q10"][::-1]),
                        fill="toself", fillcolor="rgba(235,104,52,0.18)", line={"width": 0},
                        name="80% band", visible=visible, hoverinfo="skip")
        fig.add_scatter(x=dates, y=newest["q50"], name="Forecast (median)", visible=visible,
                        line={"color": SERIES_COLORS[1], "width": 2})
        mask = [False] * (3 * len(series_ids))
        mask[3 * n: 3 * n + 3] = [True, True, True]
        try:
            label = catalog.by_id(series_id).description
        except KeyError:
            label = series_id
        buttons.append({"label": label, "method": "update", "args": [{"visible": mask}]})
    if buttons:
        fig.update_layout(updatemenus=[{"buttons": buttons, "x": 0, "xanchor": "left", "y": 1.18, "yanchor": "top"}])
    fig = _layout(fig, "What the model expects next", "", "")
    fig.update_layout(margin={"t": 100}, height=440)
    return fig


def _replay_figure(series: pd.Series, paths: pd.DataFrame, title: str):
    """Animated replay: press play to step through past forecasts and see each one meet reality."""
    import plotly.graph_objects as go

    origins = sorted(paths["origin"].unique())
    first = pd.Timestamp(origins[0])
    end = pd.Timestamp(paths["date"].max())
    window = series[(series.index >= first - (end - first) * 0.6) & (series.index <= end)]

    def traces(origin):
        now = paths[paths["origin"] == origin].sort_values("step")
        dates = pd.to_datetime(now["date"])
        known = window[window.index <= pd.Timestamp(origin)]
        return [
            go.Scatter(x=known.index, y=known.values, name="What it could see", line={"color": SERIES_COLORS[0], "width": 2}),
            go.Scatter(x=list(dates) + list(dates[::-1]), y=list(now["q90"]) + list(now["q10"][::-1]), fill="toself",
                       fillcolor="rgba(235,104,52,0.2)", line={"width": 0}, name="Its 80% range", hoverinfo="skip"),
            go.Scatter(x=dates, y=now["q50"], name="Its best guess", line={"color": SERIES_COLORS[1], "width": 2}),
            go.Scatter(x=dates, y=now["actual"], mode="markers", name="What really happened",
                       marker={"color": TEXT, "size": 6}),
        ]

    frames = [go.Frame(data=traces(o), name=str(o)) for o in origins]
    fig = go.Figure(data=traces(origins[0]), frames=frames)
    fig.update_layout(
        updatemenus=[{
            "type": "buttons", "showactive": False, "x": 0, "y": -0.28, "xanchor": "left",
            "buttons": [
                {"label": "▶ Play", "method": "animate",
                 "args": [None, {"frame": {"duration": 900, "redraw": True}, "fromcurrent": True, "transition": {"duration": 300}}]},
                {"label": "❚❚ Pause", "method": "animate",
                 "args": [[None], {"frame": {"duration": 0}, "mode": "immediate"}]},
            ],
        }],
        sliders=[{
            "x": 0.18, "len": 0.82, "y": -0.2, "currentvalue": {"prefix": "Forecast made on "},
            "steps": [{"label": str(o), "method": "animate",
                       "args": [[str(o)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}]} for o in origins],
        }],
    )
    fig.update_xaxes(range=[window.index[0], window.index[-1]])
    pad = 0.05 * float(window.max() - window.min())
    fig.update_yaxes(range=[float(window.min()) - pad, float(window.max()) + pad])
    fig = _layout(fig, f"Replay: {title}. What it expected vs what happened", "", "")
    fig.update_layout(height=470, margin={"b": 130}, legend={"y": 1.08, "orientation": "h"})
    return fig


def write_dashboard(
    results: pd.DataFrame,
    summary: pd.DataFrame,
    model: str,
    out_dir: Path,
    by_step: pd.DataFrame | None = None,
    latest: pd.DataFrame | None = None,
    ledger: pd.DataFrame | None = None,
    data: dict[str, pd.Series] | None = None,
    paths: pd.DataFrame | None = None,
    headline: str | None = None,
) -> Path | None:
    try:
        import plotly  # noqa: F401
    except ImportError:
        return None
    from . import catalog
    from .story import headlines

    figures = []
    if paths is not None and not paths.empty and data and headline in data:
        figures.append(_replay_figure(data[headline], paths, catalog.by_id(headline).description))
    figures.append(_skill_figure(summary, model))
    if by_step is not None and not by_step.empty:
        figures.append(_horizon_figure(by_step, model))
    if "p_up" in results.columns:
        figures.append(_calibration_figure(results, model))
    if latest is not None and ledger is not None and data:
        figures.append(_fan_figure(latest, ledger, data, model))

    blocks = []
    for i, fig in enumerate(figures):
        blocks.append(
            '<section class="card">'
            + fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False, config={"displaylogo": False})
            + "</section>"
        )
    plain = headlines(summary, model, results, by_step)
    cards = "".join(f'<li>{html.escape(line)}</li>' for line in plain)
    plain_html = f'<section class="plain"><h2>In plain English</h2><ul>{cards}</ul></section>' if plain else ""
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Predictions</title>
<style>
  :root {{ --surface: {SURFACE}; --text: {TEXT}; --muted: {TEXT_SECONDARY}; --line: {GRID}; }}
  body {{ margin: 0; background: var(--surface); color: var(--text); font-family: Inter, system-ui, sans-serif; }}
  main {{ max-width: 1040px; margin: 0 auto; padding: 32px 16px 64px; }}
  h1 {{ font-size: 28px; margin: 0 0 4px; }}
  p.lede {{ color: var(--muted); margin: 0 0 24px; max-width: 70ch; line-height: 1.5; }}
  .card {{ border: 1px solid var(--line); border-radius: 12px; padding: 8px; margin: 0 0 20px; overflow-x: auto; }}
  footer {{ color: var(--muted); font-size: 13px; }}
  .plain {{ background: #f3f7fd; border-left: 4px solid #2a78d6; border-radius: 8px; padding: 12px 20px; margin: 0 0 24px; }}
  .plain h2 {{ font-size: 16px; margin: 4px 0 8px; }}
  .plain li {{ margin: 6px 0; line-height: 1.5; }}
</style></head>
<body><main>
<h1>World Predictions</h1>
<p class="lede">Can Hari Seldon's psychohistory work with a modern forecasting model? {html.escape(model)} is scored against
simple baselines on world news attention, markets and technology. Generated {date.today().isoformat()}.
Full tables are in REPORT.md.</p>
{plain_html}
{''.join(blocks)}
<footer>{html.escape(SOURCE)} See CREDITS.md and REFERENCES.md.</footer>
</main></body></html>
"""
    path = out_dir / "dashboard.html"
    path.write_text(page)
    return path
