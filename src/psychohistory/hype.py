"""The hype cycle: where each new technology's public attention stands, and whether that says
anything about the next three months.

Gartner's hype cycle (Fenn & Raskino, 2008) says attention to a new technology climbs to a peak of
inflated expectations, slides into a trough of disillusionment and then climbs a gentler slope to
a plateau, while real adoption keeps growing underneath. Here attention is the daily Wikipedia
pageviews of the technology's article (from July 2015), and adoption, where there is a yearly
measure, comes from Our World in Data.

Each technology gets a phase from two numbers, both read from the history up to that day only:

* ``level``: the last 90 days' mean pageviews against the highest 90-day mean so far (1 = at the peak);
* ``slope``: the log change of the last 90 days' mean against the 90 days before.

Every phase implies a call about the next 90 days' attention (up, down or flat, within ±10%).
The backtest makes that call once a month across the whole history and checks it against what
happened, beside two plain rivals: momentum (the last 90 days' direction carries on) and "no
change". The hype cycle's own claim, that attention falls after a peak, is checked on its own.
The calls are a pure function of public data, so anyone can recompute them; no ledger is needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

WINDOW = 90        # days in the "now" window and in the look-ahead
FLAT = 0.10        # |log change| below this counts as flat (about ±10%)
NEAR_PEAK = 0.80   # level at or above this is "near the peak"
AT_PEAK = 0.90     # level at or above this while rising is a fresh climb
DEEP = 0.50        # level below this, and flat, is the trough
STEP = 30          # days between backtest origins
MIN_HISTORY = 365  # days of history before the first call
OVERLAP = max(1, WINDOW // STEP)  # calls that share one 90-day look-ahead
BURST = 0.30       # a 90-day move this large (either way) is expected to reverse: the burst rule
FOUND = "2026-11-16"  # the day the burst rule was read off the backtest; only calls after it are a fair test

# Technology -> its Wikipedia attention series and, where one exists, an adoption series.
TECH = [
    ("wiki_llm", "Language models", None),
    ("wiki_ai", "Artificial intelligence", None),
    ("wiki_quantum", "Quantum computing", None),
    ("wiki_crispr", "CRISPR", None),
    ("wiki_ev", "Electric vehicles", "adoption_ev"),
    ("wiki_battery", "Solid-state batteries", "adoption_ev"),
    ("wiki_fusion", "Fusion power", None),
    ("wiki_humanoid", "Humanoid robots", None),
    ("wiki_gene_therapy", "Gene therapy", None),
    ("wiki_self_driving", "Self-driving cars", None),
    ("wiki_starship", "SpaceX Starship", "space_launches"),
]

PHASES = {
    # key: (label, the call it implies for the next 90 days, position on the drawn curve 0..1)
    "rising": ("Climbing to a peak", "up", 0.16),
    "peak": ("At or near the peak", "down", 0.27),
    "sliding": ("Sliding into the trough", "down", 0.42),
    "trough": ("In the trough", "flat", 0.55),
    "recovering": ("Climbing back", "up", 0.70),
    "plateau": ("On a plateau", "flat", 0.88),
}
ORDER = list(PHASES)


@dataclass
class Reading:
    level: float
    slope: float
    now: float
    peak: float
    peak_date: pd.Timestamp


def daily(series: pd.Series) -> pd.Series:
    """Daily values with gaps filled by the last value (pageviews have few gaps)."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return s
    s.index = pd.to_datetime(s.index)
    return s.sort_index().asfreq("D").ffill()


def read(s: pd.Series) -> Reading | None:
    """Level and slope from the daily history up to its last day (nothing later is used)."""
    if len(s) < 2 * WINDOW:
        return None
    smooth = s.rolling(WINDOW).mean().dropna()
    now, before = float(smooth.iloc[-1]), float(smooth.iloc[-1 - WINDOW]) if len(smooth) > WINDOW else float(s.iloc[:WINDOW].mean())
    peak_at = smooth.idxmax()
    peak = float(smooth.loc[peak_at])
    if peak <= 0 or now <= 0 or before <= 0:
        return None
    return Reading(now / peak, math.log(now / before), now, peak, peak_at)


def phase(r: Reading) -> str:
    """The hype-cycle phase from level and slope; the order of the rules matters."""
    if r.level >= AT_PEAK and r.slope > FLAT:
        return "rising"
    if r.level >= NEAR_PEAK:
        return "peak"
    if r.slope < -FLAT:
        return "sliding"
    if r.slope > FLAT:
        return "recovering"
    if r.level < DEEP:
        return "trough"
    return "plateau"


def direction(change: float) -> str:
    return "up" if change > FLAT else "down" if change < -FLAT else "flat"


