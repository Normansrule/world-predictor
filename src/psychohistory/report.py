"""Turns backtest results and the prediction ledger into ``results/REPORT.md`` and charts."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from .backtest import calibration, crises, domain_table, horizon_table, scale_table

log = logging.getLogger(__name__)

# Categorical palette, fixed order (validated for colour-vision deficiency separation).
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"

DOMAIN_TITLES = {
    "news": "World events in the news",
    "markets": "Stock and value markets",
    "tech": "New technologies",
}


def _fmt(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No data._\n"
    return frame.to_markdown(index=False, floatfmt=".3f") + "\n"


def _verdict(skill: float) -> str:
    if pd.isna(skill):
        return "not enough data"
    if skill > 0.05:
        return f"beats the naive baseline ({skill:.0%} less error)"
    if skill < -0.05:
        return f"loses to the naive baseline ({-skill:.0%} more error)"
    return "about the same as the naive baseline"


def write_report(
    results: pd.DataFrame,
    summary: pd.DataFrame,
    model: str,
    ledger_table: pd.DataFrame | None = None,
    out_dir: Path = Path("results"),
    latest: pd.DataFrame | None = None,
    by_step: pd.DataFrame | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    domains = domain_table(summary)
    scales = scale_table(summary)
    lines = [
        "# World Predictions: Seldon scorecard",
        "",
        f"_Generated {date.today().isoformat()} with model `{model}`. "
        "Skill = 1 - MAE(model) / MAE(naive random walk); positive is better than naive. "
        "Coverage80 should be close to 0.80 for an honest forecaster. "
        "Brier scores the probability of going up (0.25 = coin flip, lower is better). See docs/METHODOLOGY.md._",
        "",
        "## 1. Can the future be predicted?",
        "",
    ]
    if (out_dir / "plots" / "skill_by_domain.png").exists():
        lines += ["![Skill by domain](plots/skill_by_domain.png)", ""]
    for domain in ("news", "markets", "tech"):
        row = domains[(domains["domain"] == domain) & (domains["model"] == model)]
        if not row.empty:
            skill = float(row["median_skill"].iloc[0])
            lines.append(f"- **{DOMAIN_TITLES[domain]}**: {model} {_verdict(skill)}.")
    lines += ["", _fmt(domains), "## 2. Seldon's law of large numbers: aggregates vs individuals", ""]
    lines += [
        "Psychohistory only claims to work for very large populations. If that holds here, "
        "aggregate series (indices, composites, world totals) should show higher skill and "
        "lower MASE than individual ones.",
        "",
        _fmt(scales[scales["model"] == model]),
        "## 3. Seldon crises: what the model did not see coming",
        "",
        "Backtest windows where most actual values fell outside the model's 80% band.",
        "",
        _fmt(crises(results, model)),
        "## 4. Prediction ledger (true out-of-sample test)",
        "",
    ]
    if ledger_table is not None and not ledger_table.empty:
        lines.append(_fmt(ledger_table))
    else:
        lines.append("_No ledger predictions have reached their target dates yet._\n")
    lines += _horizon_section(by_step, model, out_dir)
    lines += _calibration_section(results, model)
    lines += ["## 7. Every series", "", _fmt(summary[summary["model"] == model].round(3))]
    lines += _latest_section(latest, model, out_dir)
    path = out_dir / "REPORT.md"
    path.write_text("\n".join(lines))
    return path


def _horizon_section(by_step: pd.DataFrame | None, model: str, out_dir: Path) -> list[str]:
    """The Seldon horizon: how skill changes the further ahead the model looks."""
    lines = ["## 5. How far ahead can it see?", ""]
    if by_step is None or by_step.empty:
        return lines + ["_Run `psychohistory backtest` to measure this._", ""]
    lines += [
        "Median skill versus the naive baseline by how many steps ahead the forecast is "
        "(days for news and tech attention, trading days for markets; yearly adoption series "
        "are too short for this and are left out). "
        "Where skill drops to zero is the limit of the model's foresight in that domain.",
        "",
    ]
    if (out_dir / "plots" / "skill_by_step.png").exists():
        lines += ["![Skill by step](plots/skill_by_step.png)", ""]
    return lines + [_fmt(horizon_table(by_step, model))]


def _calibration_section(results: pd.DataFrame, model: str) -> list[str]:
    """Are the model's odds honest? Compares the probability it gave with what happened."""
    lines = ["## 6. Are its odds honest?", ""]
    if "p_up" not in results.columns:
        return lines + ["_Rerun `psychohistory backtest` to measure this._", ""]
    lines += [
        "Backtest forecasts grouped by the chance they gave of the series ending higher. "
        "`said` is the average probability given, `happened` is how often it really went up. "
        "When the two match, the odds can be taken at face value.",
        "",
    ]
    return lines + [_fmt(calibration(results, model))]


