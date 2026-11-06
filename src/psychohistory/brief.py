"""The brief: what changed since the last run, on one screen and in one Markdown file.

Three questions a reader has every morning, each answered only from sealed forecasts:

* **What came due?** Every sealed forecast whose target date fell in the last week, scored against
  what happened: per model, the share inside its 80% range, the share with the right direction and
  the skill against "no change". The lead model's closest calls and its biggest surprises are listed
  by name. A surprise is measured in range widths outside the 80% range, so a miss on a calm series
  counts as much as a miss on a wild one.
* **Where did a model change its mind?** The lead model's two newest sealed batches, asked the same
  question: the chance each series ends above *today's* level on the farthest date both batches
  cover. Comparing each batch's own "chance higher" would mix a change of mind with a change of
  starting point; holding the level fixed leaves only the change of mind. A flip is a call that
  crossed 50% and landed at least 2 points past it.
* **Who is on a streak?** The benchmark model (it has the longest sealed record). One call per sealed batch per series (the next-step call), so overlapping
  days of the same batch never count twice. The run of right (or wrong) directions that ends at the
  newest scored call is the streak.

``psychohistory brief`` prints it, ``--write`` saves results/BRIEF.md, and the app shows it on Today.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .frames import p_up3
from .monitor import _skill

BRIEF = Path("results/BRIEF.md")
DUE_DAYS = 7
SHOWN = 5
MIN_STREAK = 3
FLIP_MARGIN = 0.02  # a flip must land at least 2 points past 50%, so 51% to 49% is not news
# Who gets a row in the "came due" table, in this order after the benchmark.
RIVALS = ("radiant", "chronos-bolt", "seldon", "seldon-laws", "auto-ets", "ensemble")


def lead_model(frame: pd.DataFrame | None, model: str) -> str:
    """Radiant speaks first where it has sealed forecasts, as on the rest of Today."""
    if frame is not None and not frame.empty and (frame["model"] == "radiant").any():
        return "radiant"
    return model


def _r(x, digits: int = 4):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, digits) if np.isfinite(v) else None


def _miss_in_widths(r) -> float:
    """How far outside the 80% range the outcome landed, in range widths (0 when inside)."""
    lo, hi = sorted((r.q10, r.q90))
    width = max(hi - lo, 1e-12)
    if r.actual < lo:
        return (lo - r.actual) / width
    if r.actual > hi:
        return (r.actual - hi) / width
    return 0.0


def _call(r, title: Callable[[str], str]) -> dict:
    last = r.last_value if r.last_value else np.nan
    return {
        "id": r.series_id, "title": title(r.series_id), "domain": r.domain, "model": r.model,
        "made_on": str(r.made_on)[:10], "target": str(r.target_date)[:10], "step": int(r.step),
        "p": _r(r.p_up), "mid": _r((r.q50 - last) / abs(last)), "low": _r((r.q10 - last) / abs(last)),
        "high": _r((r.q90 - last) / abs(last)), "actual": _r((r.actual - last) / abs(last)),
        "inside": bool(r.in_band80), "right": None if pd.isna(r.direction_correct) else bool(r.direction_correct),
        "miss": _r(_miss_in_widths(r), 3),
    }


def came_due(scored: pd.DataFrame | None, model: str, title: Callable[[str], str] = str,
             days: int = DUE_DAYS, shown: int = SHOWN) -> dict | None:
    if scored is None or scored.empty:
        return None
    s = scored.copy()
    s["target_date"] = pd.to_datetime(s["target_date"])
    end = s["target_date"].max()
    s = s[s["target_date"] > end - pd.Timedelta(days=days)]
    s = s[s["last_value"].abs() > 0]
    if s.empty:
        return None
    rows = []
    for m in (model, *RIVALS):
        part = s[s["model"] == m]
        if part.empty:
            continue
        rows.append([m, int(len(part)), int(part["series_id"].nunique()), _r(part["in_band80"].mean()),
                     _r(part["direction_correct"].mean()), _r(_skill(part))])
    lead = lead_model(s, model)
    mine = s[s["model"] == lead].copy()
    mine["miss"] = [_miss_in_widths(r) for r in mine.itertuples()]
    mine["closeness"] = (mine["actual"] - mine["q50"]).abs() / (mine["q90"] - mine["q10"]).abs().clip(lower=1e-12)
    # One line per series: its worst miss, or its closest call.
    surprises = mine[mine["miss"] > 0].sort_values("miss", ascending=False).drop_duplicates("series_id").head(shown)
    nailed = mine[(mine["miss"] == 0) & (mine["direction_correct"] == 1)].sort_values("closeness")
    nailed = nailed.drop_duplicates("series_id").head(shown)
    return {
        "since": (end - pd.Timedelta(days=days - 1)).date().isoformat(), "until": end.date().isoformat(),
        "lead": lead, "models": rows,
        "nailed": [_call(r, title) for r in nailed.itertuples()],
        "surprises": [_call(r, title) for r in surprises.itertuples()],
    }


def revisions(ledger: pd.DataFrame | None, model: str, title: Callable[[str], str] = str, shown: int = 8) -> dict | None:
    if ledger is None or ledger.empty:
        return None
    lead = lead_model(ledger, model)
    mine = ledger[ledger["model"] == lead]
    batches = sorted(mine["made_on"].astype(str).unique())
    if len(batches) < 2:
        return None
    old_on, new_on = batches[-2], batches[-1]
    old = mine[mine["made_on"].astype(str) == old_on]
    new = mine[mine["made_on"].astype(str) == new_on]
    items = []
    for sid, n in new.groupby("series_id"):
        o = old[old["series_id"] == sid]
        common = sorted(set(n["target_date"].astype(str)) & set(o["target_date"].astype(str)))
        if not common:
            continue
        target = common[-1]
        nr = n[n["target_date"].astype(str) == target].iloc[0]
        orow = o[o["target_date"].astype(str) == target].iloc[0]
        level = float(nr["last_value"])
        if not np.isfinite(level) or level == 0:
            continue
        p_new = p_up3(nr["q10"], nr["q50"], nr["q90"], level)
        p_old = p_up3(orow["q10"], orow["q50"], orow["q90"], level)
        items.append({
            "id": sid, "title": title(sid), "domain": nr["domain"], "target": target,
            "p_old": _r(p_old), "p_new": _r(p_new), "shift": _r(p_new - p_old),
            "mid_old": _r((orow["q50"] - level) / abs(level)), "mid_new": _r((nr["q50"] - level) / abs(level)),
            "moved": _r((level - float(orow["last_value"])) / abs(float(orow["last_value"]))) if orow["last_value"] else None,
            "flip": bool((p_old - 0.5) * (p_new - 0.5) < 0 and min(abs(p_old - 0.5), abs(p_new - 0.5)) >= FLIP_MARGIN),
        })
    items.sort(key=lambda x: -abs(x["shift"] or 0))
    return {"model": lead, "old": old_on, "new": new_on, "series": len(items),
            "flips": sum(x["flip"] for x in items), "items": items[:shown]}


def streaks(scored: pd.DataFrame | None, model: str, title: Callable[[str], str] = str,
            minimum: int = MIN_STREAK, shown: int = SHOWN) -> dict | None:
    if scored is None or scored.empty:
        return None
    lead = model  # the benchmark has the longest record of sealed batches
    s = scored[(scored["model"] == lead) & (scored["step"] == 1)].dropna(subset=["direction_correct"])
    if s.empty:
        return None
    hot, cold = [], []
    for sid, g in s.sort_values(["made_on", "target_date"]).groupby("series_id"):
        calls = g.drop_duplicates("made_on", keep="last")["direction_correct"].astype(int).tolist()
        if not calls:
            continue
        last, run = calls[-1], 0
        for c in reversed(calls):
            if c != last:
                break
            run += 1
        if run < minimum:
            continue
        row = {"id": sid, "title": title(sid), "domain": g["domain"].iloc[-1], "run": run, "calls": len(calls),
               "right": int(sum(calls)), "since": str(g.drop_duplicates("made_on", keep="last")["made_on"].iloc[-run])}
        (hot if last == 1 else cold).append(row)
    key = lambda x: (-x["run"], -x["right"] / max(1, x["calls"]))  # noqa: E731
    return {"model": lead, "minimum": minimum, "batches": int(s["made_on"].nunique()),
            "hot": sorted(hot, key=key)[:shown], "cold": sorted(cold, key=key)[:shown]}


def build(ledger: pd.DataFrame | None, scored: pd.DataFrame | None, model: str,
          title: Callable[[str], str] = str) -> dict | None:
    out = {"due": came_due(scored, model, title), "revisions": revisions(ledger, model, title),
           "streaks": streaks(scored, model, title)}
    if not any(out.values()):
        return None
    out["text"] = text(out)  # the app's "Copy as text" button
    return out


# ---------- text ----------

NAMES = {"radiant": "Radiant", "chronos-bolt": "Chronos-Bolt", "seldon": "Seldon", "seldon-laws": "Seldon laws",
         "auto-ets": "AutoETS", "ensemble": "Ensemble"}


def _name(m: str) -> str:
    return "TimesFM" if m.startswith("timesfm") else NAMES.get(m, m)


def _pct(v, signed: bool = False) -> str:
    if v is None:
        return "–"
    return f"{v:+.1%}" if signed else f"{v:.0%}"


def text(brief: dict | None) -> str:
    """The brief as Markdown (results/BRIEF.md, the CLI and the app's copy button)."""
    if not brief:
        return "# The brief\n\nNothing sealed has come due yet. The brief fills in after two forecast runs.\n"
    lines = ["# The brief", ""]
    due = brief.get("due")
    if due:
        lines += [f"## Came due, {due['since']} to {due['until']}", "",
                  "| Model | Forecasts | Series | Inside 80% range | Right direction | Skill vs no change |",
                  "|---|---:|---:|---:|---:|---:|"]
        lines += [f"| {_name(m)} | {n} | {k} | {_pct(i)} | {_pct(d)} | {_pct(s, True)} |" for m, n, k, i, d, s in due["models"]]
        lines += ["", f"**{_name(due['lead'])}'s closest calls:** " + ("; ".join(
            f"{c['title']} (said {_pct(c['mid'], True)}, was {_pct(c['actual'], True)} by {c['target']})" for c in due["nailed"]) or "none this week") + ".",
            "", f"**Biggest surprises:** " + ("; ".join(
            f"{c['title']} (range {_pct(c['low'], True)} to {_pct(c['high'], True)}, was {_pct(c['actual'], True)}, "
            f"{c['miss']:.1f} range widths outside)" for c in due["surprises"]) or "none: every outcome landed inside its range") + ".", ""]
    rev = brief.get("revisions")
    if rev and rev["items"]:
        lines += [f"## {_name(rev['model'])} changed its mind, {rev['old']} to {rev['new']}", "",
                  f"Chance of ending above today's level on the farthest date both batches cover. "
                  f"{rev['flips']} of {rev['series']} series flipped side.", "",
                  "| Series | Target | Before | Now | Shift | Series moved |", "|---|---|---:|---:|---:|---:|"]
        lines += [f"| {x['title']}{' (flip)' if x['flip'] else ''} | {x['target']} | {_pct(x['p_old'])} | {_pct(x['p_new'])} | "
                  f"{x['shift'] * 100:+.0f} pts | {_pct(x['moved'], True)} |" for x in rev["items"]]
        lines.append("")
    st = brief.get("streaks")
    if st and (st["hot"] or st["cold"]):
        lines += [f"## Streaks ({_name(st['model'])}, next-step calls, one per sealed batch)", ""]
        if st["hot"]:
            lines.append("**Right " + f"{st['minimum']}+ in a row:** " + "; ".join(f"{x['title']} ({x['run']} straight, {x['right']} of {x['calls']} overall)" for x in st["hot"]) + ".")
        if st["cold"]:
            lines.append("")
            lines.append("**Wrong " + f"{st['minimum']}+ in a row:** " + "; ".join(f"{x['title']} ({x['run']} straight, {x['right']} of {x['calls']} overall)" for x in st["cold"]) + ".")
        lines += ["", "A streak of a few calls is weak evidence on its own; the Monitor's tests say whether a record is more than luck.", ""]
    return "\n".join(lines)


def write(brief: dict | None, path: Path = BRIEF) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text(brief), encoding="utf-8")
    return path