def burst_call(slope: float) -> str:
    """The burst rule: after attention rose 30% or more in 90 days, expect it to fall; after it
    fell 30% or more, expect it to rise; otherwise expect about the same."""
    pct = math.expm1(slope)
    return "down" if pct >= BURST else "up" if pct <= -BURST else "flat"


def backtest_one(sid: str, series: pd.Series) -> pd.DataFrame:
    """One call a month: the phase, its call, momentum's call and what the next 90 days did."""
    s = daily(series)
    rows = []
    if len(s) < MIN_HISTORY + WINDOW:
        return pd.DataFrame()
    last = len(s) - WINDOW
    for i in range(MIN_HISTORY, last + 1, STEP):
        past = s.iloc[:i]
        r = read(past)
        if r is None:
            continue
        ahead = float(s.iloc[i:i + WINDOW].mean())
        if ahead <= 0:
            continue
        change = math.log(ahead / r.now)
        p = phase(r)
        rows.append({"series_id": sid, "origin": past.index[-1].date().isoformat(), "phase": p, "level": round(r.level, 4),
                     "slope": round(r.slope, 4), "call": PHASES[p][1], "momentum": direction(r.slope), "burst": burst_call(r.slope),
                     "change": round(change, 4), "outcome": direction(change)})
    return pd.DataFrame(rows)


def backtest(data: dict[str, pd.Series]) -> pd.DataFrame:
    frames = [backtest_one(sid, data[sid]) for sid, _, _ in TECH if sid in data]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _binom_p(hits: int, n: int, p0: float) -> float | None:
    """One-sided chance of at least ``hits`` successes in ``n`` tries at rate ``p0`` (exact)."""
    if n == 0 or p0 <= 0 or p0 >= 1:
        return None
    from math import comb
    return float(min(1.0, sum(comb(n, k) * p0 ** k * (1 - p0) ** (n - k) for k in range(hits, n + 1))))


def record(rows: pd.DataFrame | None) -> dict | None:
    """How often each forecaster called the next 90 days right, overall and by phase, and the
    hype cycle's own claim: after a call at the peak, did attention fall more often than usual?
    Windows a month apart overlap by two months, so the counts are not independent: the p-value is
    worked out on a third of them (``WINDOW // STEP``, as if only every third call counted), and is
    still a rough guide, not a verdict."""
    if rows is None or rows.empty:
        return None
    rows = rows.assign(reversal=rows["momentum"].map(REVERSE))
    if "burst" not in rows:  # a backtest saved before the burst rule existed
        rows = rows.assign(burst=rows["slope"].map(burst_call))
    hit = rows["call"] == rows["outcome"]
    mom = rows["momentum"] == rows["outcome"]
    rev = rows["reversal"] == rows["outcome"]
    flat = rows["outcome"] == "flat"
    by_phase = {}
    for p in ORDER:
        g = rows[rows["phase"] == p]
        if len(g):
            by_phase[p] = {"n": int(len(g)), "hit": int((g["call"] == g["outcome"]).sum()),
                           "momentum": int((g["momentum"] == g["outcome"]).sum()),
                           "reversal": int((g["reversal"] == g["outcome"]).sum()),
                           "burst": int((g["burst"] == g["outcome"]).sum()),
                           "up": int((g["outcome"] == "up").sum()), "down": int((g["outcome"] == "down").sum()),
                           "median_change": round(float(np.expm1(g["change"].median())), 4)}
    peaks = rows[rows["phase"] == "peak"]
    base_fall = float((rows["outcome"] == "down").mean())
    fell = int((peaks["outcome"] == "down").sum())
    return {
        "n": int(len(rows)), "series": int(rows["series_id"].nunique()),
        "first": str(rows["origin"].min()), "last": str(rows["origin"].max()),
        "hype": int(hit.sum()), "momentum": int(mom.sum()), "reversal": int(rev.sum()), "flat": int(flat.sum()),
        "burst": int((rows["burst"] == rows["outcome"]).sum()), "same_as_momentum": int((rows["call"] == rows["momentum"]).sum()),
        "since_found": {"from": FOUND, "n": int((after := rows[rows["origin"] >= FOUND]).shape[0]),
                        "burst": int((after["burst"] == after["outcome"]).sum()), "flat": int((after["outcome"] == "flat").sum())},
        "by_phase": by_phase, "bursts": bursts(rows),
        "after_peak": {"n": int(len(peaks)), "fell": fell, "base": round(base_fall, 4),
                       "p": _binom_p(round(fell / OVERLAP), round(len(peaks) / OVERLAP), base_fall)},
    }