def _latest_section(latest: pd.DataFrame | None, model: str, out_dir: Path) -> list[str]:
    """What the model expects next, with the 10%-90% range as a change from the last value."""
    lines = ["## 8. What the model expects next", ""]
    if latest is None or latest.empty or model not in set(latest["model"]):
        return lines + ["_Run `psychohistory predict` to record forecasts._", ""]
    rows = latest[latest["model"] == model]
    lines += [
        f"Latest forecasts recorded in the ledger (made with data up to each series' last date). "
        "Changes are relative to the last observed value; the range is the 10%-90% band; "
        "\"chance higher\" is the model's probability that the value on the target date is above "
        "today's (scored later with the Brier score: 0 is perfect, 0.25 is a coin flip).",
        "",
    ]
    for domain in ("news", "markets", "tech"):
        part = rows[rows["domain"] == domain]
        if part.empty:
            continue
        lines += [f"### {DOMAIN_TITLES[domain]}", ""]
        table = pd.DataFrame(
            {
                "series": part["series_id"],
                "last": part["last_value"].round(3),
                "target date": part["target_date"],
                "median": part["median_change"].map("{:+.1%}".format),
                "chance higher": part["p_up"].map("{:.0%}".format),
                "range (10%-90%)": [f"{lo:+.1%} to {hi:+.1%}" for lo, hi in zip(part["low_change"], part["high_change"])],
            }
        )
        lines += [table.to_markdown(index=False), ""]
        for series_id in part["series_id"]:
            if (out_dir / "plots" / f"{series_id}.png").exists():
                lines.append(f"![{series_id}](plots/{series_id}.png)")
        lines.append("")
    return lines


def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_skill(summary: pd.DataFrame, out_dir: Path = Path("results")) -> Path | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not installed; skipping charts")
        return None
    table = domain_table(summary)
    table = table[table["model"] != "naive"]
    models = list(dict.fromkeys(table["model"]))
    domains = [d for d in ("news", "markets", "tech") if d in set(table["domain"])]
    fig, ax = plt.subplots(figsize=(7.5, 3.8), dpi=150)
    _style(ax)
    ax.grid(axis="y", visible=False)
    height = 0.8 / max(len(models), 1)
    for i, name in enumerate(models):
        rows = table[table["model"] == name].set_index("domain")["median_skill"]
        values = [float(rows.get(d, 0.0)) for d in domains]
        positions = [j + i * height for j in range(len(domains))]
        ax.barh(positions, values, height=height - 0.04, color=SERIES_COLORS[i % len(SERIES_COLORS)], label=name)
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1)
    ax.set_yticks([j + height * (len(models) - 1) / 2 for j in range(len(domains))])
    ax.set_yticklabels([DOMAIN_TITLES[d] for d in domains], color=TEXT)
    ax.invert_yaxis()
    ax.set_xlabel("Median skill vs naive (higher is better)", color=TEXT_SECONDARY)
    ax.set_title("How much better than 'tomorrow = today'?", color=TEXT, loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="lower right")
    fig.tight_layout()
    path = out_dir / "plots" / "skill_by_domain.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_fan(series: pd.Series, ledger_rows: pd.DataFrame, title: str, out_dir: Path = Path("results")) -> Path | None:
    """History plus the latest forecast's median and 10-90% band."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    rows = ledger_rows.sort_values("step")
    dates = pd.to_datetime(rows["target_date"])
    history = series.iloc[-max(4 * len(rows), 30) :]
    fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=150)
    _style(ax)
    ax.plot(history.index, history.values, color=SERIES_COLORS[0], linewidth=2, label="Observed")
    ax.fill_between(dates, rows["q10"], rows["q90"], color=SERIES_COLORS[1], alpha=0.18, linewidth=0, label="80% band")
    ax.plot(dates, rows["q50"], color=SERIES_COLORS[1], linewidth=2, label="Forecast (median)")
    ax.set_title(title, color=TEXT, loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    path = out_dir / "plots" / f"{series.name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_horizon(by_step: pd.DataFrame, model: str, out_dir: Path = Path("results")) -> Path | None:
    """Skill versus steps ahead, one line per domain."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    rows = by_step[(by_step["model"] == model) & (by_step["step"] > 0)]
    if rows.empty:
        return None
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=150)
    _style(ax)
    for i, domain in enumerate(d for d in ("news", "markets", "tech") if d in set(rows["domain"])):
        part = rows[rows["domain"] == domain].sort_values("step")
        color = SERIES_COLORS[i]
        ax.plot(part["step"], part["skill"], color=color, linewidth=2, label=DOMAIN_TITLES[domain])
    ax.axhline(0, color=TEXT_SECONDARY, linewidth=1)
    ax.set_xlabel("Steps ahead", color=TEXT_SECONDARY)
    ax.set_ylabel("Median skill vs naive", color=TEXT_SECONDARY)
    ax.set_title(f"How far ahead can {model} see?", color=TEXT, loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY, loc="best")
    fig.tight_layout()
    path = out_dir / "plots" / "skill_by_step.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