REVERSE = {"up": "down", "down": "up", "flat": "flat"}
# What the last 90 days did against the 90 before, in plain percentages (the slope is a log change).
BURSTS = [("fell", "Fell 30% or more", -np.inf, -0.30), ("eased", "Fell 10% to 30%", -0.30, -0.10),
          ("steady", "Within 10%", -0.10, 0.10), ("rose", "Rose 10% to 30%", 0.10, 0.30), ("jumped", "Rose 30% or more", 0.30, np.inf)]


def bursts(rows: pd.DataFrame) -> list[dict]:
    """After attention rose or fell by so much over 90 days, what did the next 90 days do? The
    p-value asks whether the move reversed more often than attention moved that way at all
    (counted on a third of the windows, as they overlap)."""
    pct = np.expm1(rows["slope"])
    base = {d: float((rows["outcome"] == d).mean()) for d in ("up", "down")}
    out = []
    for key, label, lo, hi in BURSTS:
        g = rows[(pct > lo) & (pct <= hi)] if np.isfinite(lo) else rows[pct <= hi]
        if g.empty:
            continue
        up, down = int((g["outcome"] == "up").sum()), int((g["outcome"] == "down").sum())
        back = "down" if lo >= 0.10 else "up" if hi <= -0.10 else None
        n_back = down if back == "down" else up if back == "up" else None
        out.append({"key": key, "label": label, "n": int(len(g)), "up": up, "down": down, "flat": int(len(g) - up - down),
                    "median_change": round(float(np.expm1(g["change"].median())), 4), "back": back,
                    "p": _binom_p(round(n_back / OVERLAP), round(len(g) / OVERLAP), base[back]) if back else None})
    return out


def verdict(rec: dict | None) -> str:
    """One plain sentence on whether the phases knew anything momentum did not."""
    if not rec or rec["n"] < 20:
        return "Not enough history for a verdict yet."
    n, h, m, f, r = rec["n"], rec["hype"], rec["momentum"], rec["flat"], rec.get("reversal", 0)
    bu = rec.get("burst", 0)
    best = max(("the hype cycle", h), ("momentum", m), ("reversal", r), ("the burst rule", bu), ("no change", f), key=lambda t: t[1])
    sm = rec.get("same_as_momentum")
    same = (f" The phases are mostly momentum in disguise: they made the same call {sm / n:.0%} of the time, as most phases are"
            f" read from the trend itself." if sm is not None else "")
    ap = rec["after_peak"]
    peak = ""
    if ap["n"]:
        rate = ap["fell"] / ap["n"]
        peak = (f" After a call at the peak, attention fell {ap['fell']} times in {ap['n']} ({rate:.0%}), against {ap['base']:.0%} of all windows"
                + (", more often than usual." if ap["p"] is not None and ap["p"] < 0.05 else ", which could be chance."))
    b = {x["key"]: x for x in rec.get("bursts", [])}
    burst = ""
    if b.get("jumped") and b.get("fell"):
        j, d = b["jumped"], b["fell"]
        burst = (f" Attention reverts: after a rise of 30% or more it fell next {j['down']} times in {j['n']} ({j['down'] / j['n']:.0%}) and rose {j['up'] / j['n']:.0%}; "
                 f"after a fall of 30% or more it rose {d['up']} times in {d['n']} ({d['up'] / d['n']:.0%}).")
    return (f"Over {n} monthly calls the hype cycle got the next 90 days' direction right {h} times ({h / n:.0%}), "
            f"momentum {m} ({m / n:.0%}), reversal {r} ({r / n:.0%}), the burst rule {bu} ({bu / n:.0%}) and \"no change\" {f} ({f / n:.0%}); "
            f"{best[0]} did best.{same}{peak}{burst} The burst rule was read off this same backtest on {FOUND}, so only its calls after that day are a fair test.")


def _curve(s: pd.Series, points: int = 140) -> list:
    """The 90-day mean, thinned for a small chart."""
    smooth = s.rolling(WINDOW, min_periods=WINDOW // 3).mean().dropna()
    if smooth.empty:
        return []
    idx = np.unique(np.linspace(0, len(smooth) - 1, min(points, len(smooth))).round().astype(int))
    return [[smooth.index[i].date().isoformat(), round(float(smooth.iloc[i]), 1)] for i in idx]


def _adoption(series: pd.Series | None) -> dict | None:
    if series is None:
        return None
    a = pd.to_numeric(series, errors="coerce").dropna()
    if len(a) < 2:
        return None
    a.index = pd.to_datetime(a.index)
    back = a.iloc[-4] if len(a) >= 4 else a.iloc[0]
    years = max(1, a.index[-1].year - (a.index[-4].year if len(a) >= 4 else a.index[0].year))
    return {"last": round(float(a.iloc[-1]), 4), "year": int(a.index[-1].year), "then": round(float(back), 4),
            "since": int(a.index[-1].year - years), "change": round(float(a.iloc[-1] / back - 1), 4) if back else None,
            "values": [[int(t.year), round(float(v), 4)] for t, v in a.iloc[-12:].items()]}


def now(data: dict[str, pd.Series]) -> list[dict]:
    """Every technology's phase today, its curve since 2015 and its adoption beside it."""
    from . import catalog
    titles = {s.id: s.description for s in catalog.CATALOG}
    out = []
    for sid, name, adopt in TECH:
        if sid not in data:
            continue
        s = daily(data[sid])
        r = read(s)
        if r is None:
            continue
        p = phase(r)
        label, call, x = PHASES[p]
        ad = _adoption(data.get(adopt)) if adopt else None
        if ad:
            ad.update({"id": adopt, "title": titles.get(adopt, adopt)})
        out.append({
            "id": sid, "name": name, "phase": p, "label": label, "call": call, "x": x, "burst": burst_call(r.slope),
            "level": round(r.level, 4), "slope": round(r.slope, 4), "now": round(r.now, 1), "peak": round(r.peak, 1),
            "peak_date": r.peak_date.date().isoformat(), "since": s.index[0].date().isoformat(), "last": s.index[-1].date().isoformat(),
            "curve": _curve(s), "adoption": ad,
            "faded": bool(ad and ad.get("change") is not None and ad["change"] > 0 and r.level < NEAR_PEAK),
        })
    return out


def payload(data: dict[str, pd.Series], rows: pd.DataFrame | None = None) -> dict | None:
    """The app's hype-cycle view: today's phases and the backtest of what the phases foretold."""
    items = now(data)
    if not items:
        return None
    rows = backtest(data) if rows is None else rows
    rec = record(rows)
    return {"made_on": max(it["last"] for it in items), "items": items, "record": rec, "verdict": verdict(rec),
            "rules": {"window": WINDOW, "min_history": MIN_HISTORY, "burst": BURST, "found": FOUND, "flat": FLAT, "near_peak": NEAR_PEAK, "at_peak": AT_PEAK, "deep": DEEP, "step": STEP,
                      "phases": {k: {"label": v[0], "call": v[1]} for k, v in PHASES.items()}}}


def describe(p: dict | None) -> str:
    """Terminal text for ``psychohistory hype``."""
    if not p:
        return "No Wikipedia attention series loaded; run `psychohistory fetch --domain tech` first."
    lines = [f"The hype cycle, {p['made_on']} (90-day mean Wikipedia views against the highest 90-day mean since the data began):", ""]
    lines.append(f"{'technology':24} {'phase':24} {'vs peak':>8} {'90-day trend':>13} {'peak':>11}  {'hype cycle says':16} burst rule says")
    for it in sorted(p["items"], key=lambda i: ORDER.index(i["phase"])):
        lines.append(f"{it['name'][:24]:24} {it['label']:24} {it['level']:>8.0%} {math.expm1(it['slope']):>+13.0%} {it['peak_date']:>11}  {it['call']:16} {it.get('burst', '–')}")
        if it.get("adoption"):
            a = it["adoption"]
            ch = f"{a['change']:+.0%}" if a.get("change") is not None else "–"
            lines.append(f"{'':24} adoption: {a['title']} {a['last']:g} in {a['year']} ({ch} since {a['since']})"
                         + ("; attention faded while adoption grew" if it["faded"] else ""))
    lines += ["", p["verdict"]]
    rec = p.get("record") or {}
    if rec.get("bursts"):
        lines += ["", "What the next 90 days did after attention moved (share of calls):"]
        for b in rec["bursts"]:
            pv = f"  p {b['p']:.2f}" if b.get("p") is not None else ""
            lines.append(f"  {b['label']:18} {b['n']:>4} calls   rose {b['up'] / b['n']:>4.0%}   fell {b['down'] / b['n']:>4.0%}   "
                         f"flat {b['flat'] / b['n']:>4.0%}   median {b['median_change']:+.0%}{pv}")
    sf = rec.get("since_found")
    if sf:
        lines.append("")
        lines.append(f"Fair test of the burst rule since {sf['from']}: " + (
            f"{sf['burst']} right in {sf['n']} settled calls ({sf['burst'] / sf['n']:.0%}), \"no change\" {sf['flat']} ({sf['flat'] / sf['n']:.0%})."
            if sf["n"] else "no call has settled yet (each needs 90 days)."))
    return "\n".join(lines)
